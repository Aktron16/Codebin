# CodeBin Installation & AI Model Setup Guide 🚀

This guide provides step-by-step instructions for integrating **CodeBin** into your workflow, covering each major AI coding assistant, Model Context Protocol (MCP) clients, and a standalone manual installation method.

---

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Manual Installation (Standalone CLI)](#manual-installation-standalone-cli)
3. [AI Model & Assistant Integrations](#ai-model--assistant-integrations)
   - [GitHub Copilot](#1-github-copilot)
   - [Claude Code](#2-claude-code)
   - [Cursor](#3-cursor)
   - [OpenAI Codex](#4-openai-codex)
   - [Gemini CLI / Assistants](#5-gemini-cli--assistants)
   - [Windsurf & Universal Agents](#6-windsurf--universal-agent-engines)
4. [Model Context Protocol (MCP) Setup](#model-context-protocol-mcp-setup)
5. [Verifying Installation & Test Suite](#verifying-installation--test-suite)
6. [Troubleshooting & FAQ](#troubleshooting--faq)

---

## Prerequisites

- **Python**: Version 3.8 or higher.
- **Git**: Installed and available in your system `PATH`.
- **Operating System**: Windows, macOS, or Linux.
- **Dependencies**: CodeBin uses Python's standard library exclusively (`ast`, `struct`, `hashlib`, `json`, `zlib`, `urllib`). No external pip packages are required.

---

## Manual Installation (Standalone CLI)

Follow these steps to set up CodeBin locally for any project without an IDE or specialized agent framework.

### Step 1: Clone the Repository
```bash
git clone https://github.com/Aktron16/Codebin.git
cd Codebin
```

### Step 2: Initialize Environment Variables
Configure `PYTHONPATH` so helper tools and scripts can resolve the engine modules seamlessly.

- **On macOS / Linux**:
  ```bash
  chmod +x scripts/*.sh scripts/*.py
  source scripts/setup_env.sh
  ```

- **On Windows (Command Prompt)**:
  ```cmd
  scripts\setup_env.bat
  ```

- **On Windows (PowerShell)**:
  ```powershell
  $env:PYTHONPATH += ";$PWD\scripts"
  ```

### Step 3: Build Your Initial Codebase Index
Run the scan command against your project root:
```bash
python scripts/codebin_engine.py scan
```
This inspects all source code files (`.py`, `.ts`, `.js`, `.rs`, `.go`, `.java`, etc.), extracts function/class/method symbols into `.codebin/symbols.bin`, and builds the high-speed index in `.codebin/symbols.idx.json`.

### Step 4: Verify Your Index
Inspect repository stats:
```bash
python scripts/tool_codebin.py status
```
Expected output:
```json
{
  "project_root": "...",
  "active_symbols": 62,
  "removed_symbols": 0,
  "total_tracked": 62,
  "binary_file_bytes": 10012,
  "index_file_bytes": 35250,
  "last_scan": 1793319476607
}
```

---

## AI Model & Assistant Integrations

CodeBin comes pre-configured for every major agent framework. Simply open this workspace or copy the respective configuration file into your target project.

### 1. GitHub Copilot
- **Configuration File**: `.github/copilot-instructions.md` (or `integrations/github_copilot/copilot-instructions.md`)
- **How to Install**:
  1. If adding to an existing repository, copy `.github/copilot-instructions.md` to your repository's `.github/` directory.
  2. GitHub Copilot Workspace and VS Code Copilot Chat automatically read this file to prioritize `$O(1)$` symbol checks before file exploration.
- **Verification**: In Copilot Chat, ask: *"Lookup the definition of calculate_tax using CodeBin."* Copilot will invoke `python scripts/codebin_engine.py lookup calculate_tax`.

---

### 2. Claude Code
- **Configuration File**: `.claude/CLAUDE.md` (or `integrations/claude_code/CLAUDE.md`)
- **How to Install**:
  1. Claude Code automatically scans `.claude/CLAUDE.md` in your workspace.
  2. The configuration instructs Claude Code to query `.codebin/` before reading multi-file source directories.
- **Verification**: In your terminal session with Claude Code, run:
  ```bash
  claude "What parameters does the processPayment function accept?"
  ```
  Claude will execute `tool_codebin.py lookup` and report the signature with zero token waste.

---

### 3. Cursor
- **Configuration File**: `.cursor/rules/codebin.mdc` (or `integrations/cursor/codebin.mdc`)
- **How to Install**:
  1. Cursor automatically picks up MDC rules from `.cursor/rules/`.
  2. When asking Cursor Composer or Cursor Chat codebase questions, the rule activates automatically to prevent context pollution.
- **Verification**: In Cursor Chat (Ctrl+L / Cmd+L), ask: *"What methods are defined on UserManager?"* Cursor will check `codebin_lookup("UserManager")`.

---

### 4. OpenAI Codex
- **Configuration File**: `.codex/instructions.md` (or `integrations/codex/instructions.md`)
- **How to Install**:
  1. Place `.codex/instructions.md` in your workspace root, or include its contents in your assistant system prompt or custom GPT workspace instructions.
  2. Codex will call `python scripts/tool_codebin.py lookup` to retrieve function headers without requesting full source files.

---

### 5. Gemini CLI / Assistants
- **Configuration File**: `.gemini/instructions.md` (or `integrations/gemini/instructions.md`)
- **How to Install**:
  1. Place `.gemini/instructions.md` in the project root or include it in your Gemini context bundle.
  2. The assistant parses the JSON output from `tool_codebin.py` to formulate concise answers.

---

### 6. Windsurf & Universal Agent Engines
- **Configuration File**: `.agents/skills/codebin/SKILL.md` (and `agent.json`)
- **How to Install**:
  1. Universal agent frameworks (such as Windsurf or open-source agent runtimes) scan `.agents/skills/` at workspace initialization.
  2. The root `agent.json` declares:
     ```json
     {
       "skills_directory": "./skill",
       "tools_directory": "./scripts"
     }
     ```
  3. No additional steps are required; the skill registers automatically.

---

## Model Context Protocol (MCP) Setup

CodeBin includes a native MCP stdio server in `scripts/mcp_server.py`. This connects directly to MCP-compatible clients.

### For Claude Desktop (`claude_desktop_config.json`)
Add the following under `mcpServers`:

```json
{
  "mcpServers": {
    "codebin": {
      "command": "python",
      "args": ["d:/Codebin/scripts/mcp_server.py"]
    }
  }
}
```
*(Replace `d:/Codebin` with the absolute path to your CodeBin directory).*

### For Cursor MCP Settings
1. Open Cursor Settings -> **Features** -> **MCP Servers**.
2. Click **+ Add New MCP Server**.
3. Name: `codebin`
4. Type: `command`
5. Command: `python scripts/mcp_server.py`

### Available MCP Tools:
- `codebin_lookup(symbol_name, project_dir)`
- `codebin_search(query, symbol_type, project_dir)`
- `codebin_scan(project_dir, force_path)`
- `codebin_status(project_dir)`

---

## Verifying Installation & Test Suite

Verify that your installation is healthy and security guards are operational:

1. **Run Core Engine Verification**:
   ```bash
   python scripts/test_codebin.py
   ```
   *Verifies binary pack/unpack roundtrip with zlib compression, JSDoc harvesting, Python decorator extraction, incremental change tracking, and tombstoning.*

2. **Run Security Test Suite**:
   ```bash
   python scripts/test_security_codebin.py
   ```
   *Verifies secret redaction (AWS/GitHub PATs), symlink jail isolation, ReDoS guards on minified files, decompression bomb caps, and prompt-injection defense tags.*

---

## Troubleshooting & FAQ

### Q: Why do I see `[SKIP] symlink creation not permitted` during tests on Windows?
**A**: On Windows, creating symbolic links requires either Developer Mode enabled or Administrative privileges. CodeBin skips creating physical test symlinks if permissions are not elevated, but its internal path resolution security checks remain 100% active.

### Q: How do I scan a different project folder?
**A**: Pass the target path directly to the CLI:
```bash
python scripts/codebin_engine.py scan /path/to/another/project
```

### Q: Does CodeBin run code or execute untrusted files?
**A**: Never. CodeBin relies exclusively on static Abstract Syntax Tree (AST) parsing and non-backtracking regular expressions. It never invokes `eval()`, `exec()`, or dynamic imports.
