"""Capture click: a synthesized 30 ms tick. Played with winsound (stdlib) - no QtMultimedia needed."""
from __future__ import annotations

import io
import logging
import math
import struct
import wave

from .resources import asset_path

log = logging.getLogger(__name__)

SAMPLE_RATE = 44100
DURATION_S = 0.030


def synth_click_wav_bytes(sample_rate: int = SAMPLE_RATE, duration: float = DURATION_S) -> bytes:
    """A soft, short tick: two decaying sine partials with a fast attack, 16-bit mono PCM."""
    n = int(sample_rate * duration)
    frames = bytearray()
    for i in range(n):
        t = i / sample_rate
        env = math.exp(-t * 140.0) * min(1.0, i / 24.0)
        v = 0.55 * math.sin(2 * math.pi * 1900 * t) + 0.25 * math.sin(2 * math.pi * 3800 * t)
        sample = int(max(-1.0, min(1.0, v * env)) * 32767 * 0.6)
        frames += struct.pack("<h", sample)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(bytes(frames))
    return buf.getvalue()


_WAV_BYTES: bytes | None = None


def _wav_bytes() -> bytes:
    global _WAV_BYTES
    if _WAV_BYTES is None:
        path = asset_path("click.wav")
        try:
            _WAV_BYTES = path.read_bytes() if path.exists() else synth_click_wav_bytes()
        except OSError:
            _WAV_BYTES = synth_click_wav_bytes()
    return _WAV_BYTES


def play_click() -> None:
    try:
        import winsound

        winsound.PlaySound(_wav_bytes(), winsound.SND_MEMORY | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
    except Exception as exc:  # pragma: no cover
        log.debug("play_click failed: %s", exc)
