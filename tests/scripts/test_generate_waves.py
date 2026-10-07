import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "generate-waves.py"
DEFINITION = REPO_ROOT / "gitops" / "waves.toml"

TWO_WAVES = """
[apps.app01]
[apps.app02]
calls = "app01"

[[waves]]
apps = ["app01"]

[[waves]]
apps = ["app02"]
"""


def generate(definition_text=None, definition_path=None):
    """Run the generator; return (exit code, output, out folder, cleanup)."""
    out = tempfile.TemporaryDirectory()
    if definition_path is None:
        definition_path = Path(out.name) / "waves.toml"
        definition_path.write_text(definition_text)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--definition", str(definition_path), "--out", out.name],
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout + result.stderr, Path(out.name), out.cleanup


def wave_apps(out, wave):
    text = (out / "waves" / f"wave-{wave}" / "applicationset.yaml").read_text()
    return re.findall(r"^\s+- app: (\S+)$", text, re.MULTILINE)


class GenerateWavesTest(unittest.TestCase):
    def run_ok(self, definition_text=None, definition_path=None):
        code, output, out, cleanup = generate(definition_text, definition_path)
        self.addCleanup(cleanup)
        self.assertEqual(code, 0, output)
        return out

    def run_failing(self, definition_text):
        code, output, _, cleanup = generate(definition_text)
        self.addCleanup(cleanup)
        self.assertNotEqual(code, 0)
        return output

    def test_writes_a_folder_of_manifests_for_every_app(self):
        out = self.run_ok(TWO_WAVES)
        for app in ("app01", "app02"):
            names = sorted(p.name for p in (out / "apps" / app).iterdir())
            self.assertEqual(names, ["deployment.yaml", "httproute.yaml", "service.yaml"])

    def test_writes_one_applicationset_per_wave_listing_its_apps(self):
        out = self.run_ok(TWO_WAVES)
        self.assertEqual(wave_apps(out, 1), ["app01"])
        self.assertEqual(wave_apps(out, 2), ["app02"])
        self.assertFalse((out / "waves" / "wave-3").exists())

    def test_wave_applicationset_deploys_each_app_from_its_folder(self):
        out = self.run_ok(TWO_WAVES)
        text = (out / "waves" / "wave-1" / "applicationset.yaml").read_text()
        self.assertIn("name: wave-1", text)
        self.assertIn('path: "gitops/apps/{{ .app }}"', text)

    def test_an_app_that_calls_another_gets_its_backend_url(self):
        out = self.run_ok(TWO_WAVES)
        caller = (out / "apps" / "app02" / "deployment.yaml").read_text()
        self.assertIn("--backend-url=http://app01.app01.svc.cluster.local/echo", caller)
        callee = (out / "apps" / "app01" / "deployment.yaml").read_text()
        self.assertNotIn("--backend-url", callee)

    def test_every_app_runs_non_root_with_a_read_only_root_and_no_capabilities(self):
        out = self.run_ok(TWO_WAVES)
        for app in ("app01", "app02"):
            text = (out / "apps" / app / "deployment.yaml").read_text()
            for line in ("runAsNonRoot: true", "readOnlyRootFilesystem: true",
                         "allowPrivilegeEscalation: false", 'drop: ["ALL"]'):
                self.assertIn(line, text, f"{app}: {line}")

    def test_rejects_an_app_in_the_same_wave_as_an_app_it_calls(self):
        output = self.run_failing(TWO_WAVES.replace('apps = ["app01"]\n\n[[waves]]\napps = ["app02"]',
                                                    'apps = ["app01", "app02"]'))
        self.assertIn("app02 calls app01", output)

    def test_rejects_an_app_in_an_earlier_wave_than_an_app_it_calls(self):
        output = self.run_failing(TWO_WAVES.replace('apps = ["app01"]', 'apps = ["@"]')
                                  .replace('apps = ["app02"]', 'apps = ["app01"]')
                                  .replace('apps = ["@"]', 'apps = ["app02"]'))
        self.assertIn("app02 calls app01", output)

    def test_rejects_an_app_that_is_in_no_wave(self):
        output = self.run_failing(TWO_WAVES + "[apps.app03]\n")
        self.assertIn("app03", output)

    def test_rejects_an_app_in_two_waves(self):
        output = self.run_failing(TWO_WAVES.replace('apps = ["app02"]', 'apps = ["app02", "app01"]'))
        self.assertIn("app01", output)

    def test_rejects_a_wave_naming_an_unknown_app(self):
        output = self.run_failing(TWO_WAVES.replace('apps = ["app02"]', 'apps = ["app02", "app09"]'))
        self.assertIn("app09", output)

    def test_rejects_a_call_to_an_unknown_app(self):
        output = self.run_failing(TWO_WAVES.replace('calls = "app01"', 'calls = "app09"'))
        self.assertIn("app09", output)

    def test_the_repo_definition_moves_app04_in_an_earlier_wave_than_app05(self):
        out = self.run_ok(definition_path=DEFINITION)
        waves = {app: n for n in (1, 2, 3) for app in wave_apps(out, n)}
        self.assertEqual(sorted(waves), [f"app0{i}" for i in range(1, 7)])
        self.assertLess(waves["app04"], waves["app05"])
        caller = (out / "apps" / "app05" / "deployment.yaml").read_text()
        self.assertIn("--backend-url=http://app04.app04.svc.cluster.local/echo", caller)


if __name__ == "__main__":
    unittest.main()
