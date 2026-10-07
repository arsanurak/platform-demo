#!/usr/bin/env python3
"""Cutover and Rollback for one Wave: `make cutover WAVE=N` and `make rollback WAVE=N`.

Usage: cutover.py {cutover,rollback} WAVE [--confirm]

Clients reach every App through the old cluster's Gateway. Cutover, per App in the Wave:
  1. adds <app>-via-new on old: a Service with no selector whose EndpointSlice is the
     new cluster's Gateway address, so the Host header still picks the App on new
  2. points old's HTTPRoute at <app>-via-new (routing switches before anything stops)
  3. scales old's Deployment to zero; its definition stays, so Argo CD keeps it
Before the first change it writes the old replicas and backends to
build/cutover/wave-N.json (CUTOVER_STATE_DIR overrides the folder). Rollback replays
that file: scale old back up, wait until ready, point the HTTPRoute back, then delete
the file. Old's Argo CD ignores replicas and HTTPRoute rules (see
gitops/bootstrap/old/applicationset.yaml), so it doesn't undo either command.

Both print their plan first and change nothing without --confirm (CONFIRM=1).
Both are safe to run again: a step already in its target state is skipped.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WAVES_DIR = REPO_ROOT / "gitops/waves"
KUBECONFIG = REPO_ROOT / "build/kubeconfig"


def kubectl(context, *args, stdin=None, check=True):
    result = subprocess.run(["kubectl", "--kubeconfig", str(KUBECONFIG), "--context", f"kind-{context}", *args],
                            input=stdin, capture_output=True, text=True)
    if check and result.returncode != 0:
        sys.exit(f"kubectl {' '.join(args)} failed: {result.stderr.strip()}")
    return result


def get(context, namespace, kind, name):
    result = kubectl(context, "-n", namespace, "get", kind, name, "-o", "json", check=False)
    return json.loads(result.stdout) if result.returncode == 0 else None


def apps_in(wave):
    applicationset = WAVES_DIR / f"wave-{wave}" / "applicationset.yaml"
    if not applicationset.is_file():
        waves = " ".join(sorted(p.name for p in WAVES_DIR.iterdir()))
        sys.exit(f"No wave '{wave}'. Waves: {waves}")
    return [line.split("- app:")[1].strip() for line in applicationset.read_text().splitlines() if "- app:" in line]


def backend_of(route):
    return route["spec"]["rules"][0]["backendRefs"][0]["name"]


def old_side(app):
    deployment = get("old", app, "deployment", app)
    route = get("old", app, "httproute", app)
    if deployment is None or route is None:
        sys.exit(f"{app} has no Deployment or HTTPRoute on old. Run make up first.")
    return deployment["spec"].get("replicas", 1), backend_of(route)


def via_new(app, address):
    """The Service on old that forwards to the new cluster's Gateway."""
    name = f"{app}-via-new"
    meta = {"name": name, "namespace": app, "labels": {"platform-demo/cutover": "true"}}
    return {"apiVersion": "v1", "kind": "List", "items": [
        {"apiVersion": "v1", "kind": "Service", "metadata": meta,
         "spec": {"ports": [{"name": "http", "port": 80, "targetPort": 80}]}},
        {"apiVersion": "discovery.k8s.io/v1", "kind": "EndpointSlice", "addressType": "IPv4",
         "metadata": {**meta, "labels": {**meta["labels"], "kubernetes.io/service-name": name}},
         "ports": [{"name": "http", "port": 80, "protocol": "TCP"}],
         "endpoints": [{"addresses": [address]}]},
    ]}


def set_backend(app, name):
    patch = [{"op": "replace", "path": "/spec/rules/0/backendRefs/0/name", "value": name}]
    kubectl("old", "-n", app, "patch", "httproute", app, "--type", "json", "-p", json.dumps(patch))


def new_gateway_address():
    gateway = get("new", "gateway", "gateway", "web") or {}
    addresses = gateway.get("status", {}).get("addresses", [])
    if not addresses:
        sys.exit("Can't find the new cluster's gateway address. Run make up first.")
    return addresses[0]["value"]


