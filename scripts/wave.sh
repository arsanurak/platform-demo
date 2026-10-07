#!/usr/bin/env bash
# `make wave-N`: bring Wave N up on the new cluster through Argo CD.
#   1. refuse unless every earlier Wave is already healthy on new, so an App
#      never arrives before an App it calls (see gitops/waves.toml)
#   2. apply gitops/waves/wave-N/applicationset.yaml to new's Argo CD, tracking
#      GIT_REVISION (default main, as `make up` does) instead of the file's main
#   3. wait until Argo CD reports every App in the Wave Healthy
# The old copies keep serving; switching routing is `make cutover`'s job.
# Needs the clusters from `make up`. Safe to run again.
set -euo pipefail

wave="${1:?usage: wave.sh N}"
repo_root="$(cd "$(dirname "$0")/.." && pwd)"
waves_dir="$repo_root/gitops/waves"
kubeconfig="$repo_root/build/kubeconfig"
revision="${GIT_REVISION:-main}"

if ! [[ "$wave" =~ ^[1-9][0-9]*$ ]] || [ ! -f "$waves_dir/wave-$wave/applicationset.yaml" ]; then
  echo "No wave '$wave'. Waves: $(ls "$waves_dir" | tr '\n' ' ')" >&2
  exit 2
fi

new() { kubectl --kubeconfig "$kubeconfig" --context kind-new "$@"; }
apps_in() { sed -n 's/^ *- app: //p' "$waves_dir/wave-$1/applicationset.yaml"; }

for ((earlier = 1; earlier < wave; earlier++)); do
  for app in $(apps_in "$earlier"); do
    health="$(new -n argocd get application "$app" -o jsonpath='{.status.health.status}' 2>/dev/null || true)"
    if [ "$health" != "Healthy" ]; then
      echo "Wave $earlier's $app is not healthy on new (${health:-missing}). Run make wave-$earlier first." >&2
      exit 1
    fi
  done
done

echo "==> wave $wave: applying its ApplicationSet to new (tracking $revision)"
sed "s|^\( *targetRevision:\) main\$|\1 $revision|" "$waves_dir/wave-$wave/applicationset.yaml" | new apply -f -

for app in $(apps_in "$wave"); do
  echo "==> waiting for $app to be healthy on new"
  for _ in $(seq 60); do
    new -n argocd get application "$app" >/dev/null 2>&1 && break
    sleep 5
  done
  new -n argocd wait "application/$app" --for=jsonpath='{.status.health.status}'=Healthy --timeout=10m
done
echo "Wave $wave is healthy on new: $(apps_in "$wave" | tr '\n' ' ')"
