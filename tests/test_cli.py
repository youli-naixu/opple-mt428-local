import os
import subprocess
import sys
import unittest
from pathlib import Path


class CliTests(unittest.TestCase):
    def test_bilingual_help_with_non_chinese_console_encoding(self):
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "cp1252:strict"
        result = subprocess.run([sys.executable, "-m", "opple_mt428", "--help"], cwd=Path(__file__).resolve().parents[1], env=env, capture_output=True, encoding="utf-8", timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("局域网", result.stdout)
        self.assertIn("LAN discovery", result.stdout)

    def test_hardware_requires_explicit_identity_before_any_network(self):
        result = subprocess.run([sys.executable, "-m", "opple_mt428", "serve"], cwd=Path(__file__).resolve().parents[1], capture_output=True, encoding="utf-8", timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires explicit --ip and --mac", result.stderr)


if __name__ == "__main__":
    unittest.main()
