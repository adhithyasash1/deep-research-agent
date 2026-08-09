"""FastAPI HTTP API: enqueue research jobs and read status."""

from __future__ import annotations

import os
import secrets
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field, field_validator

from helpers.config import load_settings
from helpers.jobs import get_job, new_job_id
from helpers.observability import log, put_metric
from helpers.stepfunctions import start_enqueue_execution

# .env for local dev; Secrets Manager overlay (RESEARCH_API_KEY, ...) on ECS
load_settings(secrets_overwrite=True)

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(provided: str | None = Security(_api_key_header)) -> None:
    expected = os.environ.get("RESEARCH_API_KEY")
    if not expected:
        # Fail closed if the server has no key configured
        log("api_key_not_configured")
        raise HTTPException(status_code=503, detail="API key not configured")
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="invalid or missing API key")

app = FastAPI(
    title="Deep Research Agent API",
    version="0.1.0",
    description=(
        "POST a question (starts Step Functions enqueue); "
        "poll job status while the ECS worker researches."
    ),
)


class ResearchRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)

    @field_validator("question")
    @classmethod
    def strip_question(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("question must contain at least 3 non-space characters")
        return value


class ResearchCreateResponse(BaseModel):
    job_id: str
    status: str


class ResearchStatusResponse(BaseModel):
    job_id: str
    question: str | None = None
    status: str
    s3_uri: str | None = None
    error: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


def _job_to_response(job: dict[str, Any]) -> ResearchStatusResponse:
    return ResearchStatusResponse(
        job_id=str(job["job_id"]),
        question=job.get("question"),
        status=str(job["status"]),
        s3_uri=job.get("s3_uri"),
        error=job.get("error"),
        created_at=job.get("created_at"),
        updated_at=job.get("updated_at"),
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/research",
    response_model=ResearchCreateResponse,
    status_code=202,
    dependencies=[Depends(require_api_key)],
)
def create_research(body: ResearchRequest) -> ResearchCreateResponse:
    """Accept a research question via Step Functions (DynamoDB + SQS inside ASL)."""
    try:
        job_id = new_job_id()
        start_enqueue_execution(job_id, body.question)
        log("api_job_enqueued", job_id=job_id, via="stepfunctions")
        put_metric("JobsEnqueued", dimensions={"Service": "api"})
        return ResearchCreateResponse(job_id=job_id, status="QUEUED")
    except Exception as exc:  # noqa: BLE001
        log("api_enqueue_error", error=str(exc))
        put_metric("ApiErrors", dimensions={"Service": "api"})
        raise HTTPException(status_code=503, detail="failed to enqueue job") from exc


@app.get(
    "/research/{job_id}",
    response_model=ResearchStatusResponse,
    dependencies=[Depends(require_api_key)],
)
def get_research(job_id: str) -> ResearchStatusResponse:
    job = get_job(job_id)
    if not job:
        log("api_job_not_found", job_id=job_id)
        raise HTTPException(status_code=404, detail=f"job not found: {job_id}")
    log("api_job_fetched", job_id=job_id, status=job.get("status"))
    return _job_to_response(job)
