#!/usr/bin/env bash
# Render the Argo CD and root-app charts with the values stage 2 installs, at
# the chart versions stage 2 pins (iac/local/argocd/charts.json), for each
# cluster, and validate the output with kubeconform. Needs no cluster.
# Usage: helm-template.sh STAGE2_DIR OUT_DIR
set -euo pipefail

stage2="${1:?usage: helm-template.sh STAGE2_DIR OUT_DIR}"
out="${2:?usage: helm-template.sh STAGE2_DIR OUT_DIR}"
here="$(cd "$(dirname "$0")" && pwd)"
repo_root="$(cd "$here/.." && pwd)"
helm="${HELM:-$repo_root/.tools/bin/helm}"
python="${PYTHON:-python3}"
mkdir -p "$out"

chart() { "$python" -c 'import json, sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' "$stage2/charts.json" "$1"; }
repository="$(chart repository)"

echo "==> helm template argo-cd $(chart argo-cd)"
"$helm" template argocd argo-cd --repo "$repository" --version "$(chart argo-cd)" \
  --namespace argocd -f "$stage2/values/argo-cd.yaml" >"$out/argo-cd.yaml"

for cluster in old new; do
  echo "==> helm template argocd-apps $(chart argocd-apps) for $cluster"
  "$helm" template root-app argocd-apps --repo "$repository" --version "$(chart argocd-apps)" \
    --namespace argocd -f "$stage2/values/argocd-apps.yaml" \
    --set "applications.root.source.path=gitops/bootstrap/$cluster" >"$out/root-app-$cluster.yaml"
done

# The pinned Kubernetes schemas have no CustomResourceDefinition schema. The
# chart's CRDs are upstream's own; everything else must validate.
echo "==> kubeconform: rendered charts"
"$here/kubeconform.sh" -skip CustomResourceDefinition "$out"
