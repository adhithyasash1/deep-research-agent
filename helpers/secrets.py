"""Load API keys from AWS Secrets Manager into the process environment."""

from __future__ import annotations

import json
import os
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from helpers.config import get_aws_region

KNOWN_SECRET_KEYS = (
    "GOOGLE_API_KEY",
    "TAVILY_API_KEY",
    "OPENROUTER_API_KEY",
    "GROQ_API_KEY",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "RESEARCH_API_KEY",
)


def get_secret_id(override: str | None = None) -> str | None:
    return override or os.environ.get("SECRETS_MANAGER_SECRET_ID") or None


def fetch_secret_dict(secret_id: str, *, region: str | None = None) -> dict[str, Any]:
    """Fetch and parse a Secrets Manager secret (JSON object)."""
    client = boto3.client("secretsmanager", region_name=region or get_aws_region())
    resp = client.get_secret_value(SecretId=secret_id)
    raw = resp.get("SecretString")
    if not raw:
        raise RuntimeError(f"Secret {secret_id!r} has no SecretString")

    data = json.loads(raw)
    if not isinstance(data, dict):
        raise RuntimeError(
            f"Secret {secret_id!r} must be a JSON object of key/value pairs"
        )
    return data


def apply_secrets_to_env(
    secret: dict[str, Any],
    *,
    overwrite: bool = False,
) -> list[str]:
    """Copy known keys from the secret into os.environ."""
    applied: list[str] = []
    for key in KNOWN_SECRET_KEYS:
        if key not in secret or secret[key] is None:
            continue
        text = str(secret[key]).strip()
        if not text:
            continue
        if not overwrite and os.environ.get(key):
            continue
        os.environ[key] = text
        applied.append(key)
    return applied


def load_secrets(
    secret_id: str | None = None,
    *,
    overwrite: bool = False,
    region: str | None = None,
) -> list[str]:
    """Load Secrets Manager values into the environment. No-op if unset."""
    sid = get_secret_id(secret_id)
    if not sid:
        return []

    try:
        data = fetch_secret_dict(sid, region=region)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "ClientError")
        message = exc.response.get("Error", {}).get("Message", str(exc))
        raise RuntimeError(f"Secrets Manager {code}: {message}") from exc
    except BotoCoreError as exc:
        raise RuntimeError(f"Secrets Manager error: {exc}") from exc

    return apply_secrets_to_env(data, overwrite=overwrite)
