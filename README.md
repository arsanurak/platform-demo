# platform-demo

[![PR checks](https://github.com/arsanurak/platform-demo/actions/workflows/pr.yml/badge.svg?branch=main)](https://github.com/arsanurak/platform-demo/actions/workflows/pr.yml)

> Work in progress. Each section below says what it will cover once the matching ticket lands.

## What this is

_Coming soon:_ a few lines on what this repo demonstrates (migrating apps between two Kubernetes clusters in waves, a CI identity that can't loosen its own guardrails, and agent-assisted delivery), with a link to each matching case-study page on the portfolio site.

## Prerequisites

_Coming soon:_ the tools and versions you need (Docker, kind, kubectl, helm, Terraform 1.7 or later or OpenTofu) and roughly how much memory Docker needs.

## `make up`

_Coming soon:_ the one command that brings up the old and new clusters, Argo CD and the sample apps, and how long the first bring-up takes.

## Tour 1: Migrate in waves

_Coming soon:_ `make wave-1`, then `make parity`, `make cutover` and `make rollback`, with what you should see after each step.

## Tour 2: Guardrails without credentials

_Coming soon:_ `make test-iac`, which runs every infrastructure check with no cloud credentials, and how to read the policy tests.

## Tour 3: How this repo was built

_Coming soon:_ the map issue, one example chain from issue to ADR to pull request, and the agent hooks in `.claude/` that block secrets and risky commands.

## Left out on purpose

_Coming soon:_ what this demo leaves out by choice and why, and what would come next.

## `make down`

_Coming soon:_ the one command that removes every cluster and container this demo created.
