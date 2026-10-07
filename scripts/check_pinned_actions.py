#!/usr/bin/env python3
"""Fail if any GitHub Action is not pinned to a full commit SHA.

Usage: check_pinned_actions.py [WORKFLOW_DIR ...]   (default: .github/workflows)

Every `uses:` must be one of:
  - a local path (./...)
  - a Docker image pinned by digest (docker://image@sha256:...)
  - owner/repo[/path]@<40-hex SHA> followed by a `# vX.Y.Z` comment
"""

import re
import sys
from pathlib import Path

USES = re.compile(r"""^\s*(?:-\s*)?uses:\s*['"]?([^'"\s#]+)['"]?\s*(#.*)?$""")
SHA_PIN = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")
DIGEST_PIN = re.compile(r"^docker://[^@]+@sha256:[0-9a-f]{64}$")
VERSION_COMMENT = re.compile(r"^#\s*v\d+(\.\d+)*\S*\s*$")


def problem_with(ref, comment):
    if ref.startswith("./") or DIGEST_PIN.match(ref):
        return None
    if not SHA_PIN.match(ref):
        return "not pinned to a full commit SHA"
    if not comment or not VERSION_COMMENT.match(comment.strip()):
        return "missing a '# vX.Y.Z' comment"
    return None


def workflow_files(folders):
    for folder in folders:
        for path in sorted(Path(folder).rglob("*")):
            if path.suffix in (".yml", ".yaml"):
                yield path


def main(argv):
    folders = argv or [".github/workflows"]
    problems = []
    for path in workflow_files(folders):
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            match = USES.match(line)
            if not match:
                continue
            problem = problem_with(match.group(1), match.group(2))
            if problem:
                problems.append(f"{path}:{number}: {match.group(1)} is {problem}")
    for problem in problems:
        print(problem)
    if problems:
        return 1
    print("Every action is pinned to a commit SHA.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
