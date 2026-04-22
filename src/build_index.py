"""
Reads data/raw/artworks.json, creates thematic text chunks per artwork,
embeds them with multilingual-e5-small, and stores everything in ChromaDB.

Run: python src/build_index.py
"""

import json
import sys
import logging
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import (
    RAW_DATA_PATH,
    CHUNKS_PATH,
    CHROMA_DB_PATH,
    CHROMA_COLLECTION,
    EMBEDDING_MODEL,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def _make_chunks(artwork: dict) -> list[dict]:
    """Produces 4-5 thematic text chunks from one artwork record."""
    a = artwork
    chunks = []

    def add(chunk_type: str, text: str, lang: str):
        text = text.strip()
        if text:
            chunks.append({
                "id": f"{a['id']}_{chunk_type}",
                "text": text,
                "chunk_type": chunk_type,
                "language": lang,
                "artwork_id": a["id"],
                "title_fr": a.get("title_fr", ""),
                "title_en": a.get("title_en", ""),
                "artist": a.get("artist", ""),
                "department": a.get("department", ""),
                "location": a.get("location", ""),
                "ark": a.get("ark", ""),
                "louvre_url": a.get("louvre_url", ""),
            })

    # Identity chunk — always generated, used for location / technique queries
    identity_parts = [
        f"{a.get('title_fr') or a.get('title_en', '?')} "
        f"({a.get('title_en') or a.get('title_fr', '')})",
    ]
    if a.get("artist"):
        identity_parts.append(f"est une œuvre de {a['artist']}")
    if a.get("date"):
        identity_parts.append(f"datée de {a['date']}")
    if a.get("location"):
        identity_parts.append(f"Elle se trouve dans {a['location']} au Musée du Louvre")
    if a.get("technique"):
        identity_parts.append(f"Technique : {a['technique']}")
    if a.get("dimensions"):
        identity_parts.append(f"Dimensions : {a['dimensions']}")
    if a.get("department"):
        identity_parts.append(f"Département : {a['department']}")
    if a.get("school"):
        identity_parts.append(f"École : {a['school']}")
    if a.get("period"):
        identity_parts.append(f"Période : {a['period']}")
    if a.get("inventory_number"):
        identity_parts.append(f"N° d'inventaire : {a['inventory_number']}")

    add("identity", ". ".join(identity_parts) + ".", "fr")

    # Louvre descriptions
    add("description_fr", a.get("louvre_description_fr", ""), "fr")
    add("description_en", a.get("louvre_description_en", ""), "en")

    # Wikipedia summaries
    add("context_fr", a.get("wikipedia_summary_fr", ""), "fr")
    add("context_en", a.get("wikipedia_summary_en", ""), "en")

    return chunks


def build_chunks(artworks: list[dict]) -> list[dict]:
    all_chunks = []
    for artwork in artworks:
        all_chunks.extend(_make_chunks(artwork))
    return all_chunks


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------

def embed_passages(texts: list[str], model: SentenceTransformer) -> list[list[float]]:
    # E5 models require "passage: " prefix at index time
    prefixed = [f"passage: {t}" for t in texts]
    embeddings = model.encode(
        prefixed,
        normalize_embeddings=True,
        batch_size=32,
        show_progress_bar=True,
    )
    return embeddings.tolist()


# ---------------------------------------------------------------------------
# ChromaDB ingestion
# ---------------------------------------------------------------------------

def build_chroma_index(chunks: list[dict], embeddings: list[list[float]]):
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

    # Drop and recreate collection for a clean rebuild
    try:
        client.delete_collection(CHROMA_COLLECTION)
        log.info("Dropped existing collection '%s'", CHROMA_COLLECTION)
    except Exception:
        pass

    collection = client.create_collection(
        name=CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )

    ids = [c["id"] for c in chunks]
    documents = [c["text"] for c in chunks]
    metadatas = [
        {
            "artwork_id": c["artwork_id"],
            "title_fr": c["title_fr"],
            "title_en": c["title_en"],
            "artist": c["artist"],
            "department": c["department"],
            "location": c["location"],
            "chunk_type": c["chunk_type"],
            "language": c["language"],
            "ark": c["ark"],
            "louvre_url": c["louvre_url"],
        }
        for c in chunks
    ]

    collection.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
    log.info("Indexed %d chunks into ChromaDB collection '%s'", len(chunks), CHROMA_COLLECTION)
    return collection


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # Load raw data
    if not RAW_DATA_PATH.exists():
        log.error("Raw data not found at %s — run src/collect_data.py first", RAW_DATA_PATH)
        sys.exit(1)

    with open(RAW_DATA_PATH, encoding="utf-8") as f:
        raw = json.load(f)

    artworks = raw["artworks"]
    log.info("Loaded %d artworks from %s", len(artworks), RAW_DATA_PATH)

    # Build chunks
    chunks = build_chunks(artworks)
    log.info("Generated %d chunks", len(chunks))

    # Save chunks for inspection
    CHUNKS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CHUNKS_PATH, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
    log.info("Saved chunks to %s", CHUNKS_PATH)

    # Load embedding model
    log.info("Loading embedding model '%s' ...", EMBEDDING_MODEL)
    model = SentenceTransformer(EMBEDDING_MODEL)

    # Embed
    texts = [c["text"] for c in chunks]
    log.info("Embedding %d passages ...", len(texts))
    embeddings = embed_passages(texts, model)

    # Build index
    Path(CHROMA_DB_PATH).mkdir(parents=True, exist_ok=True)
    build_chroma_index(chunks, embeddings)

    log.info("\nIndex built successfully. ChromaDB at: %s", CHROMA_DB_PATH)


if __name__ == "__main__":
    main()
