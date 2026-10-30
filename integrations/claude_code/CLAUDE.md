# CLAUDE.md — CodeBin Agent Configuration for Claude Code

This file defines build commands, architecture guidelines, and tool usage for Claude Code.

## Quick Commands
- **Scan Codebase:** `python scripts/codebin_engine.py scan`
- **Lookup Symbol:** `python scripts/codebin_engine.py lookup <symbol_name>`
- **Search Keywords:** `python scripts/codebin_engine.py search "<query>"`
- **Run Tests:** `python scripts/test_codebin.py`
- **Run Security Tests:** `python scripts/test_security_codebin.py`
- **Compact Index:** `python scripts/codebin_engine.py compact`

## Working Rules for Claude Code
- **Never re-read multiple files to find function signatures.** Use `codebin_lookup` or CLI `python scripts/codebin_engine.py lookup` first.
- **Respect .codebin:** `.codebin/symbols.bin` and `.codebin/symbols.idx.json` are binary and index files managed automatically by `codebin_engine.py`. Do not edit them by hand.
- **Zero Runtime Dependencies:** The core engine relies strictly on the Python standard library (`ast`, `struct`, `hashlib`, `json`, `zlib`, `urllib`). Do not introduce external dependencies without explicit approval.
