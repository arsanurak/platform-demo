# platform-demo

A public, runnable demo of three platform-engineering patterns: migrating apps between Kubernetes clusters in waves, a CI identity that can't loosen its own guardrails, and agent-assisted delivery. Everything runs free on a laptop; cloud parts are written and checked but never applied.

## Language

### Migration

**Old cluster**:
The local kind cluster the apps start on. It plays the platform being migrated away from.
_Avoid_: source, legacy, blue

**New cluster**:
The local kind cluster the apps move to.
_Avoid_: target, green

**App**:
One of the sample workloads `app01` to `app06`, each a podinfo instance. `app05` calls `app04`, which gives the waves a real dependency.
_Avoid_: service, microservice

**Wave**:
An ordered batch of **Apps** moved from the **Old cluster** to the **New cluster** together. Waves are generated from one definition of membership and order, never edited by hand.
_Avoid_: batch, phase, stage

**Parity check**:
A comparison of each **App** on the **Old cluster** and the **New cluster**: HTTP status, a chosen set of headers, and the JSON shape (keys and types, not values). Any difference fails it.
_Avoid_: smoke test, diff

**Cutover**:
Switching routing for a **Wave**'s **Apps** to the **New cluster**, then scaling the old copies to zero replicas while keeping their definitions. It prints its plan before acting.
_Avoid_: switchover, go-live

**Rollback**:
Restoring the old copies' replicas and routing after a **Cutover**.

### Guardrails

**Execution role**:
The cloud identity CI assumes through OIDC to apply infrastructure. It holds no stored keys.
_Avoid_: CI user, deploy user

**Permission boundary**:
The policy that caps what the **Execution role** can ever do, whatever its own policies grant.

**Guardrail policy**:
A deny policy that holds even against the **Execution role**: it can't edit itself or its **Permission boundary**, and it can't touch payment methods.

### Repo areas

**IaC area**:
The `iac/` folder: Terraform roots and modules.

**GitOps area**:
The `gitops/` folder: Argo CD applications and ApplicationSets that Argo CD syncs onto the clusters.

**Make target**:
A `make` entry point (`make up`, `make wave-1`, `make parity`, ...). It is the only interface: the README, CI and tests all go through it.
_Avoid_: script, task

### Agent workflow

**Hook**:
A script the coding agent's harness runs before a tool call. A hook can block the call. This repo commits two: the **Secret guard** and the **Command guard**.

**Secret guard**:
The **Hook** that blocks writing secret-shaped values (cloud keys, tokens, private keys) and reading well-known secret files.

**Command guard**:
The **Hook** that blocks shell commands that write to a cluster or cloud, destroy data, or send data out of the machine.

**Map**:
The parent issue that lists every ticket for the demo and how they block each other.

## Relationships

- A **Wave** holds one or more **Apps**; an **App** belongs to exactly one **Wave**.
- A **Cutover** applies to one **Wave** and should follow a passing **Parity check**.
- The **Permission boundary** caps the **Execution role**; **Guardrail policies** protect both.
