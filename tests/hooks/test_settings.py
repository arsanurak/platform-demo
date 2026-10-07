"""The committed agent settings must actually wire both guards in."""

import json
import os
import unittest

from tests.hooks.helpers import HOOKS_DIR, REPO_ROOT

SETTINGS = REPO_ROOT / ".claude" / "settings.json"


def pre_tool_use_entries():
    settings = json.loads(SETTINGS.read_text())
    return settings["hooks"]["PreToolUse"]


def matchers_running(hook_name):
    return [
        entry["matcher"]
        for entry in pre_tool_use_entries()
        for hook in entry["hooks"]
        if hook_name in hook["command"]
    ]


class SettingsTest(unittest.TestCase):
    def test_secret_guard_runs_on_file_and_shell_tools(self):
        matchers = "|".join(matchers_running("secret_guard.py")).split("|")
        for tool in ("Bash", "Read", "Write", "Edit", "MultiEdit", "NotebookEdit"):
            with self.subTest(tool=tool):
                self.assertIn(tool, matchers)

    def test_command_guard_runs_on_bash(self):
        self.assertIn("Bash", "|".join(matchers_running("command_guard.py")).split("|"))

    def test_every_hook_command_points_at_an_executable_script(self):
        for entry in pre_tool_use_entries():
            for hook in entry["hooks"]:
                name = hook["command"].split("/")[-1].strip('"')
                with self.subTest(hook=name):
                    self.assertTrue(os.access(HOOKS_DIR / name, os.X_OK))


if __name__ == "__main__":
    unittest.main()
