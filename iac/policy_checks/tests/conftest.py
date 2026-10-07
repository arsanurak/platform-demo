"""Fixtures for the guardrail policy tests.

The tests read the policy JSON that Terraform renders (iac/policy_checks/render-policies.sh)
and run the policy checker on it, exactly as `make test-iac` does.
"""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

POLICY_CHECKS = Path(__file__).resolve().parents[1]
RENDER = POLICY_CHECKS / "render-policies.sh"
CHECKER = POLICY_CHECKS / "check_policies.py"


@pytest.fixture(scope="session")
def rendered(tmp_path_factory):
    """The guardrails as rendered by Terraform: one JSON manifest, loaded as a dict."""
    out = tmp_path_factory.mktemp("rendered") / "guardrails.json"
    subprocess.run([str(RENDER), str(out)], check=True, capture_output=True, text=True)
    return json.loads(out.read_text())


@pytest.fixture
def manifest(rendered):
    """A private copy of the rendered manifest that a test may loosen."""
    return copy.deepcopy(rendered)


@pytest.fixture
def check(tmp_path):
    """Run the policy checker CLI on a manifest. Returns (exit code, output)."""

    def run(manifest):
        path = tmp_path / "guardrails.json"
        path.write_text(json.dumps(manifest))
        result = subprocess.run(
            [sys.executable, str(CHECKER), str(path)], capture_output=True, text=True
        )
        return result.returncode, result.stdout + result.stderr

    return run
