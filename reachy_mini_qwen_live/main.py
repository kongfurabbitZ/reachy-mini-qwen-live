"""Reachy Mini app entry point and local settings API."""
import math
import ipaddress
import sys
import threading
import time

import numpy as np
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from reachy_mini import ReachyMini, ReachyMiniApp

from .config import Settings
from .realtime import Session


class ConfigUpdate(BaseModel):
    api_key: str | None = None
    workspace_id: str | None = None
    voice: str | None = None
    instructions: str | None = Field(default=None, max_length=4000)
    motion_enabled: bool | None = None
    clear_api_key: bool = False


class ReachyMiniQwenLive(ReachyMiniApp):
    # The daemon reads this literal for its dashboard link. On the Mac running
    # Control we bind only to loopback; Wireless/Linux needs LAN access.
    custom_app_url: str | None = "http://0.0.0.0:8043"
    request_media_backend: str | None = None

    def __init__(self, *args, **kwargs):
        if sys.platform == "darwin":
            self.custom_app_url = "http://127.0.0.1:8043"
        super().__init__(*args, **kwargs)
        if self.settings_app is not None:
            @self.settings_app.middleware("http")
            async def local_only(request: Request, call_next):
                client = request.client.host if request.client else ""
                try:
                    address = ipaddress.ip_address(client)
                    allowed = address.is_loopback or (sys.platform != "darwin" and address.is_private)
                except ValueError:
                    allowed = False
                if not allowed:
                    return JSONResponse({"detail": "设置页仅供本机或受信任的局域网访问"}, status_code=403)
                return await call_next(request)

    def run(self, reachy_mini: ReachyMini, stop_event: threading.Event):
        settings = Settings()
        session = Session(reachy_mini.media, settings, reachy_mini)
        app = self.settings_app
        assert app is not None

        @app.get("/api/config")
        def get_config():
            return settings.public()

        @app.post("/api/config")
        def set_config(body: ConfigUpdate):
            if session.state not in ("未连接", "连接失败"):
                raise HTTPException(409, "请先结束当前会话")
            try:
                settings.update(body.model_dump(exclude_none=True))
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from None
            return settings.public()

        @app.get("/api/status")
        def get_status():
            return session.status()

        @app.post("/api/start")
        def start():
            try:
                return session.start()
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from None

        @app.post("/api/stop")
        def stop():
            return session.stop()

        # Only the app's running simulator is driven in this deployment. On a physical
        # robot, confirm free space and the stop button before enabling this option.
        started = time.monotonic()
        last_motion = 0.0
        try:
            while not stop_event.wait(0.05):
                if not settings.motion_enabled or time.monotonic() - last_motion < 0.12:
                    continue
                last_motion = time.monotonic()
                status = session.status()
                phase = time.monotonic() - started
                if status["user_speaking"]:
                    antennas = np.deg2rad([11.0, -11.0])
                elif status["robot_speaking"]:
                    sway = 12.0 * math.sin(phase * 6)
                    antennas = np.deg2rad([sway, -sway])
                else:
                    breathe = 5.0 * math.sin(phase * 1.7)
                    antennas = np.deg2rad([breathe, -breathe])
                reachy_mini.set_target(antennas=antennas)
        finally:
            session.shutdown()


if __name__ == "__main__":
    app = ReachyMiniQwenLive()
    try:
        app.wrapped_run()
    except KeyboardInterrupt:
        app.stop()
