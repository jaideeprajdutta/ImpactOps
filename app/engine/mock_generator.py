from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

ROOT_CAUSES = {
    "SSO Login Failure": {
        "subjects": [
            "SSO users locked out after IdP redirect",
            "Okta SSO fails with invalid assertion",
            "Cannot sign in with SAML SSO",
            "Azure AD login loop on ImpactOps",
        ],
        "bodies": [
            "Our admins are seeing repeated redirect loops after authenticating with {idp}. The browser lands back on login and users cannot access dashboards.",
            "Since this morning, SSO logins are rejected with assertion validation errors. We have not changed our {idp} app config.",
            "Roughly half of users get a 401 after completing SSO. Password login is disabled so this is blocking operations.",
        ],
    },
    "Webhook Delivery Timeouts": {
        "subjects": [
            "Outgoing webhooks timing out to downstream API",
            "Webhook retries piling up for event delivery",
            "Delivery latency spike on webhook notifications",
            "Critical events never reach our endpoint",
        ],
        "bodies": [
            "Webhook calls to our endpoint are timing out after 10 seconds and then retrying for hours. This is delaying customer sync.",
            "We see large retry backlogs for webhooks and duplicate side effects in our system due to repeated deliveries.",
            "Event notifications are delayed by 20+ minutes because webhook delivery keeps failing with timeout errors.",
        ],
    },
    "CSV Export Truncation": {
        "subjects": [
            "CSV export cuts off rows after first page",
            "Exported report missing trailing records",
            "Downloaded CSV appears truncated",
            "Large usage export incomplete",
        ],
        "bodies": [
            "When exporting usage logs to CSV, the file contains far fewer rows than the UI count. It seems capped unexpectedly.",
            "Our finance report export is missing records near the end of the date range, causing reconciliation issues.",
            "CSV downloads truncate long text fields and stop after around 1,000 rows for large datasets.",
        ],
    },
    "Billing Invoice Duplicate": {
        "subjects": [
            "Duplicate invoices generated for same billing period",
            "Customer charged twice this month",
            "Invoice run created duplicated line items",
            "Billing cycle produced two invoices",
        ],
        "bodies": [
            "Two invoices were generated for the same account and period. We need urgent clarification to prevent customer churn.",
            "Our customer received duplicate charges tied to invoice IDs that reference the same subscription window.",
            "The last invoice run appears to have duplicated records and over-billed accounts in production.",
        ],
    },
    "Safari UI Clipping": {
        "subjects": [
            "Dashboard panels clipped in Safari",
            "Buttons hidden on Safari 17",
            "Modal footer cut off in Safari browser",
            "Table header overlaps content on Safari",
        ],
        "bodies": [
            "In Safari, key controls are clipped and users cannot click Save in configuration modals.",
            "Layouts render correctly in Chrome but Safari clips side panels and hides action buttons.",
            "Navigation and table headers overlap in Safari, making the workflow unusable for our team.",
        ],
    },
}

IDP_PROVIDERS = ["Okta", "Azure AD", "Google Workspace", "OneLogin"]
SUBSCRIPTION_TIERS = ["Enterprise", "Pro", "Starter"]
TIER_WEIGHTS = [0.2, 0.45, 0.35]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_data_dir() -> Path:
    return _repo_root() / "data"


def _tier_mrr(tier: str, rng: random.Random) -> float:
    if tier == "Enterprise":
        return round(rng.uniform(1800, 5000), 2)
    if tier == "Pro":
        return round(rng.uniform(400, 2200), 2)
    return round(rng.uniform(50, 600), 2)


def generate_mock_data(
    data_dir: Path | None = None,
    customer_count: int = 60,
    ticket_count: int = 100,
    seed: int = 42,
) -> dict[str, Any]:
    rng = random.Random(seed)
    target_dir = data_dir or _default_data_dir()
    target_dir.mkdir(parents=True, exist_ok=True)

    customers: list[dict[str, Any]] = []
    for idx in range(1, customer_count + 1):
        company_slug = f"company{idx:03d}"
        company_name = f"{company_slug.capitalize()} Labs"
        email = f"ops{idx:03d}@{company_slug}.com"
        tier = rng.choices(SUBSCRIPTION_TIERS, weights=TIER_WEIGHTS, k=1)[0]
        customers.append(
            {
                "customer_id": f"CUST-{idx:04d}",
                "user_email": email,
                "company_name": company_name,
                "subscription_tier": tier,
                "mrr": _tier_mrr(tier, rng),
            }
        )

    customer_df = pd.DataFrame(customers)
    customer_path = target_dir / "mock_stripe_customers.csv"
    customer_df.to_csv(customer_path, index=False)

    now = datetime.now(timezone.utc)
    causes = list(ROOT_CAUSES.keys())
    cause_weights = [0.24, 0.22, 0.2, 0.19, 0.15]

    tickets: list[dict[str, str]] = []
    customer_emails = customer_df["user_email"].tolist()
    for idx in range(1, ticket_count + 1):
        cause = rng.choices(causes, weights=cause_weights, k=1)[0]
        bundle = ROOT_CAUSES[cause]
        subject = rng.choice(bundle["subjects"])
        body = rng.choice(bundle["bodies"]).format(idp=rng.choice(IDP_PROVIDERS))
        created_at = (now - timedelta(hours=rng.randint(1, 24 * 30))).isoformat(timespec="seconds") + "Z"
        tickets.append(
            {
                "ticket_id": f"TICK-{idx:05d}",
                "user_email": rng.choice(customer_emails),
                "created_at": created_at,
                "subject": subject,
                "body": body,
            }
        )

    ticket_df = pd.DataFrame(tickets)
    ticket_path = target_dir / "mock_support_tickets.csv"
    ticket_df.to_csv(ticket_path, index=False)

    return {
        "customers_file": str(customer_path),
        "tickets_file": str(ticket_path),
        "customer_count": customer_count,
        "ticket_count": ticket_count,
    }
