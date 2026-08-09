"""Publish domain events to EventBridge."""

from __future__ import annotations

import json
from typing import Any

import boto3

from helpers.config import get_aws_region, get_event_bus_name

SOURCE = "deep.research.agent"


def _client():
    return boto3.client("events", region_name=get_aws_region())


def put_research_event(
    detail_type: str,
    detail: dict[str, Any],
    *,
    event_bus_name: str | None = None,
) -> str | None:
    """
    Put one event on the bus. Returns EventId, or None if AWS dropped the entry.
    """
    bus = event_bus_name or get_event_bus_name()
    resp = _client().put_events(
        Entries=[
            {
                "EventBusName": bus,
                "Source": SOURCE,
                "DetailType": detail_type,
                "Detail": json.dumps(detail),
            }
        ]
    )
    entries = resp.get("Entries") or []
    if not entries:
        return None
    return entries[0].get("EventId")
