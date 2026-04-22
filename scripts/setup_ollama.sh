#!/bin/bash
# Installs Ollama and pulls the LLM model for Jetson Orin Nano.
# Run once after first boot on the Jetson.
set -e

echo "=== Installing Ollama (Linux ARM64) ==="
curl -fsSL https://ollama.com/install.sh | sh

echo "=== Starting Ollama service in background ==="
ollama serve &
OLLAMA_PID=$!
sleep 5

echo "=== Pulling Llama 3.2 3B Q4_K_M ==="
ollama pull llama3.2:3b-instruct-q4_K_M

echo "=== Installed models ==="
ollama list

echo ""
echo "Ollama is running on http://localhost:11434 (PID $OLLAMA_PID)"
echo "To run as a system service: sudo systemctl enable ollama && sudo systemctl start ollama"
