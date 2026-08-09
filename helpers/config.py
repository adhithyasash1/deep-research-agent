"""Load settings from .env / environment."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"

PROVIDER_KEYS = {
    "google_genai": "GOOGLE_API_KEY",
    "gemini": "GOOGLE_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "groq": "GROQ_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
}

DEFAULT_MODEL = "google_genai:gemini-3.5-flash"
DEFAULT_S3_BUCKET = "deep-research-agent-139675292967-eu-north-1-an"
DEFAULT_AWS_REGION = "eu-north-1"
DEFAULT_JOBS_TABLE = "deep-research-jobs"
DEFAULT_JOBS_QUEUE_URL = (
    "https://sqs.eu-north-1.amazonaws.com/139675292967/deep-research-jobs"
)
DEFAULT_STATE_MACHINE_ARN = (
    "arn:aws:states:eu-north-1:139675292967:stateMachine:deep-research-enqueue"
)
DEFAULT_EVENT_BUS_NAME = "deep-research"


def load_env() -> Path:
    """Load project .env if present."""
    load_dotenv(ENV_PATH)
    return ENV_PATH


def load_settings(
    *,
    secrets: bool = True,
    secrets_overwrite: bool = False,
    secret_id: str | None = None,
) -> Path:
    """
    Load .env, then optionally overlay API keys from Secrets Manager.

    1) .env / process env (MODEL, AWS_REGION, S3_BUCKET, SECRETS_MANAGER_SECRET_ID)
    2) Secrets Manager JSON → GOOGLE_API_KEY, TAVILY_API_KEY, ...
    """
    path = load_env()
    if secrets:
        from helpers.secrets import load_secrets

        load_secrets(secret_id, overwrite=secrets_overwrite)
    return path


def get_model(override: str | None = None) -> str:
    return override or os.environ.get("MODEL") or DEFAULT_MODEL


def get_s3_bucket(override: str | None = None) -> str:
    return override or os.environ.get("S3_BUCKET") or DEFAULT_S3_BUCKET


def get_jobs_table(override: str | None = None) -> str:
    return override or os.environ.get("JOBS_TABLE") or DEFAULT_JOBS_TABLE


def get_jobs_queue_url(override: str | None = None) -> str:
    return override or os.environ.get("JOBS_QUEUE_URL") or DEFAULT_JOBS_QUEUE_URL


def get_state_machine_arn(override: str | None = None) -> str:
    return (
        override
        or os.environ.get("STATE_MACHINE_ARN")
        or DEFAULT_STATE_MACHINE_ARN
    )


def get_event_bus_name(override: str | None = None) -> str:
    return override or os.environ.get("EVENT_BUS_NAME") or DEFAULT_EVENT_BUS_NAME


def get_aws_region(override: str | None = None) -> str:
    return (
        override
        or os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or DEFAULT_AWS_REGION
    )


def provider_of(model: str) -> str:
    if ":" not in model:
        return ""
    return model.split(":", 1)[0]


def missing_keys(model: str) -> list[str]:
    """Return missing env vars needed for this model + Tavily."""
    missing: list[str] = []
    if not os.environ.get("TAVILY_API_KEY"):
        missing.append("TAVILY_API_KEY")

    key_name = PROVIDER_KEYS.get(provider_of(model))
    if key_name and not os.environ.get(key_name):
        missing.append(key_name)
    return missing
