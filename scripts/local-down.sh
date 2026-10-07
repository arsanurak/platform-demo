#!/usr/bin/env bash
# `make down`: remove everything `make up` created. Deleting the clusters
# removes Argo CD and the apps with them, so stage 2 is not destroyed
# separately; its local state is dropped instead.
set -euo pipefail

CPK_CONTAINER="platform-demo-cloud-provider-kind"

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
kubeconfig="$repo_root/build/kubeconfig"

echo "==> stage 1: delete the kind clusters"
terraform -chdir="$repo_root/iac/local/clusters" init -input=false >/dev/null
# One cluster at a time: kind locks the shared kubeconfig and fails, rather
# than waits, when the other cluster holds the lock.
terraform -chdir="$repo_root/iac/local/clusters" destroy -input=false -auto-approve -parallelism=1 \
  -var "kubeconfig_path=$kubeconfig"
rm -f "$repo_root"/iac/local/argocd/terraform.tfstate "$repo_root"/iac/local/argocd/terraform.tfstate.backup

echo "==> cloud-provider-kind and the gateway containers it started"
docker rm -f "$CPK_CONTAINER" >/dev/null 2>&1 || true
for cluster in old new; do
  ids="$(docker ps -aq --filter "label=io.x-k8s.cloud-provider-kind.cluster=$cluster")"
  if [ -n "$ids" ]; then
    # shellcheck disable=SC2086 # one id per word
    docker rm -f $ids >/dev/null
  fi
done

rm -f "$kubeconfig"
echo "Down. No demo clusters or containers are left."
