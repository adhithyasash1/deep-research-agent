"""Local report staging: /report.md → reports/<hash>-<slug>.md."""

from __future__ import annotations

import re
import shutil
import uuid
from pathlib import Path

from helpers.config import ROOT

REPORTS_DIR = ROOT / "reports"
STAGING_REPORT = REPORTS_DIR / "report.md"


def slugify(text: str, *, max_len: int = 80) -> str:
    """Turn a title/question into a kebab-case filename stem."""
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return (text or "report")[:max_len].rstrip("-")


def title_from_report(path: Path) -> str | None:
    """Read the first markdown H1 as the report title, if present."""
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                return stripped[2:].strip() or None
    except OSError:
        return None
    return None


def ensure_reports_dir() -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return REPORTS_DIR


def clear_staging() -> None:
    if STAGING_REPORT.exists():
        STAGING_REPORT.unlink()


def finalize_local_report(
    question: str,
    staging_path: Path = STAGING_REPORT,
) -> Path:
    """Rename staging /report.md → reports/<hash>-<slug>.md."""
    if not staging_path.is_file():
        raise FileNotFoundError(
            f"Agent did not write {staging_path}. Expected /report.md."
        )

    title = title_from_report(staging_path) or question
    filename = f"{uuid.uuid4().hex[:8]}-{slugify(title)}.md"
    final_path = REPORTS_DIR / filename
    shutil.move(str(staging_path), str(final_path))
    return final_path
