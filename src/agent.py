"""Deep research agent: question → Gemini/Tavily → report → S3 + job state."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend

from helpers.config import (
    DEFAULT_MODEL,
    ENV_PATH,
    get_model,
    load_settings,
    missing_keys,
)
from helpers.jobs import create_job, mark_completed, mark_failed, mark_running
from helpers.reports import (
    REPORTS_DIR,
    clear_staging,
    ensure_reports_dir,
    finalize_local_report,
)
from helpers.s3 import upload_report
from helpers.secrets import get_secret_id
from tools.search import internet_search

SYSTEM_PROMPT = """You are a research assistant.

Use the internet_search tool to gather evidence before answering.
Prefer primary sources and recent material when available.

Write a structured markdown report to /report.md with:
- an H1 title
- summary
- key findings
- citations (URLs)

When done, briefly confirm that /report.md was written.
"""


@dataclass
class ResearchResult:
    answer: str
    job_id: str | None
    local_path: Path | None
    s3_uri: str | None


def build_agent(model: str | None = None):
    """Create the Deep Agent with search + local filesystem backend."""
    ensure_reports_dir()
    return create_deep_agent(
        model=get_model(model),
        tools=[internet_search],
        system_prompt=SYSTEM_PROMPT,
        backend=FilesystemBackend(
            root_dir=str(REPORTS_DIR),
            virtual_mode=True,
        ),
    )


def _message_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            else:
                text = getattr(block, "text", None)
                if text:
                    parts.append(str(text))
        return "\n".join(p for p in parts if p)
    return str(content)


def run(
    question: str,
    model: str | None = None,
    *,
    upload: bool = True,
    keep_local: bool = False,
    track_job: bool = True,
    job_id: str | None = None,
) -> ResearchResult:
    """question → Deep Agent → local staging → S3 + DynamoDB job state."""
    clear_staging()

    tracked_id: str | None = None
    if track_job:
        if job_id:
            # Existing queued job (worker path): QUEUED → RUNNING
            mark_running(job_id)
            tracked_id = job_id
        else:
            tracked_id = create_job(question)

    try:
        result = build_agent(model=model).invoke(
            {"messages": [{"role": "user", "content": question}]},
        )
        answer = _message_text(result["messages"][-1].content)
        local_path = finalize_local_report(question)

        s3_uri = None
        if upload:
            s3_uri = upload_report(local_path, question=question)
            if not keep_local:
                local_path.unlink(missing_ok=True)
                local_path = None

        if tracked_id:
            mark_completed(tracked_id, s3_uri=s3_uri)

        return ResearchResult(
            answer=answer,
            job_id=tracked_id,
            local_path=local_path,
            s3_uri=s3_uri,
        )
    except Exception as exc:
        if tracked_id:
            mark_failed(tracked_id, str(exc))
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Deep research agent → report → S3 + DynamoDB",
    )
    parser.add_argument("question", help="Research question")
    parser.add_argument(
        "--model",
        default=None,
        help=f"Model string (default: .env MODEL or {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--job-id",
        default=None,
        help="Optional job id (default: auto-generated)",
    )
    parser.add_argument(
        "--no-job",
        action="store_true",
        help="Skip DynamoDB job tracking",
    )
    parser.add_argument(
        "--no-upload",
        action="store_true",
        help="Skip S3; keep report under reports/",
    )
    parser.add_argument(
        "--keep-local",
        action="store_true",
        help="Keep local copy after S3 upload",
    )
    parser.add_argument(
        "--no-secrets",
        action="store_true",
        help="Use .env only (skip Secrets Manager)",
    )
    parser.add_argument(
        "--secrets-overwrite",
        action="store_true",
        help="Prefer Secrets Manager over existing .env keys",
    )
    args = parser.parse_args(argv)

    try:
        load_settings(
            secrets=not args.no_secrets,
            secrets_overwrite=args.secrets_overwrite,
        )
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    model = get_model(args.model)
    missing = missing_keys(model)
    if missing:
        print(f"error: missing {', '.join(missing)}", file=sys.stderr)
        if get_secret_id() and not args.no_secrets:
            print(
                "Secret loaded but keys missing or blocked by .env. "
                f"Try --secrets-overwrite, or update the secret / {ENV_PATH}.",
                file=sys.stderr,
            )
        else:
            print(
                f"Set SECRETS_MANAGER_SECRET_ID or keys in {ENV_PATH}.",
                file=sys.stderr,
            )
        return 1

    try:
        result = run(
            args.question,
            model=model,
            upload=not args.no_upload,
            keep_local=args.keep_local,
            track_job=not args.no_job,
            job_id=args.job_id,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(result.answer)
    if result.job_id:
        print(f"\njob:   {result.job_id}")
    if result.local_path:
        print(f"local: {result.local_path}")
    if result.s3_uri:
        print(f"s3:    {result.s3_uri}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
