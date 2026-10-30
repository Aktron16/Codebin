---
name: codebin
description: "Binary symbol indexer and O(1) codebase cache. Use to instantly look up functions, classes, variables, types, signatures, and change history without repeatedly reading raw files. Saves context window tokens and speeds up codebase navigation."
---

# /codebin

A high-performance binary symbol repository and $O(1)$ random-access indexer for AI agents.

## Why CodeBin?
Instead of reading 50 files or loading thousands of lines of source code into your context window just to inspect a function signature, class method, or variable definition, **CodeBin stores codebase symbols into a compact binary format (`.codebin/symbols.bin`) indexed with byte offsets (`.codebin/symbols.idx.json`)**.

Looking up a symbol is an instantaneous $O(1)$ disk `seek()` operation that costs **< 1ms** and returns the exact definition, description, timestamps, and line numbers.

## When to Use This Skill
- When the user asks what a specific function, class, or variable does.
- When you need to check function parameters, signatures, or class inheritance without scanning files.
- When tracking changes, additions, or deprecations/removals in the codebase.
- When starting work on a repository to index symbols upfront.

## Agent Tool Commands

### 1. Lookup a Symbol (Instant $O(1)$)
```python
from scripts.tool_codebin import codebin_lookup

result = codebin_lookup("calculate_tax")
# or with qualified path:
result = codebin_lookup("src/billing.py::calculate_tax")
```
Output:
```json
{
  "found": true,
  "name": "src/billing.py::calculate_tax",
  "type": "F",
  "status": "active",
  "signature": "def calculate_tax(gross_income, state)",
  "file": "src/billing.py",
  "line": 42,
  "description": "Calculates regional tax brackets based on annual gross income.",
  "created_at": 1730250000000,
  "modified_at": 1730250000000
}
```

### 2. Search Symbols by Keyword
```python
from scripts.tool_codebin import codebin_search

# Search all symbols matching 'user'
results = codebin_search("user")

# Filter only classes
results = codebin_search("user", symbol_type="C")
```

### 3. Scan & Update Index
```python
from scripts.tool_codebin import codebin_scan

# Incrementally scan and pack changes
stats = codebin_scan()
# Returns: {"added": 3, "modified": 1, "unchanged": 45, "removed": 0}
```

### 4. Check Status
```python
from scripts.tool_codebin import codebin_status

stats = codebin_status()
```

## CLI Usage (Terminal)
```bash
python scripts/codebin_engine.py init              # Initialize .codebin directory
python scripts/codebin_engine.py scan [path]       # Scan project and build binary index
python scripts/codebin_engine.py lookup <symbol>   # Instant lookup
python scripts/codebin_engine.py search <query>    # Search symbol names
python scripts/codebin_engine.py status            # View index statistics
python scripts/codebin_engine.py compact           # Compact binary file and purge tombstones
```

## How It Works Under The Hood
- **TLV Binary Protocol:** Packed with standard Network Byte Order (`>4sBBBcQQ16sHHHII`), storing magic bytes (`CBIN`), symbol type, timestamps, MD5 content hashes, status flags, and UTF-8 payloads.
- **Incremental Scanning:** Uses file `mtime` and AST content hashes to re-parse only modified files.
- **Tombstoning:** Deprecated or deleted symbols are marked as `removed` with timestamp tracking rather than disappearing silently.
- **Safe Static Extraction:** Pure AST inspection with zero code execution (`eval`/`exec`/`import`).
