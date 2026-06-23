#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

if [[ ! -d ".venv" ]]; then
  echo "Creating virtual environment..."
  "$PYTHON_BIN" -m venv .venv
fi

echo "Activating virtual environment..."
source ".venv/bin/activate"

echo "Installing/updating dependencies..."
pip install -r requirements.txt

if [[ ! -f ".env" ]]; then
  echo "No .env file found. Creating one from .env.example..."
  cp .env.example .env
  echo "Please edit .env and add your API keys, then run ./run.sh again."
  exit 1
fi

echo "Checking required environment variables..."
set +u
source ".env"
set -u

if [[ -z "${ELEVENLABS_API_KEY:-}" ]]; then
  echo "ELEVENLABS_API_KEY is missing in .env"
  exit 1
fi

if [[ "${LLM_PROVIDER:-mock}" == "openai" && -z "${OPENAI_API_KEY:-}" ]]; then
  echo "OPENAI_API_KEY is required when LLM_PROVIDER=openai"
  exit 1
fi

if [[ "${LLM_PROVIDER:-mock}" == "anthropic" && -z "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic"
  exit 1
fi

if [[ "${LLM_PROVIDER:-mock}" == "groq" && -z "${GROQ_API_KEY:-}" ]]; then
  echo "GROQ_API_KEY is required when LLM_PROVIDER=groq (free key: https://console.groq.com/keys )"
  exit 1
fi

if [[ "${LLM_PROVIDER:-mock}" == "gemini" ]]; then
  if [[ -z "${GEMINI_API_KEY:-}" && -z "${GOOGLE_API_KEY:-}" ]]; then
    echo "GEMINI_API_KEY or GOOGLE_API_KEY is required when LLM_PROVIDER=gemini (https://aistudio.google.com/apikey )"
    exit 1
  fi
fi

echo "Starting API server on http://${HOST}:${PORT}"
echo "Web UI:    http://127.0.0.1:${PORT}/"
echo "Swagger:   http://${HOST}:${PORT}/docs"
echo "ReDoc:     http://${HOST}:${PORT}/redoc"
exec uvicorn app.main:app --reload --host "$HOST" --port "$PORT"
