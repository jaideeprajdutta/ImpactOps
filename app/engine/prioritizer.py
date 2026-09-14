from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from app.engine.mock_generator import _default_data_dir

ISSUE_PROTOTYPES = {
    "SSO Login Failure": "sso login saml okta azure redirect assertion authentication 401 lockout",
    "Webhook Delivery Timeouts": "webhook timeout retry delayed delivery endpoint queue notification",
    "CSV Export Truncation": "csv export truncated missing rows report download incomplete",
    "Billing Invoice Duplicate": "billing invoice duplicate charged twice over billed line items",
    "Safari UI Clipping": "safari ui clipping layout hidden buttons overlap modal table",
}


@dataclass
class PrioritizationResult:
    clusters: list[dict[str, Any]]
    total_mrr_at_risk: float
    total_affected_customers: int


def _tokenize(text: str) -> Counter[str]:
    tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return Counter(tokens)


def _cosine_similarity(left: Counter[str], right: Counter[str]) -> float:
    common = set(left) & set(right)
    dot = sum(left[token] * right[token] for token in common)
    left_mag = math.sqrt(sum(value * value for value in left.values()))
    right_mag = math.sqrt(sum(value * value for value in right.values()))
    if not left_mag or not right_mag:
        return 0.0
    return dot / (left_mag * right_mag)


def _assign_cluster(text: str) -> str:
    text_vector = _tokenize(text)
    best_cluster = "General Product Defect"
    best_score = 0.0
    for cluster, prototype in ISSUE_PROTOTYPES.items():
        score = _cosine_similarity(text_vector, _tokenize(prototype))
        if score > best_score:
            best_cluster = cluster
            best_score = score
    return best_cluster if best_score >= 0.08 else "General Product Defect"


def _severity_from_mrr(total_mrr: float) -> str:
    if total_mrr >= 15000:
        return "critical"
    if total_mrr >= 8000:
        return "high"
    if total_mrr >= 3000:
        return "medium"
    return "low"


def analyze_priorities(
    customers_path: str | Path | None = None,
    tickets_path: str | Path | None = None,
) -> PrioritizationResult:
    data_dir = _default_data_dir()
    customer_file = Path(customers_path or data_dir / "mock_stripe_customers.csv")
    ticket_file = Path(tickets_path or data_dir / "mock_support_tickets.csv")

    if not customer_file.exists() or not ticket_file.exists():
        raise FileNotFoundError("Mock CSV files not found. Run data generation endpoint first.")

    customers = pd.read_csv(customer_file)
    tickets = pd.read_csv(ticket_file)

    merged = tickets.merge(
        customers[["customer_id", "user_email", "mrr"]],
        on="user_email",
        how="left",
    )
    merged["mrr"] = merged["mrr"].fillna(0.0).astype(float)
    merged["customer_id"] = merged["customer_id"].fillna("UNKNOWN")
    merged["cluster"] = (merged["subject"].fillna("") + " " + merged["body"].fillna("")).apply(_assign_cluster)
    merged["excerpt"] = (
        merged["subject"].fillna("").str.strip() + ": " + merged["body"].fillna("").str.strip().str.slice(0, 160)
    )

    known_customers = merged[merged["customer_id"] != "UNKNOWN"].copy()
    unique_customer_impact = known_customers[["cluster", "customer_id", "mrr"]].drop_duplicates(
        subset=["cluster", "customer_id"]
    )
    mrr_agg = (
        unique_customer_impact.groupby("cluster", as_index=False)
        .agg(
            total_mrr_at_risk=("mrr", "sum"),
            affected_customer_count=("customer_id", "nunique"),
            average_mrr=("mrr", "mean"),
        )
        .fillna(0.0)
    )

    ticket_agg = merged.groupby("cluster", as_index=False).agg(ticket_count=("ticket_id", "count"))
    sample_rows = merged.groupby("cluster")["excerpt"].apply(lambda s: s.head(3).tolist()).reset_index(name="samples")

    result = mrr_agg.merge(ticket_agg, on="cluster", how="outer").merge(sample_rows, on="cluster", how="outer")
    result["total_mrr_at_risk"] = result["total_mrr_at_risk"].fillna(0.0)
    result["affected_customer_count"] = result["affected_customer_count"].fillna(0).astype(int)
    result["average_mrr"] = result["average_mrr"].fillna(0.0)
    result["ticket_count"] = result["ticket_count"].fillna(0).astype(int)
    result["samples"] = result["samples"].apply(lambda x: x if isinstance(x, list) else [])
    result = result.sort_values(by=["total_mrr_at_risk", "ticket_count"], ascending=False).reset_index(drop=True)

    clusters: list[dict[str, Any]] = []
    for idx, row in result.iterrows():
        clusters.append(
            {
                "cluster_id": idx + 1,
                "issue_cluster": row["cluster"],
                "severity": _severity_from_mrr(float(row["total_mrr_at_risk"])),
                "total_mrr_at_risk": round(float(row["total_mrr_at_risk"]), 2),
                "affected_customer_count": int(row["affected_customer_count"]),
                "average_mrr": round(float(row["average_mrr"]), 2),
                "ticket_count": int(row["ticket_count"]),
                "sample_ticket_excerpts": row["samples"],
            }
        )

    return PrioritizationResult(
        clusters=clusters,
        total_mrr_at_risk=round(sum(item["total_mrr_at_risk"] for item in clusters), 2),
        total_affected_customers=int(unique_customer_impact["customer_id"].nunique()),
    )


def render_markdown_report(result: PrioritizationResult) -> str:
    lines = [
        "# ImpactOps Backlog Prioritization Report",
        "",
        f"- Total MRR at Risk: **${result.total_mrr_at_risk:,.2f}**",
        f"- Total Affected Customers: **{result.total_affected_customers}**",
        "",
        "## Ranked Issue Clusters",
        "",
    ]
    for cluster in result.clusters:
        lines.extend(
            [
                f"### {cluster['cluster_id']}. {cluster['issue_cluster']}",
                f"- Severity: **{cluster['severity']}**",
                f"- Total MRR at Risk: **${cluster['total_mrr_at_risk']:,.2f}**",
                f"- Affected Customers: **{cluster['affected_customer_count']}**",
                f"- Average MRR: **${cluster['average_mrr']:,.2f}**",
                f"- Ticket Count: **{cluster['ticket_count']}**",
                "- Sample Ticket Excerpts:",
            ]
        )
        if cluster["sample_ticket_excerpts"]:
            for excerpt in cluster["sample_ticket_excerpts"]:
                lines.append(f"  - {excerpt}")
        else:
            lines.append("  - (No excerpts available)")
        lines.append("")
    return "\n".join(lines).strip() + "\n"
