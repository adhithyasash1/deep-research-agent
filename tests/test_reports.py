"""Unit tests for report naming helpers."""

from __future__ import annotations

from pathlib import Path

from helpers.reports import finalize_local_report, slugify, title_from_report
from helpers.s3 import build_object_key


def test_slugify_basic():
    assert slugify("What is LangGraph?") == "what-is-langgraph"


def test_slugify_empty():
    assert slugify("???") == "report"


def test_title_from_report(tmp_path: Path):
    path = tmp_path / "report.md"
    path.write_text("# Hello World\n\nBody\n", encoding="utf-8")
    assert title_from_report(path) == "Hello World"


def test_finalize_local_report(tmp_path: Path, monkeypatch):
    from helpers import reports as reports_mod

    monkeypatch.setattr(reports_mod, "REPORTS_DIR", tmp_path)
    staging = tmp_path / "report.md"
    staging.write_text("# Coding Agents\n\nNotes\n", encoding="utf-8")

    final = finalize_local_report("fallback question", staging_path=staging)
    assert final.parent == tmp_path
    assert final.name.endswith("-coding-agents.md")
    assert not staging.exists()
    assert final.exists()


def test_build_object_key(tmp_path: Path):
    path = tmp_path / "report.md"
    path.write_text("# Evaluating Agents\n", encoding="utf-8")
    key = build_object_key(path)
    assert key.startswith("reports/")
    assert key.endswith("-evaluating-agents.md")
