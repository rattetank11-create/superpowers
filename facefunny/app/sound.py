"""Subtle interface sounds, synthesised at start-up (no audio files shipped).

If Qt Multimedia is not available on the system the app keeps working silently.
"""

from __future__ import annotations

import logging
import math
import os
import struct
import tempfile
import wave
from typing import Dict, List, Tuple

from PySide6.QtCore import QObject, QUrl

log = logging.getLogger(__name__)

SAMPLE_RATE = 44100

# name -> list of (start_hz, end_hz, duration_s) segments
_SOUNDS: Dict[str, List[Tuple[float, float, float]]] = {
    "click": [(1400, 1100, 0.035)],
    "connect": [(520, 520, 0.07), (780, 780, 0.07), (1040, 1250, 0.14)],
    "start": [(660, 660, 0.06), (990, 990, 0.09)],
    "pause": [(990, 990, 0.06), (620, 620, 0.09)],
    "reset": [(1200, 500, 0.16)],
    "error": [(240, 200, 0.12)],
}


def _synth(path: str, segments: List[Tuple[float, float, float]], volume: float = 0.35) -> None:
    frames = bytearray()
    phase = 0.0
    for f0, f1, dur in segments:
        n = int(SAMPLE_RATE * dur)
        attack = max(1, int(n * 0.08))
        for i in range(n):
            t = i / n
            freq = f0 + (f1 - f0) * t
            phase += 2 * math.pi * freq / SAMPLE_RATE
            env = min(1.0, i / attack) * (1.0 - t) ** 1.6
            sample = math.sin(phase) * 0.8 + math.sin(phase * 2) * 0.2
            frames += struct.pack("<h", int(sample * env * volume * 32767))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(bytes(frames))


class SoundManager(QObject):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.enabled = True
        self._effects: Dict[str, object] = {}
        self._dir = None
        try:
            from PySide6.QtMultimedia import QSoundEffect  # noqa: WPS433 (optional module)
        except Exception as exc:  # ImportError or missing system libraries
            log.info("Sound disabled: Qt Multimedia unavailable (%s)", exc)
            return
        try:
            self._dir = tempfile.TemporaryDirectory(prefix="facefunny_snd_")
            for name, segments in _SOUNDS.items():
                path = os.path.join(self._dir.name, f"{name}.wav")
                _synth(path, segments)
                effect = QSoundEffect(self)
                effect.setSource(QUrl.fromLocalFile(path))
                effect.setVolume(0.22)
                self._effects[name] = effect
        except Exception as exc:
            log.warning("Sound disabled: %s", exc)
            self._effects.clear()

    @property
    def available(self) -> bool:
        return bool(self._effects)

    def toggle(self) -> bool:
        self.enabled = not self.enabled
        return self.enabled

    def close(self) -> None:
        """Stop sounds and delete the temporary WAV files."""
        for effect in self._effects.values():
            try:
                effect.stop()
            except Exception:
                pass
        self._effects.clear()
        if self._dir is not None:
            self._dir.cleanup()
            self._dir = None

    def play(self, name: str) -> None:
        if not self.enabled:
            return
        effect = self._effects.get(name)
        if effect is None:
            return
        try:
            effect.play()
        except Exception as exc:  # never let audio break the UI
            log.debug("Could not play %s: %s", name, exc)
