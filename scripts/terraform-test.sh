#!/usr/bin/env bash
# Run `terraform test` in every folder under iac/ that has a tests/ folder.
# Tests use mock providers, so they need no cloud credentials.
set -euo pipefail

root="${1:-iac}"
mapfile -t dirs < <(find "$root" -name '*.tftest.hcl' -path '*/tests/*' -not -path '*/.terraform/*' -printf '%h\n' | xargs -r -n1 dirname | sort -u)

if [ "${#dirs[@]}" -eq 0 ]; then
  echo "No Terraform tests under $root yet, nothing to run."
  exit 0
fi

for dir in "${dirs[@]}"; do
  echo "==> terraform test: $dir"
  terraform -chdir="$dir" init -backend=false -input=false -no-color >/dev/null
  terraform -chdir="$dir" test -no-color
done
