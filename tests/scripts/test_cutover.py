import json
import os
import shutil
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FAKE_KUBECTL = REPO_ROOT / "tests/fixtures/fake-kubectl"
WRITES = {"apply", "scale", "patch", "delete", "create", "replace", "edit"}


def deployment(app, replicas):
    return {"kind": "Deployment", "metadata": {"name": app, "namespace": app}, "spec": {"replicas": replicas}}


def route(app, backend):
    return {"kind": "HTTPRoute", "metadata": {"name": app, "namespace": app},
            "spec": {"rules": [{"backendRefs": [{"name": backend, "port": 80}]}]}}


class FakeOldGateway:
    """Old's gateway: answers 503 to the first `unready` requests, then 200."""

    def __init__(self, unready=0):
        self.unready = unready
        gateway = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                status = 503 if gateway.unready > 0 else 200
                gateway.unready -= 1
                self.send_response(status)
                self.end_headers()

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.address = f"127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def two_clusters(old_gateway, wave1_health="Healthy"):
    """Old runs every App with 2 replicas; wave 1 (app01, app02) is up on new."""
    objects = {"kind-new/Gateway/gateway/web": {"status": {"addresses": [{"value": "172.18.0.9"}]}},
               "kind-old/Gateway/gateway/web": {"status": {"addresses": [{"value": old_gateway.address}]}}}
    for app in ["app01", "app02", "app03"]:
        objects[f"kind-old/Deployment/{app}/{app}"] = deployment(app, 2)
        objects[f"kind-old/HTTPRoute/{app}/{app}"] = route(app, app)
    for app in ["app01", "app02"]:
        objects[f"kind-new/Application/argocd/{app}"] = {"status": {"health": {"status": wave1_health}}}
    return objects


class CutoverTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.state = self.tmp / "cluster.json"
        self.log = self.tmp / "calls.log"
        self.gateway = FakeOldGateway()
        self.addCleanup(self.gateway.close)
        self.state.write_text(json.dumps(two_clusters(self.gateway)))
        self.log.touch()

    def make(self, *args, **extra_env):
        env = dict(os.environ, **extra_env, PATH=f"{FAKE_KUBECTL}:{os.environ['PATH']}",
                   FAKE_KUBE_STATE=str(self.state), FAKE_KUBE_LOG=str(self.log),
                   CUTOVER_STATE_DIR=str(self.tmp / "rollback"))
        return subprocess.run(["make", "-s", *args], cwd=REPO_ROOT, env=env, capture_output=True, text=True)

    def cluster(self):
        return json.loads(self.state.read_text())

    def writes(self):
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        return [c for c in calls if WRITES & set(c)]

    def backend(self, app):
        return self.cluster()[f"kind-old/HTTPRoute/{app}/{app}"]["spec"]["rules"][0]["backendRefs"][0]["name"]

    def replicas(self, app):
        return self.cluster()[f"kind-old/Deployment/{app}/{app}"]["spec"]["replicas"]

    def test_without_confirm_cutover_prints_the_plan_and_changes_nothing(self):
        before = self.cluster()
        result = self.make("cutover", "WAVE=1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("app01", result.stdout)
        self.assertIn("app01-via-new", result.stdout)
        self.assertIn("2 -> 0", result.stdout)
        self.assertIn("CONFIRM=1", result.stdout)
        self.assertEqual(self.writes(), [])
        self.assertEqual(self.cluster(), before)
        self.assertFalse((self.tmp / "rollback").exists())

    def test_confirmed_cutover_routes_the_wave_to_new_and_scales_old_to_zero_keeping_definitions(self):
        result = self.make("cutover", "WAVE=1", "CONFIRM=1")
        self.assertEqual(result.returncode, 0, result.stderr)
        for app in ["app01", "app02"]:
            self.assertEqual(self.backend(app), f"{app}-via-new")
            self.assertEqual(self.replicas(app), 0)
            forward = self.cluster()[f"kind-old/EndpointSlice/{app}/{app}-via-new"]
            self.assertEqual(forward["endpoints"][0]["addresses"], ["172.18.0.9"])
        self.assertEqual((self.backend("app03"), self.replicas("app03")), ("app03", 2))
        recorded = json.loads((self.tmp / "rollback/wave-1.json").read_text())
        self.assertEqual(recorded["apps"]["app01"], {"replicas": 2, "backend": "app01"})

    def test_cutover_switches_routing_before_scaling_old_down(self):
        self.make("cutover", "WAVE=1", "CONFIRM=1")
        verbs = [next(w for w in c if w in WRITES) for c in self.writes()]
        self.assertLess(verbs.index("patch"), verbs.index("scale"))

    def test_cutover_twice_changes_nothing_the_second_time_and_keeps_the_recorded_state(self):
        self.make("cutover", "WAVE=1", "CONFIRM=1")
        self.log.write_text("")
        result = self.make("cutover", "WAVE=1", "CONFIRM=1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("already cut over", result.stdout)
        self.assertEqual(self.writes(), [])
        recorded = json.loads((self.tmp / "rollback/wave-1.json").read_text())
        self.assertEqual(recorded["apps"]["app02"]["replicas"], 2)

    def test_cutover_refuses_a_wave_that_is_not_healthy_on_new(self):
        self.state.write_text(json.dumps(two_clusters(self.gateway, wave1_health="Progressing")))
        result = self.make("cutover", "WAVE=1", "CONFIRM=1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not healthy on new", result.stderr)
        self.assertEqual(self.writes(), [])

    def test_rollback_without_confirm_prints_the_plan_and_changes_nothing(self):
        self.make("cutover", "WAVE=1", "CONFIRM=1")
        self.log.write_text("")
        result = self.make("rollback", "WAVE=1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("0 -> 2", result.stdout)
        self.assertIn("CONFIRM=1", result.stdout)
        self.assertEqual(self.writes(), [])
        self.assertEqual(self.backend("app01"), "app01-via-new")

    def test_rollback_restores_old_replicas_and_routing(self):
        self.make("cutover", "WAVE=1", "CONFIRM=1")
        self.log.write_text("")
        result = self.make("rollback", "WAVE=1", "CONFIRM=1")
        self.assertEqual(result.returncode, 0, result.stderr)
        for app in ["app01", "app02"]:
            self.assertEqual((self.backend(app), self.replicas(app)), (app, 2))
        self.assertFalse((self.tmp / "rollback/wave-1.json").exists())

    def test_rollback_waits_until_old_gateway_serves_the_wave_again(self):
        self.make("cutover", "WAVE=1", "CONFIRM=1")
        self.gateway.unready = 2
        result = self.make("rollback", "WAVE=1", "CONFIRM=1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("app01: old's gateway answers 200, served by old", result.stdout)
        self.assertIn("app02: old's gateway answers 200, served by old", result.stdout)

    def test_rollback_fails_and_keeps_its_state_if_old_gateway_never_serves(self):
        self.make("cutover", "WAVE=1", "CONFIRM=1")
        self.gateway.unready = 10**6
        result = self.make("rollback", "WAVE=1", "CONFIRM=1", CUTOVER_SERVE_TIMEOUT="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("still answers 503", result.stderr)
        self.assertTrue((self.tmp / "rollback/wave-1.json").exists())

    def test_rollback_brings_old_up_before_routing_back_to_it(self):
        self.make("cutover", "WAVE=1", "CONFIRM=1")
        self.log.write_text("")
        self.make("rollback", "WAVE=1", "CONFIRM=1")
        verbs = [next(w for w in c if w in WRITES) for c in self.writes()]
        self.assertEqual(verbs, ["scale", "scale", "patch", "patch"])

    def test_rollback_twice_is_safe(self):
        self.make("cutover", "WAVE=1", "CONFIRM=1")
        self.make("rollback", "WAVE=1", "CONFIRM=1")
        self.log.write_text("")
        result = self.make("rollback", "WAVE=1", "CONFIRM=1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Nothing to roll back", result.stdout)
        self.assertEqual(self.writes(), [])
        self.assertEqual((self.backend("app01"), self.replicas("app01")), ("app01", 2))

    def test_an_unknown_wave_fails_before_touching_a_cluster(self):
        result = self.make("cutover", "WAVE=9")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No wave '9'", result.stderr)
        self.assertEqual(self.log.read_text(), "")


if __name__ == "__main__":
    unittest.main()
