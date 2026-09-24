"""Reachy media-to-WebRTC bridge for Qwen RTP audio."""
import asyncio
import logging
import threading
import time
from fractions import Fraction

import av
import numpy as np
from aiortc.mediastreams import MediaStreamError, MediaStreamTrack

LOG = logging.getLogger(__name__)


class Microphone(MediaStreamTrack):
    kind = "audio"

    def __init__(self, media):
        super().__init__()
        self.media = media
        self.rate = int(media.get_input_audio_samplerate())
        self.frame_size = self.rate // 50
        self.buffer = np.zeros(0, dtype=np.float32)
        self.lock = threading.Lock()
        self.done = threading.Event()
        self.worker = threading.Thread(target=self._pump, daemon=True)
        self.started_at = None
        self.pts = 0
        self.enabled = False

    def start(self):
        self.media.start_recording()
        self.worker.start()

    def _pump(self):
        while not self.done.is_set():
            try:
                chunk = self.media.get_audio_sample()
            except Exception:
                LOG.exception("Microphone read failed")
                chunk = None
            if chunk is None or len(chunk) == 0:
                time.sleep(0.005)
                continue
            samples = np.asarray(chunk, dtype=np.float32)
            mono = samples.mean(axis=1) if samples.ndim == 2 else samples.reshape(-1)
            with self.lock:
                self.buffer = np.concatenate((self.buffer, mono))[-self.rate // 4:]

    async def recv(self):
        if self.readyState != "live":
            raise MediaStreamError
        if self.started_at is None:
            self.started_at = time.monotonic()
        else:
            self.pts += self.frame_size
            await asyncio.sleep(max(0, self.started_at + self.pts / self.rate - time.monotonic()))
        with self.lock:
            if self.enabled and self.buffer.size >= self.frame_size:
                samples = self.buffer[:self.frame_size]
                self.buffer = self.buffer[self.frame_size:]
            else:
                samples = np.zeros(self.frame_size, dtype=np.float32)
        pcm = np.clip(samples * 32767, -32768, 32767).astype(np.int16)
        frame = av.AudioFrame.from_ndarray(pcm.reshape(1, -1), format="s16", layout="mono")
        frame.sample_rate = self.rate
        frame.pts = self.pts
        frame.time_base = Fraction(1, self.rate)
        return frame

    def stop(self):
        self.done.set()
        super().stop()
        if self.worker.is_alive():
            self.worker.join(timeout=1)
        self.media.stop_recording()


class Speaker:
    def __init__(self, media):
        self.media = media
        rate = int(media.get_output_audio_samplerate())
        self.resampler = av.AudioResampler(format="s16", layout="mono", rate=rate)
        self.started = False
        self.speaking_until = 0.0

    def start(self):
        self.media.start_playing()
        self.started = True

    def feed(self, frame):
        if not self.started:
            return
        for item in self.resampler.resample(frame):
            samples = item.to_ndarray().reshape(-1).astype(np.float32) / 32768.0
            if samples.size:
                if np.max(np.abs(samples)) > 0.01:
                    self.speaking_until = time.monotonic() + 0.4
                self.media.push_audio_sample(samples)

    def clear(self):
        clear = getattr(getattr(self.media, "audio", None), "clear_player", None)
        if callable(clear):
            clear()

    def stop(self):
        if self.started:
            self.started = False
            self.media.stop_playing()
