# Voice Pipeline — STT + TTS

Full audio loop: microphone → Whisper → RAG → Llama → espeak-ng → speaker.

## Architecture

```
                    ┌────────────────────────┐
User voice  ───►    │  Whisper (tiny)        │  ──►  transcript
                    └────────────────────────┘
                               │
                               ▼
                    ┌────────────────────────┐
                    │  RAG pipeline          │
                    │  • embed               │
                    │  • ChromaDB retrieve   │
                    │  • Ollama (Llama 3.2)  │
                    └────────────────────────┘
                               │
                               ▼
                    ┌────────────────────────┐
Speaker     ◄───    │  espeak-ng             │  ──► WAV (8kHz retro)
                    └────────────────────────┘
```

## Modules

| File | Role |
|------|------|
| `src/stt.py` | Whisper wrapper. Singleton, lazy-loaded. |
| `src/tts.py` | espeak-ng wrapper. Retro formant settings. |
| `src/voice_pipeline.py` | Orchestrator: audio → STT → RAG → TTS. |
| `src/voice_cli.py` | Terminal loop. Push-to-talk via Enter key. |
| `src/app.py` | Flask endpoints: `/stt`, `/tts`, `/voice-chat`. |

## Install

### Windows (local testing)
```bash
# espeak-ng MSI from https://github.com/espeak-ng/espeak-ng/releases
# Then in the conda env:
pip install -r requirements.txt
```

### Jetson Orin Nano
```bash
bash scripts/setup_ollama.sh    # installs espeak-ng + portaudio + ollama
pip install -r requirements.txt
```

## Usage

### Terminal loop (simplest)
```bash
python src/voice_cli.py
# Press Enter → speak → press Enter → hear the answer
# Ctrl+C to exit

# Fixed 5-second recording instead of push-to-talk
python src/voice_cli.py --duration 5

# Text-only (no audio playback)
python src/voice_cli.py --text-only
```

### HTTP API

**Transcribe only:**
```bash
curl -X POST http://localhost:5000/stt \
  -F "audio=@my_question.wav"
# → {"text": "Où se trouve la Joconde", "language": "auto", "model": "openai/whisper-tiny"}
```

**Synthesize only:**
```bash
curl -X POST http://localhost:5000/tts \
  -H "Content-Type: application/json" \
  -d '{"text": "Bienvenue au musée du Louvre.", "lang": "fr"}' \
  --output response.wav
```

**Full voice chat (audio in, audio out):**
```bash
curl -X POST "http://localhost:5000/voice-chat?raw=1" \
  -F "audio=@my_question.wav" \
  --output response.wav

# Or JSON with base64-encoded audio + metadata:
curl -X POST http://localhost:5000/voice-chat \
  -F "audio=@my_question.wav"
```

## Tuning the voice

Edit `config/settings.py`:

```python
# --- Speech-to-Text ---
WHISPER_MODEL = "openai/whisper-tiny"    # tiny | base | small
WHISPER_LANGUAGE = None                   # "fr" / "en" to force, None = auto

# --- Text-to-Speech (retro MacinTalk feel) ---
TTS_RATE = 120          # words per minute — lower = slower, more retro
TTS_PITCH = 35          # 0-99 — lower = deeper voice
TTS_AMPLITUDE = 80      # volume, 0-200
TTS_TARGET_SR = 8000    # Hz — 8000 for 1984 Mac lo-fi; None for full quality
```

Experiment with presets in `notebooks/tts_retro_experiment.ipynb`.

## Performance notes

| Component | CPU (Windows) | Jetson (GPU) |
|-----------|--------------|--------------|
| Whisper tiny | 1–3s / 5s audio | < 1s |
| RAG retrieve | < 100ms | < 100ms |
| Ollama 1B | 2–10s | 1–3s |
| espeak-ng | instant | instant |
| **End-to-end** | 5–15s | 2–5s |

## Troubleshooting

**`espeak-ng not found`** — install via MSI (Windows) or `apt install espeak-ng` (Jetson). Restart terminal.

**`No module named 'sounddevice'`** — `pip install sounddevice`. On Jetson also needs `sudo apt install portaudio19-dev`.

**Microphone not detected** — `python -c "import sounddevice; print(sounddevice.query_devices())"` and set default device in OS settings.

**Whisper hallucinates silence as speech** — set a minimum audio threshold or use a voice activation detector. Whisper tiny is more prone to this than larger models.

**Slow Whisper on Windows** — normal on CPU. Use `WHISPER_MODEL="openai/whisper-tiny"` and keep recordings short (< 10s).
