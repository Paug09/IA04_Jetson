#!/bin/bash
# System-level setup for the Jetson Orin Nano:
#   - Ollama + Llama 3.2 pull
#   - espeak-ng (TTS)
#   - PortAudio + libsndfile (microphone + audio file I/O)
# Run once after first boot on the Jetson.
set -e

echo "=== Installing system audio libraries ==="
sudo apt update
sudo apt install -y \
    espeak-ng \
    libportaudio2 portaudio19-dev \
    libsndfile1 \
    ffmpeg

echo "=== Installing Ollama (Linux ARM64) ==="
if ! command -v ollama &> /dev/null; then
    curl -fsSL https://ollama.com/install.sh | sh
fi

echo "=== Starting Ollama service ==="
if ! pgrep -x ollama > /dev/null; then
    ollama serve &
    sleep 5
fi

# Default = 1b for Jetson; switch to 3b in config/settings.py once validated
MODEL="${OLLAMA_MODEL:-llama3.2:1b}"
echo "=== Pulling $MODEL ==="
ollama pull "$MODEL"

echo "=== Installed models ==="
ollama list

echo ""
echo "✓ System ready. Ollama: http://localhost:11434"
echo "  To run Ollama as a systemd service:"
echo "    sudo systemctl enable ollama && sudo systemctl start ollama"
