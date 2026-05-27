#!/usr/bin/env python3
"""Send a test email using the project's email helper.

Usage:
  python scripts/send_test_email.py --to you@example.com --subject "Test" --body "Hello"

If `--to` is omitted, uses $TEST_EMAIL or falls back to localhost user.
"""
import os
import sys
from pathlib import Path
import argparse

# Ensure project root is on sys.path so `lib` imports work when run from scripts/
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lib.email import send_email


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--to", help="Recipient email address")
    p.add_argument("--subject", default="ChatBGSU test email")
    p.add_argument("--body", default="This is a test email from ChatBGSU.")
    args = p.parse_args()

    to_addr = args.to or os.getenv("TEST_EMAIL") or f"{os.getenv('USER','user')}@localhost"

    ok, msg = send_email(to_addr, args.subject, args.body)
    if ok:
        print(f"OK: Sent to {to_addr}: {msg}")
        return 0
    else:
        print(f"ERROR: {msg}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
