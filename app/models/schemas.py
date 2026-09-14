from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok"]


class GenerateMockDataResponse(BaseModel):
    customers_file: str
    tickets_file: str
    customer_count: int
    ticket_count: int


class IssueCluster(BaseModel):
    cluster_id: int
    issue_cluster: str
    severity: Literal["critical", "high", "medium", "low"]
    total_mrr_at_risk: float = Field(ge=0)
    affected_customer_count: int = Field(ge=0)
    average_mrr: float = Field(ge=0)
    ticket_count: int = Field(ge=0)
    sample_ticket_excerpts: list[str]


class AnalyzeResponse(BaseModel):
    total_mrr_at_risk: float = Field(ge=0)
    total_affected_customers: int = Field(ge=0)
    issue_clusters: list[IssueCluster]
