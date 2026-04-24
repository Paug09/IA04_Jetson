"""
RAG pipeline: user query → embed → retrieve from ChromaDB → prompt → Ollama → answer.

Loaded once at Flask startup; shared across requests.
"""

import sys
import logging
from pathlib import Path

import chromadb
import requests as http_requests
from langdetect import detect, LangDetectException
from sentence_transformers import SentenceTransformer

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import (
    CHROMA_DB_PATH,
    CHROMA_COLLECTION,
    EMBEDDING_MODEL,
    OLLAMA_MODEL,
    OLLAMA_URL,
    SYSTEM_PROMPT_PATH,
    TOP_K_RETRIEVAL,
    MAX_ARTWORKS_IN_CONTEXT,
    RELEVANCE_THRESHOLD,
    MAX_HISTORY_TURNS,
    LLM_TEMPERATURE,
    LLM_NUM_CTX,
    LLM_NUM_PREDICT,
    LLM_TIMEOUT_SECONDS,
)

log = logging.getLogger(__name__)

FALLBACK_RESPONSES = {
    "fr": (
        "Je suis désolé, je ne dispose pas d'informations sur ce sujet dans ma base de données. "
        "Je peux vous parler des œuvres emblématiques du Louvre comme la Joconde, la Vénus de Milo "
        "ou la Victoire de Samothrace. Souhaitez-vous en savoir plus sur l'une d'elles ?"
    ),
    "en": (
        "I'm sorry, I don't have information about that in my knowledge base. "
        "I can tell you about iconic Louvre artworks such as the Mona Lisa, the Venus de Milo, "
        "or the Winged Victory of Samothrace. Would you like to learn more about one of them?"
    ),
}


