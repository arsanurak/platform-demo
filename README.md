# platform-demo

[![PR checks](https://github.com/arsanurak/platform-demo/actions/workflows/pr.yml/badge.svg?branch=main)](https://github.com/arsanurak/platform-demo/actions/workflows/pr.yml)
[![Kind smoke test](https://github.com/arsanurak/platform-demo/actions/workflows/smoke.yml/badge.svg?branch=main)](https://github.com/arsanurak/platform-demo/actions/workflows/smoke.yml)

## What this is

A small, runnable model of three pieces of platform work, with generic apps (`app01` to `app06`) and placeholder values throughout:

- **Migrating apps between two Kubernetes clusters in waves**, on two local kind clusters run by Argo CD, with a parity check, cutover and rollback. Case study: [Platform migration in waves](https://arsanurak.github.io/case-studies/platform-migration-in-waves/).
- **A CI identity that can't loosen its own guardrails**: Terraform for an OIDC execution role, its permission boundary and guardrail policies, tested with no AWS credentials. Case study: [CI pipeline guardrails](https://arsanurak.github.io/case-studies/ci-pipeline-guardrails/).
- **Agent-assisted delivery**: the issues, PRs, ADRs and agent hooks that built this repo. Case study: [Agent-assisted delivery](https://arsanurak.github.io/case-studies/agent-assisted-delivery/).

Everything runs through `make` targets; `make help` lists them.

## Prerequisites

To run the demo (`make up` and Tour 1):

- Docker, with about 8 GB of memory for it (two kind clusters plus Argo CD on each)
- [kind](https://kind.sigs.k8s.io/), kubectl and curl
- Terraform 1.7 or later (OpenTofu should also work; CI uses Terraform 1.16.3)
- No separate Helm install: `make up` installs Argo CD through Terraform's Helm provider.
- Linux is the tested platform. On macOS, cloud-provider-kind maps gateway addresses through Docker; see its README.

To run the checks only (`make check`, `make test-iac`): Terraform 1.11 or later and Python 3. `make iac-tools` downloads the rest (tflint, trivy, kubeconform, helm, checkov, pytest) into `.tools/`, pinned and checksum-verified. No Docker, cluster or cloud account is needed.

Don't want to run clusters on your laptop? The [Kind smoke test](.github/workflows/smoke.yml) runs `make up`, Tour 1 and `make down` on a GitHub runner for every change to the demo; its badge above and its logs show the same output quoted below.

## `make up`

```sh
make up
```

Runs Terraform in two stages: first the `old` and `new` kind clusters, then Argo CD and a root app on each (see `iac/local/README.md`). In between it starts cloud-provider-kind, which gives each cluster a Gateway API gateway. Argo CD then syncs each cluster's gateway, and on the old cluster all six **Apps**, `app01` to `app06`. Your own `~/.kube/config` is not touched.

Argo CD tracks `main` of this repo. Set `GIT_REVISION` to deploy another branch or commit instead, for `make up` and every `make wave-N` (both read it): `GIT_REVISION=my-branch make up`.

**What you should see.** Terraform's own output, then one line per App while Argo CD syncs, then two calls through the old cluster's gateway (addresses, pod names and paths differ on your machine):

```text
==> waiting for Argo CD to sync app01 on old
...
==> waiting for Argo CD to sync app06 on old
==> app01 through the old cluster's gateway at 172.18.0.5
{
  "hostname": "app01-cb695d599-xk7cj",
  ...
  "message": "app01",
  ...
}
==> app05 calling app04 (POST /api/echo is forwarded to app04's /echo)
[
  "hello from app05"
]
Up. Use KUBECONFIG=<repo>/build/kubeconfig with the kind-old and kind-new contexts.
```

On a GitHub runner (4 CPU, 16 GB) the first `make up` took about 2.5 minutes, image downloads included. Expect longer on a laptop or a slow connection.

## Tour 1: Migrate in waves

The whole tour for wave 1, in order:

```sh
make wave-1                    # deploy wave 1 on new; old keeps serving
make parity WAVE=1             # compare old and new
make cutover WAVE=1            # print the plan
make cutover WAVE=1 CONFIRM=1  # route wave 1 to new, scale old to 0
make rollback WAVE=1 CONFIRM=1 # put old back
make down                      # when you are done
```

The output below is from a [Kind smoke test](.github/workflows/smoke.yml) run, with runner paths shortened.

### 1. Deploy a wave on new

```sh
make wave-1   # app01, app02
make wave-2   # app03, app04
make wave-3   # app05, app06 (app05 calls app04, so it moves after it)
```

`make wave-N` applies wave N's ApplicationSet to the new cluster's Argo CD and waits until its **Apps** are healthy there. It refuses to start while an earlier wave is not healthy on new. The old copies keep serving. The waves come from one definition, `gitops/waves.toml`: edit it, run `make waves`, and commit what it writes (see `gitops/README.md`).

**What you should see:**

```text
==> wave 1: applying its ApplicationSet to new (tracking <revision>)
==> waiting for app01 to be healthy on new
==> waiting for app02 to be healthy on new
Wave 1 is healthy on new: app01 app02
```

### 2. Parity

```sh
make parity WAVE=1   # the Apps in waves 1 to WAVE; WAVE defaults to 1
```

`make parity` is the **Parity check**. For every App in waves 1 to `WAVE` it calls each endpoint through both clusters' gateways (`Host: <app>.example.com`) and compares the HTTP status, a chosen set of headers and the JSON shape: keys and types, not values, so a different pod name or CPU count still matches. The endpoints and headers live in the `[parity]` table of `gitops/waves.toml`. The gateway addresses are read from the clusters; set `OLD_URL` and `NEW_URL` to point it elsewhere.

**What you should see:**

```text
Parity for waves 1-1: old http://172.18.0.5, new http://172.18.0.4
  ok    app01 GET /
  ok    app01 GET /version
  ok    app01 GET /healthz
  ok    app02 GET /
  ok    app02 GET /version
  ok    app02 GET /healthz
Parity passed: 6 checks match.
```

Any difference fails it with a non-zero exit and a diff like this:

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

### 3. Cutover

```sh
make cutover WAVE=1             # print the plan; changes nothing
make cutover WAVE=1 CONFIRM=1   # switch wave 1's routing to new, then scale old to 0
```

Clients reach every App through the old cluster's gateway. A **Cutover** refuses a wave that isn't healthy on new. With `CONFIRM=1` it records old's replicas and backends in `build/cutover/wave-1.json`, adds an `<app>-via-new` Service on old that forwards to new's gateway, points each HTTPRoute at it, and only then scales old's Deployments to zero. The Deployments stay, so the old side can come back.

**What you should see:**

```text
Cutover plan for wave 1 (app01 app02), through old's gateway:
  app01: route    old HTTPRoute app01/app01: backend app01 -> app01-via-new (new gateway 172.18.0.4)
  app01: scale    old Deployment app01/app01: 1 -> 0 replicas (definition kept)
  app02: route    old HTTPRoute app02/app02: backend app02 -> app02-via-new (new gateway 172.18.0.4)
  app02: scale    old Deployment app02/app02: 1 -> 0 replicas (definition kept)
  state:       <repo>/build/cutover/wave-1.json records old's replicas and backends for make rollback WAVE=1
==> recorded rollback state in <repo>/build/cutover/wave-1.json
==> app01: routing old's gateway to new
==> app02: routing old's gateway to new
==> app01: scaling old to 0 replicas
==> app02: scaling old to 0 replicas
==> app01: old's gateway answers 200, served by new
==> app02: old's gateway answers 200, served by new
Wave 1 is cut over: old's gateway sends app01 app02 to new. Undo with make rollback WAVE=1.
```

Without `CONFIRM=1` it prints the plan and ends with `Plan only: nothing changed. Run make cutover WAVE=1 CONFIRM=1 to apply it.` To check it yourself, `curl -H 'Host: app01.example.com'` against old's gateway: the `hostname` in the reply is a pod on new (`kubectl --context kind-new -n app01 get pods`). `make parity WAVE=1` still passes.

### 4. Rollback

```sh
make rollback WAVE=1            # print the plan to undo it
make rollback WAVE=1 CONFIRM=1  # scale old back up, wait until ready, route back to old
```

A **Rollback** replays the recorded file: old's replicas first, then routing once they are ready, then it deletes the file.

**What you should see:**

```text
Rollback plan for wave 1 (app01 app02), replaying <repo>/build/cutover/wave-1.json:
  app01: scale    old Deployment app01/app01: 0 -> 1 replicas, then wait until ready
  app01: route    old HTTPRoute app01/app01: backend app01-via-new -> app01
  app02: scale    old Deployment app02/app02: 0 -> 1 replicas, then wait until ready
  app02: route    old HTTPRoute app02/app02: backend app02-via-new -> app02
  state:       <repo>/build/cutover/wave-1.json is deleted once old serves again
==> app01: scaling old back to 1 replicas
==> app02: scaling old back to 1 replicas
==> app01: routing old's gateway back to old
==> app02: routing old's gateway back to old
==> app01: old's gateway answers 200, served by old
==> app02: old's gateway answers 200, served by old
Wave 1 is rolled back: old serves app01 app02 again.
```

Both commands end by waiting until old's gateway answers each App again, because the gateway picks up a route change a few seconds late. Both skip any step already done, so running either twice is safe. Old's Argo CD ignores replicas and HTTPRoute rules so it doesn't undo them; [ADR 2](docs/adr/0002-cutover-changes-old-at-runtime.md) explains why. `tests/scripts/test_cutover.py` (part of `make check`) runs both through `make` against a fake `kubectl` that records every call.

### Smoke test in CI

The [Kind smoke test](.github/workflows/smoke.yml) runs this tour on a GitHub runner: `make up`, `make wave-1`, `make parity`, a confirmed cutover (then checks that old's gateway is answered by new's pods), a confirmed rollback, and `make down` whatever happened. It runs on pull requests and pushes to `main` that touch `gitops/`, `iac/local/`, `scripts/` or the `Makefile`, weekly, and on demand, with `GIT_REVISION` set to the commit under test.

## Tour 2: Guardrails without credentials

```sh
make test-iac
```

Runs every IaC check with no cloud credentials: `terraform fmt` and `validate`, `terraform test` against mocked providers, tflint, trivy, checkov, then the policy checks. The first run downloads the pinned tools into `.tools/`. Any failure stops it with a non-zero exit. The same target runs on every pull request in the [PR checks](.github/workflows/pr.yml).

What is being checked lives in `iac/guardrails/` (never applied; see its [README](iac/guardrails/README.md)): the **Execution role** CI assumes through GitHub OIDC, its **Permission boundary**, the **Guardrail policy** that stops it editing itself, and a service control policy that locks payment methods.

### How to read the policy tests

There are three layers. Each one answers a different question.

1. **Is it wired up?** `iac/guardrails/tests/guardrails.tftest.hcl`. Each `run` block plans against a mocked AWS provider and asserts one fact, named in the block: `execution_role_is_capped_by_the_boundary`, `guardrail_is_attached_to_the_execution_role`, `only_main_of_one_repository_can_assume_the_role`, `github_is_the_only_oidc_issuer`, `payment_lockout_is_an_attached_scp`. The last, `a_wildcard_repository_is_rejected`, uses `expect_failures`: it passes only if Terraform refuses the input. Terraform reports `Success! N passed, 0 failed.` per folder.
2. **Do the policies hold?** `iac/policy_checks/check_policies.py` reads the policy JSON that `make render-policies` writes to `build/guardrails.json` and checks four properties by id. A pass prints:

   ```text
   [role-has-boundary] ok
   [role-cannot-edit-itself] ok
   [no-wildcard-iam-writes] ok
   [payment-methods-locked] ok
   ```

   A failure prints `[<id>] FAIL: <what is wrong>` and exits 1.
3. **Would the checks catch a regression?** `iac/policy_checks/tests/test_guardrail_policies.py`. The first test runs the checker on the real JSON. Every other test loosens a copy on purpose and asserts the checker fails with the right id. Read each test name as the regression it guards against: `test_a_role_without_a_permission_boundary_fails`, `test_a_role_that_can_attach_policies_to_itself_fails`, `test_a_role_that_can_rewrite_its_boundary_fails`, `test_a_wildcard_iam_action_fails`, `test_an_iam_write_on_every_resource_fails`, `test_an_scp_that_lets_payment_methods_change_fails`. One test, `test_reading_iam_with_a_wildcard_passes`, shows the check is not too strict.

`make simulate-policies` asks the AWS IAM policy simulator about a matrix of calls. It needs AWS credentials, so it skips without them; `iac/policy_checks/tests/test_policy_simulator.py` proves it skips cleanly.

## Tour 3: How this repo was built

An agent (Claude Code) wrote most of this repo, one ticket and one pull request at a time, with a human reviewing each PR. The trail is public:

1. **The map.** [Issue #1](https://github.com/arsanurak/platform-demo/issues/1) lists the tickets as sub-issues, with the order they block each other in and the decisions so far.
2. **A ticket.** [Issue #5, Cutover and rollback](https://github.com/arsanurak/platform-demo/issues/5) says what `make cutover` and `make rollback` must do.
3. **Its pull request.** [PR #15](https://github.com/arsanurak/platform-demo/pull/15) implements it with its tests (`tests/scripts/test_cutover.py`) and closes #5. Its commits carry a `Co-Authored-By` line for the agent.
4. **The decision it forced.** Old's Argo CD would undo a cutover within minutes. PR #15 records how that is handled in [ADR 2](docs/adr/0002-cutover-changes-old-at-runtime.md), so the reason survives the PR. [ADR 1](docs/adr/0001-one-repo-for-iac-and-gitops.md) is the other decision so far.

[`CLAUDE.md`](CLAUDE.md) holds the agent's rules for this public repo, and [`CONTEXT.md`](CONTEXT.md) the shared vocabulary that issues, code and this README use.

### The hooks

[`.claude/settings.json`](.claude/settings.json) runs two `PreToolUse` hooks before the agent's tool calls:

- [`secret_guard.py`](.claude/hooks/secret_guard.py) blocks secret-shaped values in writes and commands, and reads of well-known secret files.
- [`command_guard.py`](.claude/hooks/command_guard.py) blocks cluster and cloud writes (`kubectl apply`, for example, even inside a chain or `bash -c`), destructive commands and data exfiltration. It answers `Command guard: blocked. <reason>. If it is really needed, ask the human to run it.`

Their tests live in `tests/hooks/` and run with `make test-hooks` (part of `make check`). They call each hook as Claude Code does, with a JSON tool call on stdin, and assert it blocks or allows; `test_settings.py` checks that `settings.json` actually wires both up. Fake secrets are built at runtime from fragments, so none sits in the repo.

## Left out on purpose

Each of these would add weight without changing what the demo shows:

- **Istio or another service mesh**: routing between clusters here is a Gateway API route and a Service; a mesh would add a control plane on each cluster for the same result.
- **Keycloak or other auth**: the apps are stateless podinfo instances; auth would change none of the wave, parity, cutover or rollback steps.
- **RabbitMQ or other real brokers**: draining queues is its own migration problem; `app05` calling `app04` over HTTP shows the dependency that sets wave order.
- **Monitoring stacks**: the parity check and the smoke test are the evidence here; Prometheus and Grafana would double the memory a laptop needs.
- **A real AWS apply**: it needs an account and costs money; `iac/eks/` and `iac/guardrails/` are validated and tested with mocked providers instead, and only accept the placeholder account `000000000000`.

### Next

- **Karpenter, KWOK and all-spot node pools** (with spot interruption handling): left for later so that running the demo needs no Go toolchain or `ko`.

## `make down`

```sh
make down
```

Deletes both kind clusters (and with them Argo CD and the apps), the cloud-provider-kind container and the gateway containers it started, and `build/kubeconfig`.

**What you should see:** Terraform destroying the clusters, then:

```text
==> cloud-provider-kind and the gateway containers it started
Down. No demo clusters or containers are left.
```
