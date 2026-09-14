from __future__ import annotations

import unittest
from pathlib import Path

import pandas as pd

from app.engine.mock_generator import generate_mock_data
from app.engine.prioritizer import analyze_priorities, render_markdown_report


class EngineTests(unittest.TestCase):
    def test_generate_mock_data_creates_expected_csv_files(self) -> None:
        data_dir = Path("tests/.tmp-data")
        if data_dir.exists():
            for file in data_dir.glob("*.csv"):
                file.unlink()
        output = generate_mock_data(data_dir=data_dir, customer_count=40, ticket_count=100, seed=9)

        customers = pd.read_csv(output["customers_file"])
        tickets = pd.read_csv(output["tickets_file"])

        self.assertEqual(40, len(customers))
        self.assertEqual(100, len(tickets))
        self.assertListEqual(
            ["customer_id", "user_email", "company_name", "subscription_tier", "mrr"],
            list(customers.columns),
        )
        self.assertListEqual(
            ["ticket_id", "user_email", "created_at", "subject", "body"],
            list(tickets.columns),
        )
        self.assertTrue((customers["mrr"] >= 50).all())
        self.assertTrue((customers["mrr"] <= 5000).all())

    def test_analyze_priorities_returns_ranked_clusters(self) -> None:
        data_dir = Path("tests/.tmp-data")
        output = generate_mock_data(data_dir=data_dir, customer_count=50, ticket_count=100, seed=21)
        result = analyze_priorities(output["customers_file"], output["tickets_file"])

        self.assertGreater(len(result.clusters), 0)
        totals = [cluster["total_mrr_at_risk"] for cluster in result.clusters]
        self.assertEqual(totals, sorted(totals, reverse=True))
        for cluster in result.clusters:
            self.assertIn("issue_cluster", cluster)
            self.assertIn("severity", cluster)
            self.assertGreaterEqual(len(cluster["sample_ticket_excerpts"]), 0)

        markdown = render_markdown_report(result)
        self.assertIn("# ImpactOps Backlog Prioritization Report", markdown)


if __name__ == "__main__":
    unittest.main()
