"""Smoke test: upload a local markdown file to S3."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from botocore.exceptions import BotoCoreError, ClientError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from helpers.config import load_env  # noqa: E402
from helpers.s3 import upload_report  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    load_env()

    parser = argparse.ArgumentParser(description="Upload a local file to S3")
    parser.add_argument(
        "--file",
        type=Path,
        default=None,
        help="Local markdown file (default: tiny temp sample)",
    )
    parser.add_argument("--bucket", default=None)
    parser.add_argument("--key", default=None)
    parser.add_argument("--region", default=None)
    args = parser.parse_args(argv)

    tmp_path: Path | None = None
    local = args.file
    if local is None:
        tmp = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".md",
            prefix="s3-smoke-",
            delete=False,
            encoding="utf-8",
        )
        tmp.write("# S3 smoke test\n\nUploaded by scripts/test_s3.py\n")
        tmp.close()
        tmp_path = Path(tmp.name)
        local = tmp_path

    try:
        uri = upload_report(
            local.resolve(),
            bucket=args.bucket,
            region=args.region,
            key=args.key,
        )
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "ClientError")
        message = exc.response.get("Error", {}).get("Message", str(exc))
        print(f"error: {code}: {message}", file=sys.stderr)
        return 1
    except BotoCoreError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)

    print(f"uploaded → {uri}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
