"""Start Step Functions executions for research jobs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import boto3

from helpers.config import get_aws_region, get_state_machine_arn


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _client():
    return boto3.client("stepfunctions", region_name=get_aws_region())


def start_enqueue_execution(
    job_id: str,
    question: str,
    *,
    state_machine_arn: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """
    Start deep-research-enqueue. Returns StartExecution response fields.

    DynamoDB + SQS writes happen inside the state machine.
    """
    arn = state_machine_arn or get_state_machine_arn()
    payload = {
        "job_id": job_id,
        "question": question,
        "created_at": created_at or _now(),
    }
    resp = _client().start_execution(
        stateMachineArn=arn,
        name=f"api-{job_id}",
        input=json.dumps(payload),
    )
    return {
        "execution_arn": resp["executionArn"],
        "start_date": resp["startDate"].isoformat(),
        "job_id": job_id,
    }
