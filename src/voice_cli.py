"""
Terminal voice loop: press Enter to record, speak, press Enter again to stop.
Transcribes with Whisper, queries RAG, plays back with espeak-ng.

Run: python src/voice_cli.py
"""

import argparse
import io
import logging
import sys
import tempfile
from pathlib import Path

import numpy as np
from scipy.io import wavfile

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import MIC_SAMPLE_RATE, MIC_CHANNELS, MIC_DEFAULT_DURATION
from src.rag_pipeline import RAGPipeline
from src.voice_pipeline import VoicePipeline
from src import tts as tts_module

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)


def record_fixed(duration_s: float) -> str:
    """Record for a fixed duration. Returns path to temp WAV file."""
    import sounddevice as sd

    print(f"🎙️  Recording for {duration_s:.1f}s ... speak now.")
    audio = sd.rec(
        int(duration_s * MIC_SAMPLE_RATE),
        samplerate=MIC_SAMPLE_RATE,
        channels=MIC_CHANNELS,
        dtype="int16",
    )
    sd.wait()
    print("✓ captured.")

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    wavfile.write(tmp.name, MIC_SAMPLE_RATE, audio)
    return tmp.name


def record_push_to_talk() -> str:
    """Record until Enter is pressed a second time."""
    import queue
    import sounddevice as sd
    import threading

    q = queue.Queue()
    chunks = []

    def callback(indata, frames, time_info, status):
        if status:
            log.debug("status: %s", status)
        q.put(indata.copy())

    stream = sd.InputStream(
        samplerate=MIC_SAMPLE_RATE,
        channels=MIC_CHANNELS,
        dtype="int16",
        callback=callback,
    )

    print("🎙️  Recording ... press Enter to stop.")

    stop_event = threading.Event()

    def drain():
        while not stop_event.is_set():
            try:
                chunks.append(q.get(timeout=0.1))
            except queue.Empty:
                continue

    t = threading.Thread(target=drain, daemon=True)

    with stream:
        t.start()
        try:
            input()
        finally:
            stop_event.set()
            t.join(timeout=1.0)

    if not chunks:
        print("(no audio captured)")
        return None

    audio = np.concatenate(chunks, axis=0)
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    wavfile.write(tmp.name, MIC_SAMPLE_RATE, audio)
    print(f"✓ captured {len(audio) / MIC_SAMPLE_RATE:.1f}s.")
    return tmp.name


def main():
    parser = argparse.ArgumentParser(description="Voice CLI for the Louvre RAG chatbot")
    parser.add_argument("--duration", type=float, default=None,
                        help="Fixed recording duration in seconds. Default: push-to-talk.")
    parser.add_argument("--language", type=str, default=None,
                        help="Force language ('fr' or 'en'). Default: auto-detect.")
    parser.add_argument("--text-only", action="store_true",
                        help="Skip audio playback, print answer only.")
    args = parser.parse_args()

    print("Initializing pipeline ...")
    try:
        rag = RAGPipeline()
    except ValueError as e:
        print(f"ChromaDB error: {e}")
        print("Run `python src/build_index.py` first.")
        sys.exit(1)

    voice = VoicePipeline(rag)
    print("Ready.\n")
    print("Press Enter to speak, Ctrl+C to quit.\n")

    try:
        while True:
            input()  # wait for user to press Enter to start
            if args.duration:
                wav_path = record_fixed(args.duration)
            else:
                wav_path = record_push_to_talk()
            if wav_path is None:
                continue

            try:
                result = voice.voice_chat(wav_path, language=args.language)
            finally:
                Path(wav_path).unlink(missing_ok=True)

            if result.get("error"):
                print(f"✗ {result['error']}\n")
                continue

            print(f"👤 You said ({result['transcript']['language']}): "
                  f"{result['transcript']['text']}")
            print(f"🖼️  Guide: {result['answer']}")
            if result["sources"]:
                srcs = ", ".join(s["artwork_id"] for s in result["sources"])
                print(f"   (sources: {srcs})")
            print()

            if not args.text_only and result.get("audio_bytes"):
                tts_module.play_bytes(result["audio_bytes"])
            print()

    except KeyboardInterrupt:
        print("\nBye.")


if __name__ == "__main__":
    main()
