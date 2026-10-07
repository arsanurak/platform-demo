# 1. One repo holds both the IaC area and the GitOps area

Date: 2026-10-07

## Status

Accepted

## Context

A real platform usually keeps infrastructure code and GitOps manifests in separate repos. The split is about access control rather than code organisation:

- The IaC repo can create and destroy accounts, networks and clusters. Few people should be able to merge to it, and its pipeline runs with a powerful **Execution role**.
- The GitOps repo is what Argo CD watches. Many app teams need to change it every day, and its changes should never be able to touch cloud infrastructure.
- Separate repos give each one its own branch protection, code owners, required reviewers, CI credentials and audit trail. A pipeline that can only see the GitOps repo cannot be tricked into applying Terraform.

This repo is a demo. One person works on it, it runs on two local kind clusters, and its cloud parts are validated but never applied. Reviewers should be able to clone one thing and run `make up`.

## Decision

Keep both areas in one repo, as two top-level folders:

- `iac/`: Terraform roots and modules (the **IaC area**).
- `gitops/`: Argo CD applications and ApplicationSets (the **GitOps area**).

Each folder is laid out as if it were the root of its own repo, so splitting them later is a `git filter-repo` away and needs no restructuring. Argo CD reads only from `gitops/`, and CI jobs are scoped by path, as they would be across two repos.

## Consequences

- A reviewer clones once and runs everything with `make` targets.
- One PR can change both areas. In production that would be a smell; here it keeps the history easy to follow.
- The access-control benefits of the split are not demonstrated. They are described here instead.
- In production, split into two repos with separate code owners, branch protection and CI identities: only the IaC pipeline may assume the **Execution role**, and the GitOps repo's CI gets no cloud credentials at all.
