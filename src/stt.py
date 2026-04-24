"""
Speech-to-Text via Whisper (transformers pipeline).

Loads whisper-tiny by default (~150MB, runs on CPU). Uses GPU if available.
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import WHISPER_MODEL, WHISPER_LANGUAGE

log = logging.getLogger(__name__)


class STT:
    def __init__(self, model_name: str = None):
        self.model_name = model_name or WHISPER_MODEL
        self._pipeline = None  # lazy-loaded — avoids slow import at Flask startup
        self._device = None

    def _load(self):
        if self._pipeline is not None:
            return

        import torch
        from transformers import pipeline

        if torch.cuda.is_available():
            self._device = "cuda:0"
            dtype = torch.float16
        else:
            self._device = "cpu"
            dtype = torch.float32

        log.info("Loading Whisper (%s) on %s ...", self.model_name, self._device)
        self._pipeline = pipeline(
            "automatic-speech-recognition",
            model=self.model_name,
            torch_dtype=dtype,
            device=self._device,
        )
        log.info("Whisper ready.")

    def transcribe(self, audio, language: str = None) -> dict:
        """
        Transcribe audio from a file path, URL, or numpy array/bytes.

        Returns: {"text": str, "language": str, "model": str}
        """
        self._load()

        lang = language or WHISPER_LANGUAGE
        generate_kwargs = {"language": lang} if lang else {}

        result = self._pipeline(audio, generate_kwargs=generate_kwargs)
        text = result["text"].strip()

        return {
            "text": text,
            "language": lang or "auto",
            "model": self.model_name,
        }

    def is_loaded(self) -> bool:
        return self._pipeline is not None


# Singleton — import this from other modules
stt = STT()