class RAGPipeline:
    def __init__(self):
        log.info("Loading embedding model '%s' ...", EMBEDDING_MODEL)
        self.embed_model = SentenceTransformer(EMBEDDING_MODEL)

        log.info("Connecting to ChromaDB at %s ...", CHROMA_DB_PATH)
        client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        self.collection = client.get_collection(CHROMA_COLLECTION)
        log.info("ChromaDB collection loaded: %d chunks", self.collection.count())

        self.system_prompt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()

        if not self.ollama_reachable():
            log.warning("Ollama is not reachable at %s — /chat will fail until it starts", OLLAMA_URL)

        log.info("RAG pipeline ready.")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def query(self, message: str, language: str = None, history: list[dict] = None) -> dict:
        lang = language or self._detect_language(message)
        retrieved = self._retrieve(message)

        if not retrieved:
            return {
                "answer": FALLBACK_RESPONSES.get(lang, FALLBACK_RESPONSES["en"]),
                "sources": [],
                "language_detected": lang,
                "model_used": None,
                "out_of_scope": True,
            }

        context_text = self._format_context(retrieved, lang)
        prompt = self._build_prompt(context_text, message, history or [])
        answer = self._call_ollama(prompt)

        return {
            "answer": answer,
            "sources": [
                {
                    "artwork_id": r["metadata"]["artwork_id"],
                    "title_fr": r["metadata"]["title_fr"],
                    "title_en": r["metadata"]["title_en"],
                    "chunk_type": r["metadata"]["chunk_type"],
                    "relevance_score": round(1 - r["distance"], 3),
                }
                for r in retrieved
            ],
            "language_detected": lang,
            "model_used": OLLAMA_MODEL,
            "out_of_scope": False,
        }

    def index_size(self) -> int:
        return self.collection.count()

    def list_artworks(self) -> list[dict]:
        """Returns deduplicated artwork catalog from ChromaDB metadata."""
        result = self.collection.get(where={"chunk_type": {"$eq": "identity"}})
        seen = {}
        for meta in result["metadatas"]:
            aid = meta["artwork_id"]
            if aid not in seen:
                seen[aid] = {
                    "id": aid,
                    "title_fr": meta["title_fr"],
                    "title_en": meta["title_en"],
                    "artist": meta.get("artist", ""),
                    "department": meta["department"],
                    "location": meta["location"],
                    "louvre_url": meta.get("louvre_url", ""),
                }
        return list(seen.values())

    def ollama_reachable(self) -> bool:
        try:
            r = http_requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _detect_language(self, text: str) -> str:
        try:
            lang = detect(text)
            return lang if lang in ("fr", "en") else "fr"
        except LangDetectException:
            return "fr"

    def _embed_query(self, text: str) -> list[float]:
        # E5 requires "query: " prefix at query time
        embedding = self.embed_model.encode(
            f"query: {text}",
            normalize_embeddings=True,
        )
        return embedding.tolist()

    def _retrieve(self, query: str) -> list[dict]:
        embedding = self._embed_query(query)
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=TOP_K_RETRIEVAL,
            include=["documents", "metadatas", "distances"],
        )

        if not results["documents"] or not results["documents"][0]:
            return []

        chunks = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            # ChromaDB cosine distance: 0 = identical, 2 = opposite
            # Normalize to [0,1]: dist/2
            normalized_dist = dist / 2.0
            if normalized_dist <= RELEVANCE_THRESHOLD:
                chunks.append({"text": doc, "metadata": meta, "distance": normalized_dist})

        if not chunks:
            return []

        # Deduplicate: keep best chunk per artwork_id, cap at MAX_ARTWORKS_IN_CONTEXT
        best_per_artwork: dict[str, dict] = {}
        for chunk in sorted(chunks, key=lambda c: c["distance"]):
            aid = chunk["metadata"]["artwork_id"]
            if aid not in best_per_artwork:
                best_per_artwork[aid] = chunk
            if len(best_per_artwork) >= MAX_ARTWORKS_IN_CONTEXT:
                break

        return list(best_per_artwork.values())

    def _format_context(self, retrieved: list[dict], lang: str) -> str:
        parts = []
        for r in retrieved:
            meta = r["metadata"]
            title = meta["title_fr"] if lang == "fr" else meta["title_en"]
            fallback_title = meta["title_en"] if lang == "fr" else meta["title_fr"]
            display = title or fallback_title
            parts.append(f"[Source : {display}]\n{r['text']}")
            log.info("  retrieved chunk: %s / %s (dist=%.3f)",
                     meta["artwork_id"], meta["chunk_type"], r["distance"])
        return "\n\n".join(parts)

    def _build_prompt(self, context: str, question: str, history: list[dict]) -> str:
        # Include last N turns of conversation history
        history_text = ""
        if history:
            recent = history[-(MAX_HISTORY_TURNS * 2):]
            lines = []
            for turn in recent:
                role = "Visiteur" if turn.get("role") == "user" else "Guide"
                lines.append(f"{role} : {turn.get('content', '')}")
            history_text = "\n".join(lines) + "\n\n"

        return (
            f"=== INFORMATIONS SUR LES ŒUVRES (utilisez uniquement ceci pour répondre) ===\n\n"
            f"{context}\n\n"
            f"=== FIN DES INFORMATIONS ===\n\n"
            f"{history_text}"
            f"Visiteur : {question}\n\n"
            f"Guide :"
        )

    def _call_ollama(self, prompt: str) -> str:
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "system": self.system_prompt,
            "stream": False,
            "options": {
                "temperature": LLM_TEMPERATURE,
                "top_p": 0.9,
                "num_ctx": LLM_NUM_CTX,
                "num_predict": LLM_NUM_PREDICT,
                "stop": ["<|eot_id|>", "Visiteur :", "Visitor:"],
            },
        }
        log.info("Sending request to Ollama (model=%s, timeout=%ds) ...", OLLAMA_MODEL, LLM_TIMEOUT_SECONDS)
        r = http_requests.post(
            f"{OLLAMA_URL}/api/generate",
            json=payload,
            timeout=LLM_TIMEOUT_SECONDS,
        )
        try:
            r.raise_for_status()
            answer = r.json()["response"].strip()
        except (http_requests.exceptions.HTTPError, KeyError, ValueError) as e:
            log.error("Ollama error: %s", e)
            raise
        log.info("Ollama responded (%d chars)", len(answer))
        return answer
