#!/usr/bin/env bash
# Create or update this repo's triage labels. Safe to run more than once.
# Usage: scripts/create-labels.sh [owner/repo]   (default: the repo of the current clone)
set -euo pipefail

repo_args=()
if [ $# -gt 0 ]; then
  repo_args=(--repo "$1")
fi

# name|color|description
labels=(
  "needs-triage|d4c5f9|The maintainer still needs to evaluate this"
  "needs-info|fbca04|Waiting on the reporter for more detail"
  "ready-for-agent|0e8a16|Fully specified, ready for an agent to do"
  "ready-for-human|1d76db|Needs a human to do it"
  "wontfix|cccccc|Will not be actioned"
)

for label in "${labels[@]}"; do
  IFS='|' read -r name color description <<<"$label"
  gh label create "$name" --color "$color" --description "$description" --force "${repo_args[@]}"
done
