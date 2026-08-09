"""Upload local research reports to S3."""

from __future__ import annotations

import uuid
from pathlib import Path

import boto3

from helpers.config import get_aws_region, get_s3_bucket
from helpers.reports import slugify, title_from_report


def build_object_key(local_path: Path, *, question: str | None = None) -> str:
    """Build `reports/<8-hex>-<slug>.md`."""
    title = title_from_report(local_path) or question or local_path.stem
    return f"reports/{uuid.uuid4().hex[:8]}-{slugify(title)}.md"


def upload_report(
    local_path: Path,
    *,
    question: str | None = None,
    bucket: str | None = None,
    region: str | None = None,
    key: str | None = None,
) -> str:
    """Upload a local markdown report. Returns the s3:// URI."""
    if not local_path.is_file():
        raise FileNotFoundError(f"Local file not found: {local_path}")

    bucket = bucket or get_s3_bucket()
    region = region or get_aws_region()
    key = key or build_object_key(local_path, question=question)

    client = boto3.client("s3", region_name=region)
    client.upload_file(
        str(local_path),
        bucket,
        key,
        ExtraArgs={"ContentType": "text/markdown; charset=utf-8"},
    )
    return f"s3://{bucket}/{key}"
