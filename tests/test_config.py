import json
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

    def test_region_selects_a_fixed_signaling_host_and_survives_reload(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "config.json"
            with patch.object(config, "CONFIG_DIR", path.parent), patch.object(config, "CONFIG_PATH", path):
                settings = config.Settings()
                self.assertEqual(settings.region, "cn-beijing")
                settings.update({"workspace_id": "ws-test123", "region": "ap-southeast-1"})
                reloaded = config.Settings()
                self.assertEqual(reloaded.public()["region"], "ap-southeast-1")
                self.assertEqual(reloaded.signaling_url(),
                                 "https://ws-test123.ap-southeast-1.maas.aliyuncs.com"
                                 "/api/v1/webrtc/realtime?model=qwen3.8-omni-flash-realtime")
                with self.assertRaises(ValueError):
                    reloaded.update({"region": "evil.example.com", "workspace_id": "ws-changed"})
                self.assertEqual(reloaded.workspace_id, "ws-test123")
                self.assertEqual(config.Settings().region, "ap-southeast-1")

    def test_existing_config_without_region_keeps_beijing_default(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "config.json"
            path.write_text(json.dumps({"api_key": "unit-test-secret", "workspace_id": "ws-test123"}))
            with patch.object(config, "CONFIG_DIR", path.parent), patch.object(config, "CONFIG_PATH", path):
                settings = config.Settings()
                self.assertEqual(settings.region, "cn-beijing")
                self.assertIn(".cn-beijing.maas.aliyuncs.com", settings.signaling_url())


if __name__ == "__main__":
    unittest.main()
