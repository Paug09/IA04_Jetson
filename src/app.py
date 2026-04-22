"""
Flask API for the Louvre museum chatbot.

Endpoints:
  GET  /health     — service status
  GET  /artworks   — catalog of indexed artworks
  POST /chat       — ask a question about Louvre artworks
"""

import logging
import sys
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import FLASK_HOST, FLASK_PORT, FLASK_DEBUG, OLLAMA_MODEL
from src.rag_pipeline import RAGPipeline

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

log.info("Initializing RAG pipeline ...")
pipeline = RAGPipeline()
log.info("Flask app ready.")


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
    except TimeoutError:
        return jsonify({
            "error": "ollama_timeout",
            "message": "Le modèle met trop de temps à répondre. Veuillez réessayer.",
        }), 503
    except Exception as e:
        log.exception("Unexpected error during /chat")
        return jsonify({"error": "internal_error", "message": str(e)}), 500


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)
