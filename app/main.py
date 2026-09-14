from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse

from app.engine.mock_generator import generate_mock_data
from app.engine.prioritizer import analyze_priorities, render_markdown_report
from app.models.schemas import AnalyzeResponse, GenerateMockDataResponse, HealthResponse

app = FastAPI(title="ImpactOps Prioritization API", version="0.1.0")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/api/v1/generate-mock-data", response_model=GenerateMockDataResponse)
def generate_mock_data_endpoint() -> GenerateMockDataResponse:
    return GenerateMockDataResponse(**generate_mock_data())


@app.post("/api/v1/analyze", response_model=AnalyzeResponse)
def analyze_endpoint() -> AnalyzeResponse:
    try:
        result = analyze_priorities()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return AnalyzeResponse(
        total_mrr_at_risk=result.total_mrr_at_risk,
        total_affected_customers=result.total_affected_customers,
        issue_clusters=result.clusters,
    )


@app.get("/api/v1/export-markdown", response_class=PlainTextResponse)
def export_markdown() -> str:
    try:
        result = analyze_priorities()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return render_markdown_report(result)
