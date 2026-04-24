# IA04_Jetson

Assistant vocal de musée embarqué — répond en français ou en anglais à des questions sur les œuvres du Louvre, grâce à un pipeline RAG + LLM local sur NVIDIA Jetson Orin Nano 8GB.

## Pipeline

```text
🎙️  mic  →  Whisper (STT)  →  RAG (ChromaDB + e5)  →  Llama 3.2 (Ollama)  →  espeak-ng (TTS)  →  🔊  haut-parleur
```

Tout tourne localement sur le Jetson, sans connexion internet en inférence.

## Stack

| Composant | Choix |
|-----------|-------|
| LLM | Llama 3.2 (1B/3B) via Ollama |
| Embeddings | multilingual-e5-small |
| Vector store | ChromaDB |
| STT | Whisper-tiny (transformers) |
| TTS | espeak-ng (formant synth, retro MacinTalk) |
| API | Flask |
| Données | Louvre Collections API + Wikipedia (~24 œuvres + vue générale du musée) |

## Démarrage rapide

```bash
# 1. Setup
conda env create --prefix ./env -f environment.yml
conda activate ./env

# 2. Sur Jetson : Ollama + libs audio système (espeak-ng, portaudio)
bash scripts/setup_ollama.sh

# 3. Build RAG index
python src/collect_data.py
python src/build_index.py

# 4. Serve Flask
python src/app.py

# 5. (option) Terminal voix : press Enter → speak → Enter
python src/voice_cli.py
```

## Documentation

- [LOCAL_TESTING.md](LOCAL_TESTING.md) — setup Windows 11 local (conda + Ollama)
- [JETSON_SETUP.md](JETSON_SETUP.md) — SSH, NoMachine, déploiement sur Jetson
- [VOICE_PIPELINE.md](VOICE_PIPELINE.md) — architecture STT/TTS, endpoints, presets

## Matériel

- NVIDIA Jetson Orin Nano 8GB (JetPack 6.x)
- Microphone USB, haut-parleur

## Musée

Louvre — 24 œuvres emblématiques (peintures, sculptures, antiquités) + article musée général sur Wikipedia.
