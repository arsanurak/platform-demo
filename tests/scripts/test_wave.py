import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


class WaveTargetTest(unittest.TestCase):
    def test_an_unknown_wave_fails_before_touching_a_cluster_and_lists_the_waves(self):
        result = subprocess.run(["make", "-s", "wave-9"], cwd=REPO_ROOT, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No wave '9'", result.stderr)
        self.assertIn("wave-1 wave-2 wave-3", result.stderr)


if __name__ == "__main__":
    unittest.main()
