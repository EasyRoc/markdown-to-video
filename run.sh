#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: ./run.sh <markdown-file>"
    echo ""
    echo "Environment:"
    echo "  DEEPSEEK_API_KEY   DeepSeek API key (required)"
    echo ""
    echo "Example:"
    echo "  export DEEPSEEK_API_KEY=sk-xxx"
    echo "  ./run.sh article.md"
    exit 1
fi

MD_FILE="$1"

if [ ! -f "$MD_FILE" ]; then
    echo "Error: file not found: $MD_FILE"
    exit 1
fi

if [ -z "${DEEPSEEK_API_KEY:-}" ]; then
    echo "Error: DEEPSEEK_API_KEY is not set"
    echo "  export DEEPSEEK_API_KEY=sk-xxx"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "==> Generating video from: $MD_FILE"
echo ""

python main.py "$MD_FILE" --v3 --llm 2>&1

echo ""
echo "==> Done! Output: output/$(basename "$MD_FILE" | sed 's/\.[^.]*$//').mp4"
