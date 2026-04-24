# Local Testing Guide (Windows 11)

## Prerequisites

- [Ollama for Windows](https://ollama.com/download) installed and running
- Conda installed (Anaconda or Miniconda)

---

## 1. Pull the LLM

```bash
ollama pull llama3.2:1b
```

Verify it's listed:
```bash
ollama list
```

> For higher quality responses (slower on CPU), use `llama3.2:3b` and update `OLLAMA_MODEL` in `config/settings.py`.

---

## 2. Create the conda environment

```bash
conda env create --prefix ./env -f environment.yml
conda activate ./env
```

To recreate from scratch:
```bash
conda env remove --prefix ./env
conda env create --prefix ./env -f environment.yml
```

---

## 3. Run the pipeline

Run these three steps in order. Steps 1 and 2 only need to run once (or after adding new artworks).

```bash
# Fetch ~23 artworks from Louvre API + Wikipedia (~5 min, ~150 HTTP requests)
python src/collect_data.py

# Embed and store in ChromaDB (~2 min)
python src/build_index.py

# Start Flask on http://localhost:5000
python src/app.py
```

To restart the API without re-collecting or re-indexing:
```bash
python src/app.py
```

---

## 4. Test the endpoints

### Health check
```bash
curl http://localhost:5000/health
```
Expected: `{"status": "ok", "ollama_reachable": true, ...}`

### List indexed artworks
```bash
curl http://localhost:5000/artworks
```

### Ask a question (French)
```bash
curl -X POST http://localhost:5000/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"message\": \"Où se trouve la Joconde ?\"}"
```

### Ask a question (English)
```bash
curl -X POST http://localhost:5000/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"message\": \"Who painted the Mona Lisa?\"}"
```

### Out-of-scope question (should return fallback, no LLM call)
```bash
curl -X POST http://localhost:5000/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"message\": \"Who won the World Cup in 2022?\"}"
```

### Multi-turn conversation
```bash
curl -X POST http://localhost:5000/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"message\": \"Tell me more about its artist\", \"conversation_history\": [{\"role\": \"user\", \"content\": \"Tell me about the Mona Lisa\"}, {\"role\": \"assistant\", \"content\": \"The Mona Lisa is a painting by Leonardo da Vinci...\"}]}"
```

---

## 5. Performance notes

| Situation | Expected response time |
|-----------|----------------------|
| CPU only (no GPU) | 1–3 min for first response, ~1 min after |
| With a GPU | 5–15 seconds |
| Out-of-scope question | < 1 second (no LLM call) |

If you hit a timeout, increase `LLM_TIMEOUT_SECONDS` in `config/settings.py` (currently 300s).

---

## 6. Key files to modify

| File | What to change |
|------|---------------|
| `config/settings.py` | Switch model, tune RAG parameters, adjust timeout |
| `prompts/system_prompt.txt` | Adjust the guide's persona and rules |
| `src/collect_data.py` | Add or remove artworks from the `ARTWORKS` dict |

---

## 7. Troubleshooting

**`404 Not Found` on `/chat`** — Model name in `config/settings.py` doesn't match `ollama list`. Update `OLLAMA_MODEL` to the exact tag shown.

**`Connection refused` on Ollama** — Ollama isn't running. Open the Ollama desktop app or run `ollama serve` in a separate terminal.

**`Read timed out`** — CPU inference is slow. Increase `LLM_TIMEOUT_SECONDS` in `config/settings.py` or switch to the 1B model.

**Empty or missing fields in `data/raw/artworks.json`** — Some Louvre ARK IDs may have changed. Check the fallback warnings printed by `collect_data.py` and update the `ARTWORKS` dict in `src/collect_data.py`.

**ChromaDB collection not found** — Run `python src/build_index.py` before starting the API.
