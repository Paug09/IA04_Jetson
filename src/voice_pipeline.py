"""
Full voice pipeline orchestrator: audio → STT → RAG → TTS → audio.

Sits on top of RAGPipeline (text-only). Lazily loads Whisper so the Flask
app can start even if transformers/torch are missing.
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.rag_pipeline import RAGPipeline
from src import tts

log = logging.getLogger(__name__)


class VoicePipeline:
    def __init__(self, rag: RAGPipeline):
        self.rag = rag
        self._stt = None

    def _ensure_stt(self):
        if self._stt is None:
            from src.stt import stt as stt_singleton
            self._stt = stt_singleton
        return self._stt

    # ------------------------------------------------------------------
    # Voice chat: audio in → audio out
    # ------------------------------------------------------------------

    def voice_chat(self, audio, language: str = None, history: list = None) -> dict:
        """
        Full pipeline:
          1. Whisper transcribes audio
          2. RAG pipeline answers the transcribed text
          3. espeak-ng synthesizes the answer
        Returns dict including transcript, answer, sources, audio_bytes.
        """
        stt = self._ensure_stt()

        log.info("Transcribing audio ...")
        transcript = stt.transcribe(audio, language=language)
        log.info("Transcript: %s", transcript["text"])

        if not transcript["text"]:
            return {
                "transcript": transcript,
                "answer": "",
                "sources": [],
                "audio_bytes": None,
                "error": "empty_transcript",
            }

        # Detected language from Whisper informs TTS voice
        resolved_lang = language or transcript.get("language", "fr")
        if resolved_lang == "auto":
            resolved_lang = self.rag._detect_language(transcript["text"])

        log.info("Querying RAG pipeline ...")
        rag_result = self.rag.query(
            transcript["text"],
            language=resolved_lang,
            history=history or [],
        )

        log.info("Synthesizing response ...")
        audio_bytes = tts.synthesize(rag_result["answer"], lang=resolved_lang)

        return {
            "transcript": transcript,
            "answer": rag_result["answer"],
            "sources": rag_result["sources"],
            "language": resolved_lang,
            "out_of_scope": rag_result.get("out_of_scope", False),
            "audio_bytes": audio_bytes,
        }
