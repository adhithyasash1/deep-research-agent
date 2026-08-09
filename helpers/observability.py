"""Structured logging + CloudWatch custom metrics."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any

import boto3

from helpers.config import get_aws_region

NAMESPACE = "DeepResearchAgent"


def log(event: str, **fields: Any) -> None:
    """Print one JSON log line (picked up by CloudWatch Logs on ECS)."""
    payload = {
        "ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        ),
        "event": event,
        **{k: v for k, v in fields.items() if v is not None},
    }
    print(json.dumps(payload, default=str), flush=True)


def put_metric(
    name: str,
    value: float = 1.0,
    *,
    unit: str = "Count",
    dimensions: dict[str, str] | None = None,
) -> None:
    """Emit a custom CloudWatch metric (best-effort; never crash the app)."""
    try:
        dims = [
            {"Name": k, "Value": v}
            for k, v in (dimensions or {}).items()
        ]
        boto3.client("cloudwatch", region_name=get_aws_region()).put_metric_data(
            Namespace=NAMESPACE,
            MetricData=[
                {
                    "MetricName": name,
                    "Value": value,
                    "Unit": unit,
                    "Dimensions": dims,
                }
            ],
        )
    except Exception as exc:  # noqa: BLE001
        print(
            json.dumps(
                {
                    "ts": datetime.now(timezone.utc)
                    .replace(microsecond=0)
                    .isoformat()
                    .replace("+00:00", "Z"),
                    "event": "metric_error",
                    "error": str(exc),
                    "metric": name,
                }
            ),
            file=sys.stderr,
            flush=True,
        )
