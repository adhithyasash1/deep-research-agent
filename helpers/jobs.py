"""DynamoDB job state: QUEUED → RUNNING → COMPLETED / FAILED."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import boto3

from helpers.config import get_aws_region, get_jobs_table

STATUS_QUEUED = "QUEUED"
STATUS_RUNNING = "RUNNING"
STATUS_COMPLETED = "COMPLETED"
STATUS_FAILED = "FAILED"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _table():
    return boto3.resource("dynamodb", region_name=get_aws_region()).Table(get_jobs_table())


def new_job_id() -> str:
    return uuid.uuid4().hex[:12]


def create_job(question: str, *, job_id: str | None = None) -> str:
    """Create a job row with status=RUNNING (direct/ECS one-shot path)."""
    jid = job_id or new_job_id()
    now = _now()
    _table().put_item(
        Item={
            "job_id": jid,
            "question": question,
            "status": STATUS_RUNNING,
            "created_at": now,
            "updated_at": now,
        },
        # Idempotency: refuse to overwrite an existing job_id
        ConditionExpression="attribute_not_exists(job_id)",
    )
    return jid


def mark_running(job_id: str) -> None:
    _table().update_item(
        Key={"job_id": job_id},
        UpdateExpression="SET #s = :s, updated_at = :u",
        # Never upsert a ghost row for an unknown job_id
        ConditionExpression="attribute_exists(job_id)",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": STATUS_RUNNING, ":u": _now()},
    )


def mark_completed(job_id: str, *, s3_uri: str | None = None) -> None:
    expr = "SET #s = :s, updated_at = :u"
    names = {"#s": "status"}
    values: dict[str, Any] = {":s": STATUS_COMPLETED, ":u": _now()}
    if s3_uri:
        expr += ", s3_uri = :uri"
        values[":uri"] = s3_uri

    _table().update_item(
        Key={"job_id": job_id},
        UpdateExpression=expr,
        ConditionExpression="attribute_exists(job_id)",
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
    )


def mark_failed(job_id: str, error: str) -> None:
    _table().update_item(
        Key={"job_id": job_id},
        UpdateExpression="SET #s = :s, updated_at = :u, #e = :e",
        ConditionExpression="attribute_exists(job_id)",
        ExpressionAttributeNames={"#s": "status", "#e": "error"},
        ExpressionAttributeValues={
            ":s": STATUS_FAILED,
            ":u": _now(),
            ":e": error[:1000],
        },
    )


def get_job(job_id: str) -> dict[str, Any] | None:
    resp = _table().get_item(Key={"job_id": job_id})
    return resp.get("Item")
