"""SQS helpers for research job messages."""

from __future__ import annotations

import json
from dataclasses import dataclass

import boto3

from helpers.config import get_aws_region, get_jobs_queue_url


@dataclass
class QueueMessage:
    job_id: str
    question: str
    receipt_handle: str
    message_id: str
    receive_count: int


def _client():
    return boto3.client("sqs", region_name=get_aws_region())


def receive_job(
    *,
    queue_url: str | None = None,
    wait_seconds: int = 10,
    visibility_timeout: int = 300,
) -> QueueMessage | None:
    """Long-poll for one job message. None if queue is empty."""
    url = queue_url or get_jobs_queue_url()
    resp = _client().receive_message(
        QueueUrl=url,
        MaxNumberOfMessages=1,
        WaitTimeSeconds=wait_seconds,
        VisibilityTimeout=visibility_timeout,
        AttributeNames=["ApproximateReceiveCount"],
    )
    messages = resp.get("Messages") or []
    if not messages:
        return None

    msg = messages[0]
    body = json.loads(msg["Body"])
    return QueueMessage(
        job_id=str(body["job_id"]),
        question=str(body["question"]),
        receipt_handle=msg["ReceiptHandle"],
        message_id=msg["MessageId"],
        receive_count=int(
            msg.get("Attributes", {}).get("ApproximateReceiveCount", 1)
        ),
    )


def delete_message(receipt_handle: str, *, queue_url: str | None = None) -> None:
    """Ack success: remove message so it is not retried."""
    url = queue_url or get_jobs_queue_url()
    _client().delete_message(QueueUrl=url, ReceiptHandle=receipt_handle)
