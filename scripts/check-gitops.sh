#!/usr/bin/env bash
# Validate every manifest under the GitOps folder, then prove the validator
# bites: each file in the known-bad folder must be rejected.
# Usage: check-gitops.sh GITOPS_DIR KNOWN_BAD_DIR
set -euo pipefail

gitops="${1:?usage: check-gitops.sh GITOPS_DIR KNOWN_BAD_DIR}"
known_bad="${2:?usage: check-gitops.sh GITOPS_DIR KNOWN_BAD_DIR}"
here="$(dirname "$0")"

echo "==> kubeconform: $gitops"
"$here/kubeconform.sh" "$gitops"

echo "==> kubeconform must reject every file in $known_bad"
failed=0
for file in "$known_bad"/*.yaml; do
  if "$here/kubeconform.sh" "$file" >/dev/null 2>&1; then
    echo "NOT REJECTED: $file" >&2
    failed=1
  else
    echo "rejected as expected: $file"
  fi
done
exit "$failed"
