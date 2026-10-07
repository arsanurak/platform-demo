import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check_pinned_actions.py"
SHA = "0123456789abcdef0123456789abcdef01234567"


def check(workflow_text):
    with tempfile.TemporaryDirectory() as folder:
        (Path(folder) / "ci.yml").write_text(workflow_text)
        result = subprocess.run([sys.executable, str(SCRIPT), folder], capture_output=True, text=True)
    return result.returncode, result.stdout + result.stderr


def workflow(uses_line):
    return f"jobs:\n  build:\n    steps:\n      - {uses_line}\n"


class CheckPinnedActionsTest(unittest.TestCase):
    def test_passes_an_action_pinned_to_a_sha_with_a_version_comment(self):
        code, _ = check(workflow(f"uses: actions/checkout@{SHA} # v4.2.2"))
        self.assertEqual(code, 0)

    def test_fails_an_action_pinned_to_a_tag(self):
        code, output = check(workflow("uses: actions/checkout@v4"))
        self.assertEqual(code, 1)
        self.assertIn("actions/checkout@v4", output)

    def test_fails_a_sha_pin_without_a_version_comment(self):
        code, _ = check(workflow(f"uses: actions/checkout@{SHA}"))
        self.assertEqual(code, 1)

    def test_fails_a_short_sha(self):
        code, _ = check(workflow("uses: actions/checkout@0123456 # v4.2.2"))
        self.assertEqual(code, 1)

    def test_passes_local_actions_and_reusable_workflows_in_this_repo(self):
        code, _ = check(workflow("uses: ./.github/actions/setup"))
        self.assertEqual(code, 0)

    def test_checks_quoted_uses_and_reusable_workflow_calls(self):
        text = f"jobs:\n  call:\n    uses: 'org/repo/.github/workflows/x.yml@main'\n"
        code, output = check(text)
        self.assertEqual(code, 1)
        self.assertIn("org/repo/.github/workflows/x.yml@main", output)

    def test_passes_a_docker_image_pinned_by_digest(self):
        code, _ = check(workflow("uses: docker://alpine@sha256:" + "a" * 64))
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
