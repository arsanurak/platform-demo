#!/usr/bin/env bash
# Render the guardrail policies to one JSON manifest: render-policies.sh OUT.json
# The policies module has no provider, so this `terraform plan` needs no
# credentials and creates nothing. It only evaluates the module's outputs.
set -euo pipefail

out="${1:?usage: render-policies.sh OUT.json}"
module="$(cd "$(dirname "$0")/../guardrails/policies" && pwd)"
plan="$(mktemp)"
trap 'rm -f "$plan"' EXIT

terraform -chdir="$module" init -backend=false -input=false -no-color >/dev/null
terraform -chdir="$module" plan -input=false -no-color -lock=false -out="$plan" >/dev/null
terraform -chdir="$module" show -json "$plan" |
  python3 -c 'import json, sys; json.dump(json.load(sys.stdin)["planned_values"]["outputs"]["manifest"]["value"], sys.stdout, indent=2)' >"$out"
echo "Rendered guardrails to $out"
