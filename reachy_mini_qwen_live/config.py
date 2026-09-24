"""Local-only configuration. Never expose or log the API key."""
import json
import os
import re
from pathlib import Path
from platformdirs import user_config_dir

MODEL = "qwen3.8-omni-flash-realtime"
DEFAULT_REGION = "cn-beijing"
REGION_DOMAINS = {
    "cn-beijing": "cn-beijing.maas.aliyuncs.com",
    "ap-southeast-1": "ap-southeast-1.maas.aliyuncs.com",
}
CONFIG_DIR = Path(user_config_dir("reachy_mini_qwen_live"))
CONFIG_PATH = CONFIG_DIR / "config.json"
WORKSPACE_RE = re.compile(r"^[A-Za-z0-9-]{3,100}$")


class Settings:
    def __init__(self):
        data = json.loads(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else {}
        self.api_key = data.get("api_key", "")
        self.workspace_id = data.get("workspace_id", "")
        self.region = data.get("region", DEFAULT_REGION)
        if self.region not in REGION_DOMAINS:
            self.region = DEFAULT_REGION
        self.voice = data.get("voice", "Tina")
        self.instructions = data.get("instructions", "你是 Reachy Mini。用简洁、自然的中文与用户交谈。")
        self.motion_enabled = data.get("motion_enabled", True)

    def public(self):
        return {"api_key_configured": bool(self.api_key), "workspace_id": self.workspace_id,
                "voice": self.voice, "instructions": self.instructions,
                "motion_enabled": self.motion_enabled, "model": MODEL, "region": self.region}

    def signaling_url(self):
        return (f"https://{self.workspace_id}.{REGION_DOMAINS[self.region]}"
                f"/api/v1/webrtc/realtime?model={MODEL}")

    def update(self, data):
        region = data.get("region")
        if region is not None and region not in REGION_DOMAINS:
            raise ValueError("请选择支持的百炼服务地域")
        workspace = data.get("workspace_id")
        if workspace is not None:
            workspace = workspace.strip()
            if workspace and not WORKSPACE_RE.fullmatch(workspace):
                raise ValueError("业务空间 ID 只能包含字母、数字和连字符")
            self.workspace_id = workspace
        key = data.get("api_key")
        if key is not None and key.strip():
            self.api_key = key.strip()
        if data.get("clear_api_key"):
            self.api_key = ""
        if region is not None:
            self.region = region
        voice = data.get("voice")
        if voice is not None:
            if voice not in ("Tina", "Cherry", "Chelsie"):
                raise ValueError("不支持该音色")
            self.voice = voice
        instructions = data.get("instructions")
        if instructions is not None:
            self.instructions = instructions.strip()[:4000]
        motion = data.get("motion_enabled")
        if motion is not None:
            self.motion_enabled = bool(motion)
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        os.chmod(CONFIG_DIR, 0o700)
        tmp = CONFIG_PATH.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            os.chmod(tmp, 0o600)
            json.dump({name: getattr(self, name) for name in
                       ("api_key", "workspace_id", "region", "voice", "instructions", "motion_enabled")}, handle, ensure_ascii=False)
        os.replace(tmp, CONFIG_PATH)
