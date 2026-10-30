# Gemini Agent & CLI Instructions for CodeBin

## System Protocol
This repository utilizes **CodeBin** to cache symbol AST definitions into a binary store (`.codebin/symbols.bin`).

## Agent Directives:
1. When asked about code behavior, invoke `codebin_lookup` or use CLI `python scripts/codebin_engine.py lookup <symbol>` to fetch signatures and docstrings.
2. When searching for features across the codebase, call `codebin_search` or CLI `python scripts/codebin_engine.py search "<keyword>"`.
3. CodeBin handles cross-platform locking and zlib payload compression transparently.
4. Keep the binary index synchronized after editing files with `python scripts/codebin_engine.py scan`.
