"""SQS worker: poll queue → run research → ack message."""

from __future__ import annotations

import argparse
import sys
import time

from helpers.config import ENV_PATH, get_model, load_settings, missing_keys
from helpers.events import put_research_event
from helpers.jobs import STATUS_COMPLETED, get_job
from helpers.observability import log, put_metric
from helpers.queue import delete_message, receive_job
from helpers.secrets import get_secret_id
from src.agent import run


def process_one(*, visibility_timeout: int = 300) -> bool:
    """
    Receive and process at most one job.

    Returns True if a message was handled (success, skip, or failed-after-mark).
    Returns False if the queue was empty.
    """
    msg = receive_job(
        wait_seconds=20,
        visibility_timeout=visibility_timeout,
    )
    if msg is None:
        return False

    log(
        "job_received",
        job_id=msg.job_id,
        message_id=msg.message_id,
        attempt=msg.receive_count,
    )
    put_metric("JobsReceived", dimensions={"Service": "worker"})

    existing = get_job(msg.job_id)
    if existing and existing.get("status") == STATUS_COMPLETED:
        delete_message(msg.receipt_handle)
        log("job_skipped_completed", job_id=msg.job_id)
        put_metric("JobsSkipped", dimensions={"Service": "worker"})
        return True

    try:
        result = run(
            msg.question,
            track_job=True,
            job_id=msg.job_id,
            upload=True,
            keep_local=False,
        )
        delete_message(msg.receipt_handle)
        event_id = put_research_event(
            "ResearchCompleted",
            {
                "job_id": result.job_id,
                "question": msg.question,
                "s3_uri": result.s3_uri,
                "status": "COMPLETED",
            },
        )
        log(
            "job_completed",
            job_id=result.job_id,
            s3_uri=result.s3_uri,
            event_id=event_id,
        )
        put_metric("JobsCompleted", dimensions={"Service": "worker"})
        return True
    except Exception as exc:  # noqa: BLE001
        # Do NOT delete: visibility timeout → retry → eventually DLQ
        event_id = put_research_event(
            "ResearchFailed",
            {
                "job_id": msg.job_id,
                "question": msg.question,
                "status": "FAILED",
                "error": str(exc)[:500],
                "attempt": msg.receive_count,
            },
        )
        log(
            "job_failed",
            job_id=msg.job_id,
            error=str(exc),
            attempt=msg.receive_count,
            event_id=event_id,
        )
        put_metric("JobsFailed", dimensions={"Service": "worker"})
        return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deep research SQS worker")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process at most one message then exit",
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
    parser.add_argument(
        "--visibility-timeout",
        type=int,
        default=300,
        help="SQS visibility timeout seconds (default 300)",
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

    model = get_model()
    missing = missing_keys(model)
    if missing:
        print(f"error: missing {', '.join(missing)}", file=sys.stderr)
        if get_secret_id() and not args.no_secrets:
            print(
                f"Try --secrets-overwrite, or update the secret / {ENV_PATH}.",
                file=sys.stderr,
            )
        return 1

    log("worker_started")
    put_metric("WorkerStarted", dimensions={"Service": "worker"})

    if args.once:
        handled = process_one(visibility_timeout=args.visibility_timeout)
        if not handled:
            log("queue_empty")
        return 0

    while True:
        try:
            handled = process_one(visibility_timeout=args.visibility_timeout)
        except Exception as exc:  # noqa: BLE001
            # Transient SQS/DynamoDB/EventBridge error: keep the worker alive.
            log("worker_loop_error", error=str(exc))
            put_metric("WorkerLoopErrors", dimensions={"Service": "worker"})
            time.sleep(5)
            continue
        if not handled:
            time.sleep(1)


if __name__ == "__main__":
    raise SystemExit(main())
