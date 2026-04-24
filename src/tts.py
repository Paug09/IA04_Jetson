"""
Text-to-Speech via espeak-ng — formant synthesis, retro MacinTalk sound.

Returns WAV bytes. Settings tuned for the 1984 Mac "Fred" vibe:
low pitch, slow rate, 8kHz downsampling.
"""

import logging
import os
import shutil
import subprocess
import sys
import tempfile
from math import gcd
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import TTS_RATE, TTS_PITCH, TTS_AMPLITUDE, TTS_TARGET_SR

log = logging.getLogger(__name__)


class TTSError(RuntimeError):
    pass


def _ensure_espeak():
    if shutil.which("espeak-ng") is None:
        raise TTSError(
            "espeak-ng not found. Install it:\n"
            "  Windows: download MSI from github.com/espeak-ng/espeak-ng/releases\n"
            "  Jetson:  sudo apt install espeak-ng"
        )


def synthesize(
    text: str,
    lang: str = "fr",
    rate: int = None,
    pitch: int = None,
    amplitude: int = None,
    target_sr: int = None,
) -> bytes:
    """
    Returns WAV bytes. Raises TTSError if espeak-ng is missing or fails.
    """
    _ensure_espeak()

    if not text or not text.strip():
        raise TTSError("text is empty")

    rate = rate if rate is not None else TTS_RATE
    pitch = pitch if pitch is not None else TTS_PITCH
    amplitude = amplitude if amplitude is not None else TTS_AMPLITUDE
    target_sr = target_sr if target_sr is not None else TTS_TARGET_SR

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        out_path = f.name

    try:
        result = subprocess.run(
            [
                "espeak-ng",
                "-v", lang,
                "-s", str(rate),
                "-p", str(pitch),
                "-a", str(amplitude),
                "-w", out_path,
                text,
            ],
            capture_output=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise TTSError(f"espeak-ng failed: {result.stderr.decode(errors='replace')}")

        if target_sr:
            sr, data = wavfile.read(out_path)
            if sr != target_sr:
                g = gcd(target_sr, sr)
                data = resample_poly(data.astype(np.float32), target_sr // g, sr // g)
                wavfile.write(out_path, target_sr, data.astype(np.int16))

        with open(out_path, "rb") as f:
            return f.read()
    finally:
        try:
            os.unlink(out_path)
        except OSError:
            pass


def play_bytes(wav_bytes: bytes):
    """Play WAV bytes through the default audio device (for CLI use)."""
    try:
        import io
        import sounddevice as sd
        sr, data = wavfile.read(io.BytesIO(wav_bytes))
        sd.play(data, sr)
        sd.wait()
    except ImportError:
        raise TTSError("sounddevice not installed — pip install sounddevice")
