"""Qwen Omni Realtime WebRTC signaling and session events."""
import asyncio
import json
import logging
import ssl
import threading
import time
from collections import deque

import aiohttp
import certifi
from aiortc import RTCConfiguration, RTCPeerConnection, RTCSessionDescription
from aiortc.mediastreams import MediaStreamError

from .audio import Microphone, Speaker

LOG = logging.getLogger(__name__)


class Session:
    def __init__(self, media, settings, mini):
        self.media, self.settings, self.mini = media, settings, mini
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        self.state = "未连接"
        self.error = ""
        self.events = deque(maxlen=40)
        self.lock = threading.Lock()
        self.pc = self.mic = self.speaker = self.play_task = None
        self.user_speaking_until = 0.0
        self.wobbling = False

    def _loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def _set(self, state, error=""):
        with self.lock:
            self.state, self.error = state, error

    def status(self):
        with self.lock:
            return {"state": self.state, "error": self.error, "events": list(self.events),
                    "user_speaking": time.monotonic() < self.user_speaking_until,
                    "robot_speaking": bool(self.speaker and time.monotonic() < self.speaker.speaking_until)}

    def _event(self, role, content):
        if content:
            with self.lock:
                self.events.append({"role": role, "content": str(content)[:1000]})

    def start(self):
        if not self.settings.api_key or not self.settings.workspace_id:
            raise ValueError("请先填写所选地域的 API Key 和业务空间 ID")
        if self.state not in ("未连接", "连接失败"):
            raise ValueError("会话已经启动")
        self._set("连接中")
        future = asyncio.run_coroutine_threadsafe(self._connect(), self.loop)
        try:
            future.result(timeout=40)
        except Exception as exc:
            future.cancel()
            # No server response body or request headers are included in the message.
            message = str(exc) if isinstance(exc, ValueError) else "连接失败；请检查网络、地域、业务空间和 Key"
            LOG.warning("Qwen connect failed: %s", type(exc).__name__)
            self._set("连接失败", message)
            raise ValueError(message) from None
        return self.status()

    async def _connect(self):
        self.mic = Microphone(self.media)
        self.speaker = Speaker(self.media)
        self.pc = RTCPeerConnection(RTCConfiguration(iceServers=[]))
        pc, mic, speaker = self.pc, self.mic, self.speaker
        pc.addTrack(mic)
        pc.createDataChannel("oai-events")

        @pc.on("datachannel")
        def on_datachannel(channel):
            if channel.label != "txt":
                return

            @channel.on("message")
            def on_message(raw):
                try:
                    event = json.loads(raw)
                except (TypeError, ValueError):
                    return
                kind = event.get("type", "")
                if kind == "session.created":
                    channel.send(json.dumps({"type": "session.update", "session": {
                        "modalities": ["text", "audio"],
                        "voice": self.settings.voice,
                        "instructions": self.settings.instructions,
                        "input_audio_format": "pcm", "output_audio_format": "pcm",
                        "turn_detection": {"type": "server_vad", "threshold": 0.5, "silence_duration_ms": 800},
                        "enable_input_audio_transcription": True}}, ensure_ascii=False))
                elif kind == "session.updated":
                    mic.enabled = True
                    self._set("对话中")
                    if self.settings.motion_enabled and not self.wobbling:
                        try:
                            self.mini.enable_wobbling()
                            self.wobbling = True
                        except Exception:
                            LOG.exception("Could not enable head wobble")
                elif kind == "input_audio_buffer.speech_started":
                    self.user_speaking_until = time.monotonic() + 1.5
                    speaker.clear()
                elif kind == "conversation.item.input_audio_transcription.completed":
                    self._event("你", event.get("transcript", ""))
                elif kind == "response.audio_transcript.done":
                    self._event("千问", event.get("transcript", ""))
                elif kind == "error":
                    # API error details can contain sensitive request data; show generic guidance.
                    self._set("连接失败", "千问服务返回错误；请检查 Key、模型权限和会话配置")

        @pc.on("track")
        def on_track(track):
            if track.kind == "audio":
                self.play_task = asyncio.create_task(self._play(track, speaker))

        @pc.on("connectionstatechange")
        async def on_state():
            if pc.connectionState in ("failed", "disconnected"):
                self._set("连接失败", "WebRTC 连接中断")
                await self._close()

        try:
            offer = await pc.createOffer()
            await pc.setLocalDescription(offer)
            for _ in range(100):
                if pc.iceGatheringState == "complete":
                    break
                await asyncio.sleep(0.1)
            if pc.iceGatheringState != "complete":
                raise ValueError("本机 ICE 收集超时")
            url = self.settings.signaling_url()
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=25)) as client:
                async with client.post(url, data=pc.localDescription.sdp.encode(), headers={
                    "Content-Type": "application/sdp", "Authorization": f"Bearer {self.settings.api_key}"
                }, ssl=ssl.create_default_context(cafile=certifi.where())) as response:
                    if response.status != 200:
                        raise ValueError(f"百炼信令失败（HTTP {response.status}）；请检查 Key、地域和业务空间")
                    answer = await response.text()
            answer = answer.strip().replace("\r\n", "\n").replace("\n", "\r\n") + "\r\n"
            await pc.setRemoteDescription(RTCSessionDescription(sdp=answer, type="answer"))
            speaker.start()
            mic.start()
            self._set("等待千问会话")
        except Exception:
            await self._close()
            raise

    async def _play(self, track, speaker):
        try:
            while True:
                speaker.feed(await track.recv())
        except (MediaStreamError, asyncio.CancelledError):
            pass
        except Exception:
            LOG.exception("Speaker playback failed")

    async def _close(self):
        if self.play_task:
            self.play_task.cancel()
            self.play_task = None
        if self.mic:
            self.mic.stop()
            self.mic = None
        if self.speaker:
            self.speaker.stop()
            self.speaker = None
        if self.pc:
            await self.pc.close()
            self.pc = None
        if self.wobbling:
            try:
                self.mini.disable_wobbling()
            except Exception:
                LOG.exception("Could not disable head wobble")
            self.wobbling = False

    def stop(self):
        asyncio.run_coroutine_threadsafe(self._close(), self.loop).result(timeout=10)
        self._set("未连接")
        return self.status()

    def shutdown(self):
        self.stop()
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=2)
