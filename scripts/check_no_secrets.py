#!/usr/bin/env python3
"""Reject staged files that contain credentials or private runtime data."""

import argparse
import re
import subprocess
import sys
from pathlib import Path

FORBIDDEN_FILENAMES = {
    ".env",
    "profil.json",
    "n8n_workflow_job_hunter.json",
}
FORBIDDEN_PATTERNS = [
    re.compile(r"api\.telegram\.org/bot\d+:[A-Za-z0-9_-]+"),
    re.compile(r"AIza[0-9A-Za-z_-]{35}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?im)^(?:TELEGRAM_BOT_TOKEN|GEMINI_API_KEY|WORKER_API_TOKEN|N8N_ENCRYPTION_KEY|N8N_WEBHOOK_TOKEN)\s*=\s*(?!your_|generate_|example|change-me|AIzaSyYour)[^\s#]{8,}\s*$"),
]


def staged_paths():
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [Path(line) for line in result.stdout.splitlines() if line.strip()]


def inspect_path(path):
    if path.name in FORBIDDEN_FILENAMES or path.name.startswith("client_secret_"):
        return f"forbidden runtime file: {path}"

    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    for pattern in FORBIDDEN_PATTERNS:
        if pattern.search(content):
            return f"credential-like content detected: {path} ({pattern.pattern})"
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--staged", action="store_true", help="scan staged files")
    args = parser.parse_args()
    paths = staged_paths() if args.staged else [Path(path) for path in subprocess.check_output(["git", "ls-files"], text=True).splitlines()]

    findings = [finding for path in paths if (finding := inspect_path(path))]
    if findings:
        print("Commit blocked by secret guard:")
        print("\n".join(f"- {finding}" for finding in findings))
        return 1
    print(f"Secret guard passed for {len(paths)} staged file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())