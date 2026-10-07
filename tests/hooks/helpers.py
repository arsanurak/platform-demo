"""Run a hook the way the agent harness does: JSON on stdin, verdict in the exit code."""

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"

BLOCKED = 2
ALLOWED = 0


def run_hook(hook_name, tool_name, tool_input):
    """Return (exit_code, stderr) for one PreToolUse event."""
    hook = HOOKS_DIR / hook_name
    # Python exits 2 when a script is missing, which would look like a block.
    if not hook.is_file():
        raise FileNotFoundError(f"hook not found: {hook}")
    event = {
        "hook_event_name": "PreToolUse",
        "tool_name": tool_name,
        "tool_input": tool_input,
    }
    result = subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.returncode, result.stderr


def run_hook_raw(hook_name, stdin_text):
    """Return (exit_code, stderr) for arbitrary stdin, e.g. malformed JSON."""
    hook = HOOKS_DIR / hook_name
    if not hook.is_file():
        raise FileNotFoundError(f"hook not found: {hook}")
    result = subprocess.run(
        [sys.executable, str(hook)], input=stdin_text, capture_output=True, text=True, timeout=10
    )
    return result.returncode, result.stderr
