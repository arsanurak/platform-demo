# The Makefile is this repo's interface: the README, CI and tests all go through it.
.DEFAULT_GOAL := help
SHELL := /usr/bin/env bash
PYTHON ?= python3

# Pinned IaC check tools, installed into .tools/ by `make iac-tools`.
TOOLS := $(CURDIR)/.tools
export TFLINT_PLUGIN_DIR := $(TOOLS)/tflint-plugins
RENDERED := build/guardrails.json

.PHONY: help check test-hooks check-actions fmt-check validate test-tf \
	iac-tools tflint trivy checkov render-policies test-policies test-iac simulate-policies

help: ## List the targets
	@grep -E '^[a-z0-9-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-16s %s\n", $$1, $$2}'

check: test-hooks check-actions test-iac ## Run every static check the PR workflow runs

test-hooks: ## Test the agent guard hooks and repo scripts
	$(PYTHON) -m unittest discover -s tests -t . -v

check-actions: ## Fail if any GitHub Action is not pinned to a commit SHA
	$(PYTHON) scripts/check_pinned_actions.py .github/workflows

fmt-check: ## Check Terraform formatting under iac/
	terraform fmt -check -recursive -diff iac

validate: ## Run terraform validate on every folder under iac/
	scripts/terraform-validate.sh iac

test-tf: ## Run terraform test (mock providers, no credentials) under iac/
	scripts/terraform-test.sh iac

iac-tools: ## Install the pinned tflint, trivy, checkov and pytest into .tools/
	PYTHON=$(PYTHON) scripts/install-iac-tools.sh

tflint: iac-tools ## Lint every folder under iac/ with tflint and its AWS ruleset
	$(TOOLS)/bin/tflint --chdir iac --recursive --config "$(CURDIR)/.tflint.hcl"

trivy: iac-tools ## Scan iac/ for misconfigurations with trivy
	$(TOOLS)/bin/trivy config --quiet --exit-code 1 iac

checkov: iac-tools ## Scan iac/ for misconfigurations with checkov
	$(TOOLS)/venv/bin/checkov --directory iac --framework terraform --quiet --compact

render-policies: ## Render the guardrail policies to build/guardrails.json
	@mkdir -p build
	iac/policy_checks/render-policies.sh $(RENDERED)

test-policies: iac-tools render-policies ## Check the guardrail properties on the rendered policy JSON
	$(PYTHON) iac/policy_checks/check_policies.py $(RENDERED)
	$(TOOLS)/venv/bin/pytest iac/policy_checks

test-iac: fmt-check validate test-tf tflint trivy checkov test-policies ## Run every IaC check, with no cloud credentials

simulate-policies: render-policies ## Opt-in: run the IAM policy simulator matrix (skips without AWS credentials)
	$(PYTHON) iac/policy_checks/simulate_policies.py $(RENDERED)
