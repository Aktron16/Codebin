#!/bin/bash
# Allows the AI assistant to self-configure paths during session start
export PYTHONPATH="${PYTHONPATH}:$(pwd)/scripts"
chmod +x scripts/*.py 2>/dev/null || true
echo "CodeBin environment initialized successfully."