def cutover(wave, apps, state_file, confirm):
    for app in apps:
        application = get("new", "argocd", "application", app) or {}
        health = application.get("status", {}).get("health", {}).get("status", "missing")
        if health != "Healthy":
            sys.exit(f"{app} is not healthy on new ({health}). Run make wave-{wave} and make parity WAVE={wave} first.")
    address = new_gateway_address()
    # Recorded state wins over what old shows now: after a cutover old shows 0 replicas.
    recorded = json.loads(state_file.read_text())["apps"] if state_file.exists() else {}
    current = {app: old_side(app) for app in apps}

    print(f"Cutover plan for wave {wave} ({' '.join(apps)}), through old's gateway:")
    steps = []
    for app in apps:
        replicas, backend = current[app]
        target = f"{app}-via-new"
        if backend == target:
            print(f"  {app}: route    already points at {target}")
        else:
            print(f"  {app}: route    old HTTPRoute {app}/{app}: backend {backend} -> {target} (new gateway {address})")
            steps.append(("route", app))
        if replicas == 0:
            print(f"  {app}: scale    old Deployment {app}/{app} already at 0 replicas")
        else:
            print(f"  {app}: scale    old Deployment {app}/{app}: {replicas} -> 0 replicas (definition kept)")
            steps.append(("scale", app))
    print(f"  state:       {state_file} records old's replicas and backends for make rollback WAVE={wave}")
    if not steps:
        print(f"Wave {wave} is already cut over. Nothing to do.")
        return
    if not confirm:
        print(f"Plan only: nothing changed. Run make cutover WAVE={wave} CONFIRM=1 to apply it.")
        return

    if not recorded:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        record = {app: {"replicas": current[app][0], "backend": current[app][1]} for app in apps}
        state_file.write_text(json.dumps({"wave": wave, "apps": record}, indent=2) + "\n")
        print(f"==> recorded rollback state in {state_file}")
    for step, app in steps:
        if step == "route":
            print(f"==> {app}: routing old's gateway to new")
            kubectl("old", "apply", "-f", "-", stdin=json.dumps(via_new(app, address)))
            set_backend(app, f"{app}-via-new")
    for step, app in steps:
        if step == "scale":
            print(f"==> {app}: scaling old to 0 replicas")
            kubectl("old", "-n", app, "scale", "deployment", app, "--replicas=0")
    print(f"Wave {wave} is cut over: old's gateway sends {' '.join(apps)} to new. Undo with make rollback WAVE={wave}.")


def rollback(wave, apps, state_file, confirm):
    if not state_file.exists():
        print(f"No rollback state for wave {wave} ({state_file}). Nothing to roll back.")
        return
    recorded = json.loads(state_file.read_text())["apps"]
    print(f"Rollback plan for wave {wave} ({' '.join(apps)}), replaying {state_file}:")
    steps = []
    for app in apps:
        replicas, backend = old_side(app)
        want = recorded[app]
        if replicas == want["replicas"]:
            print(f"  {app}: scale    old Deployment {app}/{app} already at {replicas} replicas")
        else:
            print(f"  {app}: scale    old Deployment {app}/{app}: {replicas} -> {want['replicas']} replicas, then wait until ready")
            steps.append(("scale", app))
        if backend == want["backend"]:
            print(f"  {app}: route    already points at {backend}")
        else:
            print(f"  {app}: route    old HTTPRoute {app}/{app}: backend {backend} -> {want['backend']}")
            steps.append(("route", app))
    print(f"  state:       {state_file} is deleted once old serves again")
    if not confirm:
        print(f"Plan only: nothing changed. Run make rollback WAVE={wave} CONFIRM=1 to apply it.")
        return

    for step, app in steps:
        if step == "scale":
            print(f"==> {app}: scaling old back to {recorded[app]['replicas']} replicas")
            kubectl("old", "-n", app, "scale", "deployment", app, f"--replicas={recorded[app]['replicas']}")
    for step, app in steps:
        if step == "scale":
            kubectl("old", "-n", app, "rollout", "status", f"deployment/{app}", "--timeout=5m")
    for step, app in steps:
        if step == "route":
            print(f"==> {app}: routing old's gateway back to old")
            set_backend(app, recorded[app]["backend"])
    state_file.unlink()
    print(f"Wave {wave} is rolled back: old serves {' '.join(apps)} again.")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["cutover", "rollback"])
    parser.add_argument("wave")
    parser.add_argument("--confirm", action="store_true", help="act on the plan instead of only printing it")
    args = parser.parse_args()
    apps = apps_in(args.wave)
    state_dir = Path(os.environ.get("CUTOVER_STATE_DIR") or REPO_ROOT / "build/cutover")
    state_file = state_dir / f"wave-{args.wave}.json"
    {"cutover": cutover, "rollback": rollback}[args.command](args.wave, apps, state_file, args.confirm)


if __name__ == "__main__":
    main()
