"""Smoke test: fetch API keys from AWS Secrets Manager."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from helpers.config import get_aws_region, load_env  # noqa: E402
from helpers.secrets import fetch_secret_dict, get_secret_id, load_secrets  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    load_env()

    parser = argparse.ArgumentParser(description="Test Secrets Manager access")
    parser.add_argument("--secret-id", default=None)
    parser.add_argument("--region", default=None)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Also write known keys into the process environment",
    )
    args = parser.parse_args(argv)

    secret_id = get_secret_id(args.secret_id)
    if not secret_id:
        print(
            "error: set SECRETS_MANAGER_SECRET_ID or pass --secret-id",
            file=sys.stderr,
        )
        return 1

    region = args.region or get_aws_region()
    try:
        data = fetch_secret_dict(secret_id, region=region)
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"secret: {secret_id}")
    print(f"region: {region}")
    print(f"keys:   {', '.join(sorted(data.keys()))}")
    for key, value in sorted(data.items()):
        text = str(value)
        preview = f"{text[:4]}…{text[-4:]}" if len(text) > 10 else "***"
        print(f"  {key}={preview} (len={len(text)})")

    if args.apply:
        applied = load_secrets(secret_id, overwrite=True, region=region)
        print(f"applied to env: {', '.join(applied) or '(none)'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
