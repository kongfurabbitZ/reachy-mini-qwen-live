import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from reachy_mini_qwen_live import config


class SettingsTest(unittest.TestCase):
    def test_secret_is_local_redacted_and_reloaded(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "cfg" / "config.json"
            with patch.object(config, "CONFIG_DIR", path.parent), patch.object(config, "CONFIG_PATH", path):
                settings = config.Settings()
                settings.update({"workspace_id": "ws-test123", "api_key": "unit-test-secret"})
                self.assertNotIn("unit-test-secret", str(settings.public()))
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
                self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
                self.assertEqual(config.Settings().workspace_id, "ws-test123")
                self.assertTrue(config.Settings().public()["api_key_configured"])

    def test_workspace_id_cannot_change_signaling_host(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "config.json"
            with patch.object(config, "CONFIG_DIR", path.parent), patch.object(config, "CONFIG_PATH", path):
                with self.assertRaises(ValueError):
                    config.Settings().update({"workspace_id": "evil.example.com/path"})
                self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
