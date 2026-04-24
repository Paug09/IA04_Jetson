"""
Flask API for the Louvre museum chatbot.

Endpoints:
  GET  /health       — service status
  GET  /artworks     — catalog of indexed artworks
  POST /chat         — text in, text out
  POST /stt          — audio in, transcript out
  POST /tts          — text in, WAV out
  POST /voice-chat   — audio in, audio + transcript + answer out
"""

import base64
import io
import logging
import sys
import tempfile
from pathlib import Path

import requests as http_requests
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import FLASK_HOST, FLASK_PORT, FLASK_DEBUG, OLLAMA_MODEL
from src.rag_pipeline import RAGPipeline
from src.voice_pipeline import VoicePipeline
from src import tts as tts_module

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

log.info("Initializing RAG pipeline ...")
try:
    pipeline = RAGPipeline()
except ValueError as e:
    log.error("ChromaDB collection not found: %s", e)
    log.error("Run `python src/build_index.py` first.")
    sys.exit(1)

voice = VoicePipeline(pipeline)
log.info("Flask app ready (voice endpoints available on demand).")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "model": OLLAMA_MODEL,
        "index_size": pipeline.index_size(),
        "ollama_reachable": pipeline.ollama_reachable(),
    })


@app.get("/artworks")
def artworks():
    return jsonify({"artworks": pipeline.list_artworks()})


@app.post("/chat")
def chat():
    body = request.get_json(silent=True) or {}
    message = (body.get("message") or "").strip()

    if not message:
        return jsonify({"error": "empty_message", "message": "Le message ne peut pas être vide."}), 400

    language = body.get("language")  # optional; auto-detected if absent
    history = body.get("conversation_history", [])

    try:
        result = pipeline.query(message, language=language, history=history)
        return jsonify(result)
    except (TimeoutError, http_requests.exceptions.ReadTimeout):
        return jsonify({
            "error": "ollama_timeout",
            "message": "Le modèle met trop de temps à répondre. Veuillez réessayer.",
        }), 503
    except Exception as e:
        log.exception("Unexpected error during /chat")
        return jsonify({"error": "internal_error", "message": str(e)}), 500


# ---------------------------------------------------------------------------
# Voice endpoints
# ---------------------------------------------------------------------------

def _save_uploaded_audio_to_tempfile() -> str:
    """Accepts either multipart 'audio' file or raw body; returns temp path."""
    if "audio" in request.files:
        f = request.files["audio"]
        suffix = Path(f.filename or "audio.wav").suffix or ".wav"
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        f.save(tmp.name)
        return tmp.name
    if request.data:
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.write(request.data)
        tmp.close()
        return tmp.name
    return None


@app.post("/stt")
def stt_endpoint():
    """Audio in (multipart file 'audio' or raw body), returns {text, language, model}."""
    path = _save_uploaded_audio_to_tempfile()
    if not path:
        return jsonify({"error": "no_audio", "message": "No audio uploaded."}), 400

    language = request.args.get("language")
    try:
        from src.stt import stt
        result = stt.transcribe(path, language=language)
        return jsonify(result)
    except Exception as e:
        log.exception("STT error")
        return jsonify({"error": "stt_failed", "message": str(e)}), 500
    finally:
        try:
            Path(path).unlink()
        except OSError:
            pass


@app.post("/tts")
def tts_endpoint():
    """Text in (JSON {"text": ..., "lang": ...}), returns WAV bytes."""
    body = request.get_json(silent=True) or {}
    text = (body.get("text") or "").strip()
    lang = body.get("lang", "fr")

    if not text:
        return jsonify({"error": "empty_text", "message": "text is required."}), 400

    try:
        wav_bytes = tts_module.synthesize(text, lang=lang)
        return send_file(
            io.BytesIO(wav_bytes),
            mimetype="audio/wav",
            as_attachment=False,
            download_name="speech.wav",
        )
    except tts_module.TTSError as e:
        return jsonify({"error": "tts_failed", "message": str(e)}), 500


@app.post("/voice-chat")
def voice_chat_endpoint():
    """
    Full voice pipeline: audio in → transcript + answer + audio out.

    Returns JSON with base64-encoded WAV in 'audio_base64'.
    Use ?raw=1 to stream WAV directly instead.
    """
    path = _save_uploaded_audio_to_tempfile()
    if not path:
        return jsonify({"error": "no_audio", "message": "No audio uploaded."}), 400

    language = request.args.get("language")
    try:
        result = voice.voice_chat(path, language=language)

        if result.get("error"):
            return jsonify(result), 400

        audio_bytes = result.pop("audio_bytes")

        if request.args.get("raw") == "1":
            return send_file(
                io.BytesIO(audio_bytes),
                mimetype="audio/wav",
                as_attachment=False,
                download_name="response.wav",
            )

        result["audio_base64"] = base64.b64encode(audio_bytes).decode("ascii")
        return jsonify(result)
    except (TimeoutError, http_requests.exceptions.ReadTimeout):
        return jsonify({"error": "ollama_timeout", "message": "LLM timeout."}), 503
    except Exception as e:
        log.exception("voice-chat error")
        return jsonify({"error": "internal_error", "message": str(e)}), 500
    finally:
        try:
            Path(path).unlink()
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)
