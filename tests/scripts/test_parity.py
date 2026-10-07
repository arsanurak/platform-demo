import json
import os
import subprocess
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

ROOT = {"hostname": "app01-abc", "version": "6.15.0", "num_cpu": 4, "runtime": {"go": "1.24"}}
VERSION = {"commit": "abc123", "version": "6.15.0"}
HEALTHZ = {"status": "OK"}


def podinfo_like(**overrides):
    """Responses a podinfo App gives, keyed by path: (status, headers, body)."""
    responses = {
        "/": (200, {"Content-Type": "application/json; charset=utf-8"}, ROOT),
        "/version": (200, {"Content-Type": "application/json; charset=utf-8"}, VERSION),
        "/healthz": (200, {"Content-Type": "application/json; charset=utf-8"}, HEALTHZ),
    }
    responses.update(overrides)
    return responses


class FakeCluster:
    """A local HTTP server that plays one cluster's Gateway: it routes on the Host header."""

    def __init__(self, apps):
        self.apps = apps  # {"app01.example.com": {path: (status, headers, body)}}
        cluster = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                app = cluster.apps.get(self.headers.get("Host", ""), {})
                status, headers, body = app.get(self.path, (404, {"Content-Type": "text/plain"}, "not found"))
                payload = (body if isinstance(body, str) else json.dumps(body)).encode()
                self.send_response(status)
                for name, value in headers.items():
                    self.send_header(name, value)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def wave1(app01=None, app02=None):
    return {"app01.example.com": app01 or podinfo_like(), "app02.example.com": app02 or podinfo_like()}


class ParityTargetTest(unittest.TestCase):
    def parity(self, old_apps, new_apps, wave="1"):
        old, new = FakeCluster(old_apps), FakeCluster(new_apps)
        self.addCleanup(old.close)
        self.addCleanup(new.close)
        env = {**os.environ, "OLD_URL": old.url, "NEW_URL": new.url}
        return subprocess.run(
            ["make", "-s", "parity", f"WAVE={wave}"], cwd=REPO_ROOT, env=env, capture_output=True, text=True
        )

    def test_identical_old_and_new_pass_for_every_app_in_the_wave(self):
        result = self.parity(wave1(), wave1())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("app01", result.stdout)
        self.assertIn("app02", result.stdout)
        self.assertIn("Parity passed", result.stdout)

    def test_a_key_missing_on_new_fails_and_names_the_app_endpoint_and_key(self):
        trimmed = {key: value for key, value in VERSION.items() if key != "commit"}
        new = wave1(app02=podinfo_like(**{"/version": (200, {"Content-Type": "application/json; charset=utf-8"}, trimmed)}))
        result = self.parity(wave1(), new)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("FAIL  app02 GET /version", result.stdout)
        self.assertIn("$.commit: missing on new (old: string)", result.stdout)
        self.assertIn("ok    app01 GET /version", result.stdout)
        self.assertIn("Parity failed: 1 of 6 checks differ.", result.stdout)

    def test_same_shape_with_different_values_passes(self):
        other_pod = {"hostname": "app01-xyz", "version": "6.15.1", "num_cpu": 8, "runtime": {"go": "1.25"}}
        new = wave1(app01=podinfo_like(**{"/": (200, {"Content-Type": "application/json; charset=utf-8"}, other_pod)}))
        result = self.parity(wave1(), new)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Parity passed: 6 checks match.", result.stdout)

    def test_a_different_status_and_header_fail_and_are_named(self):
        new = wave1(app01=podinfo_like(**{"/healthz": (503, {"Content-Type": "text/plain"}, "unavailable")}))
        result = self.parity(wave1(), new)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("FAIL  app01 GET /healthz", result.stdout)
        self.assertIn("status: old 200, new 503", result.stdout)
        self.assertIn("header content-type: old 'application/json; charset=utf-8', new 'text/plain'", result.stdout)
        self.assertIn("$: type old object, new not JSON", result.stdout)

    def test_an_app_new_does_not_serve_yet_fails(self):
        result = self.parity(wave1(), {"app01.example.com": podinfo_like()})
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("FAIL  app02 GET /", result.stdout)
        self.assertIn("status: old 200, new 404", result.stdout)

    def test_an_unreachable_cluster_fails_and_says_which(self):
        env = {**os.environ, "OLD_URL": "http://127.0.0.1:9", "NEW_URL": "http://127.0.0.1:9"}
        result = subprocess.run(["make", "-s", "parity", "WAVE=1"], cwd=REPO_ROOT, env=env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("request: old unreachable", result.stdout)

    def test_an_unknown_wave_fails_and_lists_the_waves(self):
        result = self.parity(wave1(), wave1(), wave="9")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No wave '9'. Waves: 1 to 3.", result.stderr)


if __name__ == "__main__":
    unittest.main()
