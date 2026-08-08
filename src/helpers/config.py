"""Load settings from .env / environment."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT / ".env"

# Provider prefix → required env var
PROVIDER_KEYS = {
    "google_genai": "GOOGLE_API_KEY",
    "gemini": "GOOGLE_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "groq": "GROQ_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
}

DEFAULT_MODEL = "google_genai:gemini-3.5-flash"


def load_env() -> Path:
    """Load project .env if present. Returns the path that was considered."""
    load_dotenv(ENV_PATH)
    return ENV_PATH


def get_model(override: str | None = None) -> str:
    return override or os.environ.get("MODEL") or DEFAULT_MODEL


def provider_of(model: str) -> str:
    if ":" not in model:
        return ""
    return model.split(":", 1)[0]


def missing_keys(model: str) -> list[str]:
    """Return missing env vars needed for this model + Tavily."""
    missing: list[str] = []
    if not os.environ.get("TAVILY_API_KEY"):
        missing.append("TAVILY_API_KEY")

    provider = provider_of(model)
    key_name = PROVIDER_KEYS.get(provider)
    if key_name and not os.environ.get(key_name):
        missing.append(key_name)
    return missing
