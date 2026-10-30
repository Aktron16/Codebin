# CodeBin 📦

> **Universal binary codebase memory & indexing platform for AI agents.**  
> Gives AI assistants instant $O(1)$ random access to functions, classes, and types in < 1ms without reading entire files.

---

## What is CodeBin?

When you ask an AI assistant a question about your code, it usually has to open and read dozens of files just to find one function or class. This makes the AI slow, wastes lots of tokens (which can get expensive), and clutters the conversation.

**Think of CodeBin like the index at the back of a 1,000-page book.**  
Instead of reading through every single page from the beginning, CodeBin scans your project once and creates a tiny, organized bookmark file. When the AI wants to know what a function does, it jumps straight to that exact spot in less than a millisecond.

---

## Universal AI Integrations

CodeBin works natively out of the box with all major AI developer tools:

| Platform | Integration Folder | Config File |
|---|---|---|
| **GitHub Copilot** | `integrations/github_copilot/` | `.github/copilot-instructions.md` |
| **Claude Code** | `integrations/claude_code/` | `.claude/CLAUDE.md`, `CLAUDE.md` |
| **Cursor** | `integrations/cursor/` | `.cursor/rules/codebin.mdc` |
| **OpenAI Codex** | `integrations/codex/` | `.codex/instructions.md` |
| **Gemini CLI** | `integrations/gemini/` | `.gemini/instructions.md` |

---

## GitHub CLI Integration

CodeBin includes built-in GitHub CLI & repository synchronization capabilities:

```bash
# Clone any GitHub repo and immediately build a binary index
python scripts/codebin_gh.py clone-index owner/repo

# Initialize git, stage files, and prepare initial commit
python scripts/codebin_gh.py init-repo -m "Initial commit"

# Push commits to origin
python scripts/codebin_gh.py push --branch main
```

---

## Core Usage Commands

```bash
python scripts/codebin_engine.py scan               # Scan project and build binary index
python scripts/codebin_engine.py lookup <symbol>    # Instant O(1) symbol lookup
python scripts/codebin_engine.py search "<query>"   # Multi-token keyword search
python scripts/codebin_engine.py status             # View repository stats
python scripts/codebin_engine.py compact            # Defragment binary store and purge tombstones
```

---

## Repository Structure

```text
d:\Codebin\
├── README.md               # Universal quickstart guide
├── CLAUDE.md               # Root Claude Code configuration
├── .gitignore              # Standard git exclusion rules
├── .github/                # GitHub Copilot instructions
├── .claude/                # Claude Code configuration
├── .cursor/rules/          # Cursor MDC rules
├── .codex/                 # OpenAI Codex instructions
├── .gemini/                # Gemini Agent instructions
├── integrations/           # Universal platform reference configs
│   ├── github_copilot/
│   ├── claude_code/
│   ├── cursor/
│   ├── codex/
│   └── gemini/
├── skill/
│   └── SKILL.md            # Agent skill specification
├── references/
│   ├── skill_guide.md      # Deep technical architecture specification
│   └── examples.md         # Real-world use cases, token savings & MCP config
└── scripts/
    ├── codebin_engine.py   # Core binary engine with security & compression
    ├── tool_codebin.py     # AI agent callable tool interface with injection guards
    ├── mcp_server.py       # Model Context Protocol stdio server
    ├── codebin_gh.py       # GitHub CLI & remote repository tools
    ├── test_codebin.py     # Functional test suite
    └── test_security_codebin.py # Automated security & vulnerability tests
```
