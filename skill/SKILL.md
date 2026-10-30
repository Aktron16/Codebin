---
name: codebin
description: "Binary symbol indexer and O(1) codebase cache. Use to instantly look up functions, classes, variables, types, signatures, and change history without repeatedly reading raw files. Saves context window tokens and speeds up codebase navigation."
tools:
  - name: codebin_lookup
    description: "Instantly retrieves the description, signature, type, and file location of a function, class, variable, or type from the binary database without reading entire source files."
    command: "python scripts/tool_codebin.py lookup --symbol_name {symbol_name} [--project_dir {project_dir}]"
    parameters:
      type: object
      properties:
        symbol_name:
          type: string
          description: "The name or qualified path of the symbol to retrieve (e.g. 'calculate_tax' or 'src/auth.py::login')."
        project_dir:
          type: string
          description: "Optional root directory of the project. Defaults to '.'."
          default: "."
      required:
        - symbol_name
  - name: codebin_search
    description: "Performs a fast multi-token search across all indexed symbol names and descriptions."
    command: "python scripts/tool_codebin.py search --query {query} [--symbol_type {symbol_type}] [--project_dir {project_dir}]"
    parameters:
      type: object
      properties:
        query:
          type: string
          description: "Keywords or substrings to match against symbol names and docstrings."
        symbol_type:
          type: string
          enum: ["F", "C", "V", "T", "M"]
          description: "Optional filter: 'F' (Function), 'C' (Class), 'V' (Variable), 'T' (Type), 'M' (Method)."
        project_dir:
          type: string
          description: "Optional root directory of the project. Defaults to '.'."
          default: "."
      required:
        - query
  - name: codebin_scan
    description: "Scans the project files, extracts new or modified symbols, records removals, and updates the binary database and index map."
    command: "python scripts/tool_codebin.py scan [--project_dir {project_dir}] [--force_path {force_path}]"
    parameters:
      type: object
      properties:
        project_dir:
          type: string
          description: "Root directory of the project to scan. Defaults to '.'."
          default: "."
        force_path:
          type: string
          description: "Optional specific file or folder to re-index."
  - name: codebin_status
    description: "Returns summary statistics about the binary index (active symbols, file size, last scan time)."
    command: "python scripts/tool_codebin.py status [--project_dir {project_dir}]"
    parameters:
      type: object
      properties:
        project_dir:
          type: string
          description: "Optional root directory of the project. Defaults to '.'."
          default: "."
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

### 5. MCP Server (JSON-RPC stdio)
For platforms using the Model Context Protocol (Cursor, Windsurf, Claude Desktop, etc.):
```json
{
  "mcpServers": {
    "codebin": {
      "command": "python",
      "args": ["scripts/mcp_server.py"]
    }
  }
}
```
Exposes standard MCP tools with identical parameters:
- `codebin_lookup(symbol_name: str, project_dir: str = ".")`
- `codebin_search(query: str, symbol_type: Optional[str] = None, project_dir: str = ".")`
- `codebin_scan(project_dir: str = ".", force_path: Optional[str] = None)`
- `codebin_status(project_dir: str = ".")`

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
