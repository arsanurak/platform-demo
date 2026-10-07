#!/usr/bin/env python3
"""Secret guard: a PreToolUse hook that blocks secret-shaped values.

Reads one PreToolUse event as JSON on stdin. Exits 2 with a reason on stderr
to block the tool call, or 0 to leave the decision to the normal permission flow.
"""

import json
import re
import shlex
import sys
from pathlib import PurePosixPath

SECRET_PATTERNS = {
    "AWS access key ID": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "private key": re.compile(r"-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----"),
    "GitHub token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,})"),
    "Slack token": re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    "API key": re.compile(r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{32,}"),
}

# A quoted value assigned to a credential-like name, e.g. db_password = "...".
CREDENTIAL_ASSIGNMENT = re.compile(
    r"""[A-Za-z0-9_-]*(?:password|passwd|secret|token|api_?key|access_?key)[A-Za-z0-9_-]*"""
    r"""["']?\s*[:=]\s*(["'])([^"'\s]{8,})\1""",
    re.IGNORECASE,
)
PLACEHOLDER_WORDS = ("example", "placeholder", "changeme", "redacted", "dummy", "xxxx")

SECRET_FILE_NAMES = {"id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", "credentials", ".netrc", ".pgpass"}
SECRET_FILE_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".tfstate", ".tfstate.backup")
SAFE_ENV_SUFFIXES = (".example", ".sample", ".template")


def is_placeholder(value):
    lowered = value.lower()
    return value[0] in "<${" or any(word in lowered for word in PLACEHOLDER_WORDS)


def find_secret(text):
    for name, pattern in SECRET_PATTERNS.items():
        if pattern.search(text):
            return name
    for match in CREDENTIAL_ASSIGNMENT.finditer(text):
        if not is_placeholder(match.group(2)):
            return "hardcoded credential"
    return None


def is_secret_file(path):
    name = PurePosixPath(path).name
    if name == ".env" or (name.startswith(".env.") and not name.endswith(SAFE_ENV_SUFFIXES)):
        return True
    return name in SECRET_FILE_NAMES or name.endswith(SECRET_FILE_SUFFIXES)


def words_of(command):
    try:
        return shlex.split(command)
    except ValueError:
        return command.split()


def secret_file_in(tool_name, tool_input):
    for key in ("file_path", "notebook_path", "path"):
        value = tool_input.get(key)
        if isinstance(value, str) and is_secret_file(value):
            return value
    if tool_name == "Bash":
        for word in words_of(tool_input.get("command", "")):
            if is_secret_file(word):
                return word
    return None


def texts_to_scan(tool_input):
    for key in ("content", "new_string", "command"):
        value = tool_input.get(key)
        if isinstance(value, str):
            yield value
    for edit in tool_input.get("edits") or []:
        if isinstance(edit, dict) and isinstance(edit.get("new_string"), str):
            yield edit["new_string"]


def main():
    try:
        event = json.load(sys.stdin)
        tool_input = event.get("tool_input") or {}
    except (ValueError, AttributeError):
        print("Secret guard: could not read the tool call, so it was blocked.", file=sys.stderr)
        return 2
    path = secret_file_in(event.get("tool_name", ""), tool_input)
    if path:
        print(
            f"Secret guard: blocked access to {path}, which usually holds secrets. "
            "Ask the human to handle this file.",
            file=sys.stderr,
        )
        return 2
    for text in texts_to_scan(tool_input):
        found = find_secret(text)
        if found:
            print(
                f"Secret guard: blocked a value that looks like a {found}. "
                "Use a placeholder and keep real secrets out of the repo.",
                file=sys.stderr,
            )
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
