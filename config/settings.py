import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent

# --- Paths ---
RAW_DATA_PATH = BASE_DIR / "data" / "raw" / "artworks.json"
CHUNKS_PATH = BASE_DIR / "data" / "processed" / "chunks.json"
CHROMA_DB_PATH = str(BASE_DIR / "data" / "chroma_db")
SYSTEM_PROMPT_PATH = BASE_DIR / "prompts" / "system_prompt.txt"

# --- Models ---
EMBEDDING_MODEL = "intfloat/multilingual-e5-small"
# OLLAMA_MODEL = "llama3.2:3b" # For final version with better performance
OLLAMA_MODEL = "llama3.2:1b"  # For testing with smaller model
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

# --- ChromaDB ---
CHROMA_COLLECTION = "louvre_artworks"

# --- RAG parameters ---
TOP_K_RETRIEVAL = 5
MAX_ARTWORKS_IN_CONTEXT = 3
# Cosine distance threshold: chunks above this are considered irrelevant
RELEVANCE_THRESHOLD = 0.45

# Number of past conversation turns to include in prompt
MAX_HISTORY_TURNS = 3

# --- Ollama inference parameters ---
LLM_TEMPERATURE = 0.3
LLM_NUM_CTX = 2048        # use 4096 on Jetson with 3B model
LLM_NUM_PREDICT = 200     # use 512 on Jetson with 3B model
LLM_TIMEOUT_SECONDS = 300  # CPU inference is slow; increase if still timing out

# --- Flask ---
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5000
FLASK_DEBUG = False

# --- Data collection ---
REQUEST_DELAY_SECONDS = 1.0
LOUVRE_BASE_URL = "https://collections.louvre.fr"
WIKIPEDIA_REST_URL = "https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}"

# --- Speech-to-Text (Whisper) ---
# tiny   = 39M params, ~150MB  → good for Jetson
# base   = 74M params, ~290MB
# small  = 244M params, ~970MB → too heavy for Jetson alongside LLM
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "openai/whisper-tiny")
WHISPER_LANGUAGE = None  # None = auto-detect; "fr" or "en" to force

# --- Text-to-Speech (espeak-ng) ---
TTS_RATE = 120          # words per minute — slow for retro MacinTalk feel
TTS_PITCH = 35          # 0-99, lower = deeper
TTS_AMPLITUDE = 80      # 0-200
TTS_TARGET_SR = 8000    # Hz — 8kHz = lo-fi 1984 Mac vibe; None for full quality

# --- Audio recording (voice CLI) ---
MIC_SAMPLE_RATE = 16000  # Whisper expects 16kHz
MIC_CHANNELS = 1
MIC_DEFAULT_DURATION = 5.0  # seconds
