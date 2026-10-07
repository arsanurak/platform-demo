# The Makefile is this repo's interface: the README, CI and tests all go through it.
.DEFAULT_GOAL := help
SHELL := /usr/bin/env bash
PYTHON ?= python3

.PHONY: help check test-hooks check-actions fmt-check validate

help: ## List the targets
	@grep -E '^[a-z0-9-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-16s %s\n", $$1, $$2}'

check: test-hooks check-actions fmt-check validate ## Run every static check the PR workflow runs

test-hooks: ## Test the agent guard hooks and repo scripts
	$(PYTHON) -m unittest discover -s tests -t . -v

check-actions: ## Fail if any GitHub Action is not pinned to a commit SHA
	$(PYTHON) scripts/check_pinned_actions.py .github/workflows

fmt-check: ## Check Terraform formatting under iac/
	terraform fmt -check -recursive -diff iac

validate: ## Run terraform validate on every folder under iac/
	scripts/terraform-validate.sh iac
