# GitHub Copilot Instructions for CodeBin

When working inside this repository, GitHub Copilot should use **CodeBin** to understand functions, classes, and types without re-reading source files.

## Guidelines for Copilot:
1. **Symbol Lookups:**
   Whenever the user asks what a function, method, or class does, or before refactoring a symbol, consult the CodeBin index:
   ```bash
   python scripts/codebin_engine.py lookup <symbol_name>
   ```
2. **Search Before Reading:**
   If you need to locate functions handling specific concepts (e.g. auth, billing, taxes), run:
   ```bash
   python scripts/codebin_engine.py search "<keyword>"
   ```
3. **Keep Context Lightweight:**
   Rely on CodeBin's $O(1)$ random seek results instead of loading dozens of source files into conversation memory.
4. **Rescan on Updates:**
   After writing or refactoring major components, keep the index fresh by executing:
   ```bash
   python scripts/codebin_engine.py scan
   ```
