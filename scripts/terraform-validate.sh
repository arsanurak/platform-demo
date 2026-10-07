#!/usr/bin/env bash
# Run `terraform validate` in every folder under iac/ that holds .tf files.
# Needs no cloud credentials: providers are installed, backends are skipped.
set -euo pipefail

root="${1:-iac}"
mapfile -t dirs < <(find "$root" -name '*.tf' -not -path '*/.terraform/*' -printf '%h\n' | sort -u)

if [ "${#dirs[@]}" -eq 0 ]; then
  echo "No Terraform under $root yet, nothing to validate."
  exit 0
fi

for dir in "${dirs[@]}"; do
  echo "==> terraform validate: $dir"
  terraform -chdir="$dir" init -backend=false -input=false -no-color >/dev/null
  terraform -chdir="$dir" validate -no-color
done
