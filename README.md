# CodeBin 📦

> **Universal binary codebase memory & indexing platform for AI agents.**  
> Gives AI assistants instant $O(1)$ random access to functions, classes, and types in < 1ms without reading entire files.

---

## What is CodeBin?

When you ask an AI assistant a question about your code, it usually has to open and read dozens of files just to find one function or class. This makes the AI slow, wastes lots of tokens (which gets expensive), and clutters the conversation window.

**Think of CodeBin like the index at the back of a 1,000-page book.**  
Instead of reading through every single page from the beginning, CodeBin scans your project once and creates a tiny, organized binary file (`.codebin/symbols.bin`) with a byte-offset index (`.codebin/symbols.idx.json`). When the AI wants to know what a function does, it jumps straight to that exact byte location in less than a millisecond.

---

## Installation Methods

### Method 1: Git Clone (Quickstart)
```bash
git clone https://github.com/Aktron16/Codebin.git
cd Codebin
```

### Method 2: Zero-Config AI Assistant Integration
If you are opening this workspace in **Cursor**, **Windsurf**, **Claude Code**, or **GitHub Copilot**, CodeBin is pre-configured to activate automatically via:
- `.agents/skills/codebin/SKILL.md` (Universal Agent Specification)
- `.cursor/rules/codebin.mdc` (Cursor IDE)
- `.claude/CLAUDE.md` (Claude Code)
- `.github/copilot-instructions.md` (GitHub Copilot)
- `.codex/instructions.md` (OpenAI Codex)
- `.gemini/instructions.md` (Gemini CLI)

### Method 3: Model Context Protocol (MCP) Server
Connect CodeBin directly to Claude Desktop or Cursor MCP:
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

👉 **For comprehensive step-by-step setup guides for each platform, see [INSTALL.md](INSTALL.md).**

---

## CLI Integration Guide

CodeBin provides two complementary CLI tools:
1. **`codebin_engine.py`**: Human-friendly terminal utility for scanning, searching, and managing the binary database.
2. **`tool_codebin.py`**: AI agent evaluation interface emitting strict, structured JSON on STDOUT.

### Step 1: Environment Initialization
Run the environment configuration script once per terminal or container session:
```bash
# macOS / Linux
source scripts/setup_env.sh

# Windows
scripts\setup_env.bat
```

### Step 2: Indexing Any Codebase
Scan the current directory or specify any path:
```bash
# Scan current workspace
python scripts/codebin_engine.py scan

# Or scan an external project directory
python scripts/codebin_engine.py scan /path/to/another/project
```

### Step 3: Instant Symbol Lookups (< 1ms)
Retrieve symbol metadata, line numbers, and parameters directly from disk:
```bash
# Human-readable CLI
python scripts/codebin_engine.py lookup calculate_tax

# Agent-evaluation JSON interface
python scripts/tool_codebin.py lookup --symbol_name calculate_tax
```

### Step 4: Multi-Token Keyword Search
Search across symbol names and docstrings without regex scanning:
```bash
# Human-readable CLI
python scripts/codebin_engine.py search "auth credentials"

# Filter by symbol type (F = Function, C = Class, V = Variable, T = Type)
python scripts/tool_codebin.py search --query "auth" --symbol_type C
```

### Step 5: Database Status & Compaction
```bash
# View database health, active symbol counts, and file sizes
python scripts/tool_codebin.py status

# Defragment binary store and purge removed symbol tombstones
python scripts/codebin_engine.py compact
```

---

## GitHub CLI Integration

CodeBin includes remote repository and binary cache synchronization capabilities:

```bash
# Clone any GitHub repository and immediately generate a binary index
python scripts/codebin_gh.py clone-index owner/repo

# Initialize git tracking and stage initial commit
python scripts/codebin_gh.py init-repo -m "Initial commit"

# Push local commits to origin main
python scripts/codebin_gh.py push --branch main
```

---

## Repository Structure

```text
d:\Codebin\
├── README.md                              # Plain-English guide & quickstart
├── INSTALL.md                             # Step-by-step installation for each AI model
├── agent.json                             # Root agent specification manifest
├── skills.json                            # Compatibility manifest mirror
├── .gitignore                             # Git exclusion rules
├── .agents/
│   └── skills/codebin/SKILL.md            # Universal engine mapping (Windsurf, CLI frameworks)
├── .claude/CLAUDE.md                      # Claude Code instructions
├── .cursor/rules/codebin.mdc              # Cursor MDC rules
├── .github/copilot-instructions.md        # GitHub Copilot instructions
├── .codex/instructions.md                 # OpenAI Codex instructions
├── .gemini/instructions.md                # Gemini Agent instructions
├── integrations/                          # Portable multi-assistant definitions
│   ├── claude_code/CLAUDE.md
│   ├── cursor/codebin.mdc
│   ├── github_copilot/copilot-instructions.md
│   ├── codex/instructions.md
│   └── gemini/instructions.md
├── references/
│   ├── skill_guide.md                     # Deep technical architecture specification
│   └── examples.md                        # Real-world use cases & token benchmarks
├── skill/
│   └── SKILL.md                           # Universal AI agent skill definition with unified tools
└── scripts/
    ├── codebin_engine.py                  # Core binary indexing engine with compression
    ├── tool_codebin.py                    # Tool definitions with CLI JSON data contract
    ├── mcp_server.py                      # Model Context Protocol stdio server
    ├── codebin_gh.py                      # GitHub CLI & remote binary sync
    ├── setup_env.sh                       # Unix environment initialization
    ├── setup_env.bat                      # Windows environment initialization
    ├── test_codebin.py                    # Functional verification test suite
    └── test_security_codebin.py           # Automated security & vulnerability tests
```

---

## Verification & Tests

Run the built-in self-test suites to verify engine integrity:
```bash
# Core engine tests (packing, unpacking, incremental scan, tombstoning)
python scripts/test_codebin.py

# Security tests (symlink jail, secret redaction, ReDoS guard, decompression bomb bounds)
python scripts/test_security_codebin.py
```
