#!/usr/bin/env python3
"""Compare each App on the old and new clusters: the parity check.

Usage: parity.py WAVE [--definition gitops/waves.toml]

Checks every App in waves 1..WAVE (the Apps on new so far). For each endpoint
in the definition's [parity] table it requests the App through each cluster's
Gateway (Host: <app>.example.com) and compares the HTTP status, the chosen
headers and the JSON shape: keys and types, never values. Prints one line per
check and a diff for each mismatch. Exits 1 on any difference, 2 on bad input.

The Gateway base URLs come from OLD_URL and NEW_URL, or from the kind-old and
kind-new clusters' `web` Gateway when unset.
"""
import argparse
import json
import os
import subprocess
import sys
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def gateway_url(cluster):
    env = os.environ.get(f"{cluster.upper()}_URL")
    if env:
        return env.rstrip("/")
    address = subprocess.run(
        ["kubectl", "--kubeconfig", str(REPO_ROOT / "build/kubeconfig"), "--context", f"kind-{cluster}",
         "-n", "gateway", "get", "gateway", "web", "-o", "jsonpath={.status.addresses[0].value}"],
        capture_output=True, text=True,
    )
    if address.returncode != 0 or not address.stdout.strip():
        sys.exit(f"Can't find the {cluster} cluster's gateway address. Run make up, or set {cluster.upper()}_URL.")
    return f"http://{address.stdout.strip()}"


def fetch(base, app, path):
    """Return (status, headers, body) for GET path on app, or an error string."""
    request = urllib.request.Request(base + path, headers={"Host": f"{app}.example.com"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, response.headers, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.headers, error.read()
    except (urllib.error.URLError, OSError) as error:
        return f"unreachable ({getattr(error, 'reason', error)})"


def type_name(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    return {str: "string", list: "array", dict: "object"}[type(value)]


def shape(value, path="$"):
    """Flatten a JSON value to {path: type}. An array's elements share one path, $.items[]."""
    shapes = {path: type_name(value)}
    if isinstance(value, dict):
        for key, child in value.items():
            shapes.update(shape(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for child in value:
            shapes.update(shape(child, f"{path}[]"))
    return shapes


def body_shape(body):
    try:
        return shape(json.loads(body))
    except ValueError:
        return {"$": "not JSON"}


def shape_differences(old, new):
    diffs = []
    for path in sorted(old.keys() | new.keys()):
        if path not in new:
            diffs.append(f"{path}: missing on new (old: {old[path]})")
        elif path not in old:
            diffs.append(f"{path}: only on new ({new[path]})")
        elif old[path] != new[path]:
            diffs.append(f"{path}: type old {old[path]}, new {new[path]}")
    return diffs


def differences(old, new, headers):
    """Return the list of readable differences between two responses."""
    if isinstance(old, str) or isinstance(new, str):
        return [f"request: old {old if isinstance(old, str) else 'answered'}, new {new if isinstance(new, str) else 'answered'}"]
    diffs = []
    if old[0] != new[0]:
        diffs.append(f"status: old {old[0]}, new {new[0]}")
    for name in headers:
        if old[1].get(name) != new[1].get(name):
            diffs.append(f"header {name}: old {old[1].get(name)!r}, new {new[1].get(name)!r}")
    diffs += shape_differences(body_shape(old[2]), body_shape(new[2]))
    return diffs


def main():
    parser = argparse.ArgumentParser(description="Compare each App on old and new.")
    parser.add_argument("wave")
    parser.add_argument("--definition", default=str(REPO_ROOT / "gitops/waves.toml"))
    args = parser.parse_args()
    definition = tomllib.loads(Path(args.definition).read_text())
    waves = [wave["apps"] for wave in definition.get("waves", [])]
    if not args.wave.isdigit() or not 1 <= int(args.wave) <= len(waves):
        print(f"No wave '{args.wave}'. Waves: 1 to {len(waves)}.", file=sys.stderr)
        return 2
    apps = [app for wave in waves[: int(args.wave)] for app in wave]
    settings = definition.get("parity", {})
    old_url, new_url = gateway_url("old"), gateway_url("new")
    print(f"Parity for waves 1-{args.wave}: old {old_url}, new {new_url}")
    failed = total = 0
    for app in apps:
        for path in settings.get("endpoints", ["/"]):
            total += 1
            diffs = differences(fetch(old_url, app, path), fetch(new_url, app, path), settings.get("headers", []))
            print(f"  {'FAIL' if diffs else 'ok  '}  {app} GET {path}")
            for diff in diffs:
                print(f"          {diff}")
            failed += bool(diffs)
    if failed:
        print(f"Parity failed: {failed} of {total} checks differ.")
        return 1
    print(f"Parity passed: {total} checks match.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
