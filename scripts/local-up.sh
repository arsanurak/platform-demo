#!/usr/bin/env bash
# `make up`: bring up the local demo. Needs Docker, kind, kubectl and Terraform.
#   1. stage 1 (iac/local/clusters): the old and new kind clusters
#   2. cloud-provider-kind, which gives each cluster's Gateway an address
#   3. stage 2 (iac/local/argocd): Argo CD and the root app on each cluster
#   4. wait until Argo CD has synced app01-app06 on old, then call app01 and
#      app05 (which calls app04) through the gateway
# Safe to run again: every step converges on what is already there.
set -euo pipefail

CPK_IMAGE="registry.k8s.io/cloud-provider-kind/cloud-controller-manager:v0.12.0@sha256:1b97632e5dfec8f83c7e970cf18cedb9e6b707e272011d712cabf6ab59d323c9"
CPK_CONTAINER="platform-demo-cloud-provider-kind"

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
kubeconfig="$repo_root/build/kubeconfig"
revision="${GIT_REVISION:-main}"
mkdir -p "$repo_root/build"

echo "==> stage 1: kind clusters old and new"
terraform -chdir="$repo_root/iac/local/clusters" init -input=false >/dev/null
# One cluster at a time: kind locks the shared kubeconfig and fails, rather
# than waits, when the other cluster holds the lock.
terraform -chdir="$repo_root/iac/local/clusters" apply -input=false -auto-approve -parallelism=1 \
  -var "kubeconfig_path=$kubeconfig"

echo "==> cloud-provider-kind"
if [ -z "$(docker ps -q --filter "name=^${CPK_CONTAINER}$")" ]; then
  docker rm -f "$CPK_CONTAINER" >/dev/null 2>&1 || true
  docker run -d --name "$CPK_CONTAINER" --network host \
    -v /var/run/docker.sock:/var/run/docker.sock "$CPK_IMAGE" >/dev/null
fi

echo "==> stage 2: Argo CD and the root app on both clusters (tracking $revision)"
terraform -chdir="$repo_root/iac/local/argocd" init -input=false >/dev/null
terraform -chdir="$repo_root/iac/local/argocd" apply -input=false -auto-approve \
  -var "kubeconfig_path=$kubeconfig" -var "git_revision=$revision"

old() { kubectl --kubeconfig "$kubeconfig" --context kind-old "$@"; }

apps="$(sed -n 's/^\[apps\.\(app[0-9]*\)\]$/\1/p' "$repo_root/gitops/waves.toml")"
for app in $apps; do
  echo "==> waiting for Argo CD to sync $app on old"
  for _ in $(seq 60); do
    old -n argocd get application "$app" >/dev/null 2>&1 && break
    sleep 5
  done
  old -n argocd wait "application/$app" --for=jsonpath='{.status.health.status}'=Healthy --timeout=10m
done
old -n gateway wait gateway/web --for=condition=Programmed --timeout=5m

address="$(old -n gateway get gateway web -o jsonpath='{.status.addresses[0].value}')"
echo "==> app01 through the old cluster's gateway at $address"
curl -fsS --retry 10 --retry-all-errors --retry-delay 3 -H "Host: app01.example.com" "http://$address/"
echo
echo "==> app05 calling app04 (POST /api/echo is forwarded to app04's /echo)"
curl -fsS --retry 10 --retry-all-errors --retry-delay 3 -H "Host: app05.example.com" -d "hello from app05" "http://$address/api/echo"
echo
echo "Up. Use KUBECONFIG=$kubeconfig with the kind-old and kind-new contexts."
