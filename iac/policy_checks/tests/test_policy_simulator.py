"""The opt-in IAM policy-simulator matrix, tested through its command line.

The real run needs AWS credentials and happens only in CI when they are
configured. These tests cover the parts that need none: it skips cleanly
without credentials, and it fails when IAM disagrees with the expected matrix.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

SIMULATOR = Path(__file__).resolve().parents[1] / "simulate_policies.py"


def run_simulator(manifest_path, env):
    result = subprocess.run(
        [sys.executable, str(SIMULATOR), str(manifest_path)], capture_output=True, text=True, env=env
    )
    return result.returncode, result.stdout + result.stderr


def env_without_aws():
    return {k: v for k, v in os.environ.items() if not k.startswith("AWS_")}


def test_it_skips_cleanly_without_credentials(rendered, tmp_path):
    manifest = tmp_path / "guardrails.json"
    manifest.write_text(json.dumps(rendered))

    code, output = run_simulator(manifest, env_without_aws())

    assert code == 0, output
    assert "skipped" in output.lower()


def test_it_fails_when_iam_allows_a_call_the_guardrails_should_deny(rendered, tmp_path):
    manifest = tmp_path / "guardrails.json"
    manifest.write_text(json.dumps(rendered))
    # A stand-in `aws` CLI that answers "allowed" to every simulated call.
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_aws = fake_bin / "aws"
    fake_aws.write_text(
        "#!/bin/sh\n"
        'echo \'{"EvaluationResults": [{"EvalActionName": "x", "EvalDecision": "allowed"}]}\'\n'
    )
    fake_aws.chmod(0o755)
    env = env_without_aws()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
    env["AWS_ACCESS_KEY_ID"] = "fake" + "-for-test"

    code, output = run_simulator(manifest, env)

    assert code == 1
    assert "iam:PutRolePolicy" in output
    assert "expected explicitDeny" in output
