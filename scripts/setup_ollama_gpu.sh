#!/usr/bin/env bash
set -euo pipefail

# GPU-focused Ollama setup for ScholarOS.
# - Verifies NVIDIA GPU visibility
# - Installs zstd when possible
# - Ensures Ollama service is running
# - Pulls a large model appropriate for 32GB-class GPUs
# - Verifies GPU-backed execution

MODEL_DEFAULT="qwen2.5:32b"
OLLAMA_URL="http://localhost:11434"

echo "============================================================"
echo "Ollama GPU Setup for ScholarOS"
echo "============================================================"
echo

install_zstd() {
  if command -v zstd >/dev/null 2>&1; then
    echo "zstd already installed"
    return
  fi

  echo "Installing zstd..."
  if command -v apt-get >/dev/null 2>&1; then
    apt-get update && apt-get install -y zstd
  elif command -v dnf >/dev/null 2>&1; then
    dnf install -y zstd
  elif command -v yum >/dev/null 2>&1; then
    yum install -y zstd
  elif command -v pacman >/dev/null 2>&1; then
    pacman -S --noconfirm zstd
  else
    echo "No supported package manager detected. Install zstd manually."
    return 1
  fi
}

echo "Step 1: Checking GPU"
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
else
  echo "nvidia-smi not found. Ollama will run on CPU unless GPU runtime is configured."
fi
echo

echo "Step 2: Checking zstd"
install_zstd || true
echo

echo "Step 3: Checking Ollama installation"
if command -v ollama >/dev/null 2>&1; then
  ollama --version
else
  echo "Installing Ollama..."
  curl -fsSL https://ollama.com/install.sh | sh
  ollama --version
fi
echo

echo "Step 4: Ensuring Ollama service"
if curl -fsS "${OLLAMA_URL}/api/tags" >/dev/null 2>&1; then
  echo "Ollama API already available at ${OLLAMA_URL}"
else
  if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files | grep -q '^ollama\.service'; then
    systemctl start ollama
    sleep 3
  else
    nohup ollama serve >/tmp/ollama-serve.log 2>&1 &
    sleep 3
  fi
fi

curl -fsS "${OLLAMA_URL}/api/tags" >/dev/null

echo
echo "Step 5: Pulling model ${MODEL_DEFAULT}"
ollama pull "${MODEL_DEFAULT}"
echo

echo "Step 6: GPU execution verification"
ollama run "${MODEL_DEFAULT}" "Respond with exactly: {\"ok\": true}" >/tmp/ollama-gpu-smoke.txt
sleep 1
ollama ps || true
nvidia-smi --query-compute-apps=pid,process_name,used_gpu_memory --format=csv,noheader || true

echo
echo "============================================================"
echo "Ollama GPU setup complete"
echo "Model ready: ${MODEL_DEFAULT}"
echo "Set env: export OLLAMA_MODEL=${MODEL_DEFAULT}"
echo "============================================================"
