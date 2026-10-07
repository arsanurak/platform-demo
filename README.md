# platform-demo

[![PR checks](https://github.com/arsanurak/platform-demo/actions/workflows/pr.yml/badge.svg?branch=main)](https://github.com/arsanurak/platform-demo/actions/workflows/pr.yml)

> Work in progress. Each section below says what it will cover once the matching ticket lands.

## What this is

_Coming soon:_ a few lines on what this repo demonstrates (migrating apps between two Kubernetes clusters in waves, a CI identity that can't loosen its own guardrails, and agent-assisted delivery), with a link to each matching case-study page on the portfolio site.

## Prerequisites

To run the demo (`make up`):

- Docker, with about 8 GB of memory for it (two kind clusters plus Argo CD on each)
- [kind](https://kind.sigs.k8s.io/), kubectl and curl
- Terraform 1.7 or later (OpenTofu should also work; CI uses Terraform)
- Linux is the tested platform. On macOS, cloud-provider-kind maps gateway addresses through Docker; see its README.

To run the checks only (`make check`): Terraform and Python 3. `make iac-tools` downloads the rest (tflint, trivy, kubeconform, helm, checkov) into `.tools/`, pinned and checksum-verified. No Docker, cluster or cloud account is needed.

## `make up`

```sh
make up
```

Runs Terraform in two stages: first the `old` and `new` kind clusters, then Argo CD and a root app on each (see `iac/local/README.md`). In between it starts cloud-provider-kind, which gives each cluster a Gateway API gateway. Argo CD then syncs each cluster's gateway, and on the old cluster all six **Apps**, `app01` to `app06`. It ends by calling `app01` through the old cluster's gateway, then `app05`'s `/api/echo`, which podinfo forwards to `app04`, so the reply shows `app05` calling `app04`. It prints where the kubeconfig is (`build/kubeconfig`, contexts `kind-old` and `kind-new`). Your own `~/.kube/config` is not touched.

The first bring-up has not been timed yet; expect it to take a while as images download.

## Tour 1: Migrate in waves

```sh
make wave-1   # app01, app02
make wave-2   # app03, app04
make wave-3   # app05, app06 (app05 calls app04, so it moves after it)
```

`make wave-N` applies wave N's ApplicationSet to the new cluster's Argo CD and waits until its **Apps** are healthy there. It refuses to start while an earlier wave is not healthy on new. The old copies keep serving. The waves come from one definition, `gitops/waves.toml`: edit it, run `make waves`, and commit what it writes (see `gitops/README.md`).

### Parity

```sh
make parity WAVE=1   # the Apps in waves 1 to WAVE; WAVE defaults to 1
```

`make parity` is the **Parity check**. For every App in waves 1 to `WAVE` it calls each endpoint through both clusters' gateways (`Host: <app>.example.com`) and compares the HTTP status, a chosen set of headers and the JSON shape: keys and types, not values, so a different pod name or CPU count still matches. The endpoints and headers live in the `[parity]` table of `gitops/waves.toml`. The gateway addresses are read from the clusters; set `OLD_URL` and `NEW_URL` to point it elsewhere. Any difference fails it with a non-zero exit and a diff like this:

```text
  ok    app01 GET /version
  FAIL  app01 GET /healthz
          status: old 200, new 503
          header content-type: old 'application/json; charset=utf-8', new 'text/plain'
          $: type old object, new not JSON
          $.status: missing on new (old: string)
  FAIL  app02 GET /version
          $.commit: missing on new (old: string)
Parity failed: 2 of 6 checks differ.
```

Run it after each `make wave-N`, before any cutover. `tests/scripts/test_parity.py` (part of `make check`) runs it against two local fake gateways, including ones that differ, to show it fails when it should.

### Cutover and rollback

```sh
make cutover WAVE=1             # print the plan; changes nothing
make cutover WAVE=1 CONFIRM=1   # switch wave 1's routing to new, then scale old to 0
make rollback WAVE=1            # print the plan to undo it
make rollback WAVE=1 CONFIRM=1  # scale old back up, wait until ready, route back to old
```

Clients reach every App through the old cluster's gateway. A **Cutover** refuses a wave that isn't healthy on new, then prints its plan:

```text
Cutover plan for wave 1 (app01 app02), through old's gateway:
  app01: route    old HTTPRoute app01/app01: backend app01 -> app01-via-new (new gateway 172.18.0.9)
  app01: scale    old Deployment app01/app01: 1 -> 0 replicas (definition kept)
  ...
  state:       build/cutover/wave-1.json records old's replicas and backends for make rollback WAVE=1
Plan only: nothing changed. Run make cutover WAVE=1 CONFIRM=1 to apply it.
```

With `CONFIRM=1` it records old's replicas and backends in `build/cutover/wave-1.json`, adds an `<app>-via-new` Service on old that forwards to new's gateway, points each HTTPRoute at it, and only then scales old's Deployments to zero. The Deployments stay, so the old side can come back. Afterwards `curl -H 'Host: app01.example.com'` against old's gateway answers from new.

A **Rollback** replays the recorded file: old's replicas first, then routing once they are ready, then it deletes the file. Both commands skip any step already done, so running either twice is safe. Old's Argo CD ignores replicas and HTTPRoute rules so it doesn't undo them; [ADR 2](docs/adr/0002-cutover-changes-old-at-runtime.md) explains why. `tests/scripts/test_cutover.py` (part of `make check`) runs both through `make` against a fake `kubectl` that records every call.

## Tour 2: Guardrails without credentials

_Coming soon:_ `make test-iac`, which runs every infrastructure check with no cloud credentials, and how to read the policy tests.

## Tour 3: How this repo was built

_Coming soon:_ the map issue, one example chain from issue to ADR to pull request, and the agent hooks in `.claude/` that block secrets and risky commands.

## Left out on purpose

_Coming soon:_ what this demo leaves out by choice and why, and what would come next.

## `make down`

```sh
make down
```

Deletes both kind clusters (and with them Argo CD and the apps), the cloud-provider-kind container and the gateway containers it started, and `build/kubeconfig`.
