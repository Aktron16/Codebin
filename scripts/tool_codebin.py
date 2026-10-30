"""
AI Agent Tool Interface for CodeBin.
Exposes clean functions and schemas for LLMs and agent frameworks
(OpenAI Function Calling, LangChain, Anthropic Tools, MCP).
Features safe prompt-injection tagging and secret redaction.
"""

import json
import os
import sys
from typing import Any, Dict, List, Optional

_scripts_dir = os.path.dirname(os.path.abspath(__file__))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

try:
    from codebin_engine import CodeBinManager, sanitize_agent_output
except ImportError:
    from scripts.codebin_engine import CodeBinManager, sanitize_agent_output


# ==============================================================================
# CALLABLE FUNCTIONS FOR AI AGENTS (Safe & Guarded)
# ==============================================================================

def codebin_lookup(symbol_name: str, project_dir: str = ".") -> Dict[str, Any]:
    """
    Instantly retrieves the description, signature, type, and file location
    of a function, class, variable, or type from the binary database.
    Use this instead of reading entire source code files.
    """
    mgr = CodeBinManager(project_dir)
    record = mgr.lookup(symbol_name)
    if not record:
        return {
            "found": False,
            "message": f"Symbol '{symbol_name}' was not found in the binary index. Try codebin_search or codebin_scan."
        }
    
    # Wrap in guarded untrusted delimiter to mitigate prompt injection from untrusted repos
    desc = sanitize_agent_output(record.get("description", ""))
    guarded_desc = f"<codebin_untrusted_metadata symbol='{record['qualified_name']}'>\n{desc}\n</codebin_untrusted_metadata>"

    return {
        "found": True,
        "name": record["qualified_name"],
        "type": record["type"],
        "status": record["status"],
        "signature": sanitize_agent_output(record["signature"]),
        "file": record["file_path"],
        "line": record["line_number"],
        "description": guarded_desc,
        "created_at": record["created_at"],
        "modified_at": record["modified_at"],
    }


def codebin_search(query: str, symbol_type: Optional[str] = None, project_dir: str = ".") -> Dict[str, Any]:
    """
    Performs a fast multi-token search across all indexed symbol names and descriptions.
    Optionally filter by symbol_type ('F' for Function, 'C' for Class, 'V' for Variable, 'T' for Type, 'M' for Method).
    """
    mgr = CodeBinManager(project_dir)
    results = mgr.search(query, sym_type=symbol_type)
    return {
        "count": len(results),
        "matches": results[:30]  # Cap results to keep context concise
    }


def codebin_scan(project_dir: str = ".", force_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Scans the project files, extracts new or modified symbols, records removals,
    and updates the binary database and index map.
    """
    mgr = CodeBinManager(project_dir)
    stats = mgr.scan(force_path)
    return {
        "status": "success",
        "added": stats["added"],
        "modified": stats["modified"],
        "unchanged": stats["unchanged"],
        "removed": stats["removed"],
        "total_active": mgr.status()["active_symbols"]
    }


def codebin_status(project_dir: str = ".") -> Dict[str, Any]:
    """
    Returns summary statistics about the binary index (active symbols, file size, last scan time).
    """
    mgr = CodeBinManager(project_dir)
    return mgr.status()


# ==============================================================================
# TOOL CALL SCHEMAS (JSON Schema for Agent Function Calling)
# ==============================================================================

TOOL_SCHEMAS = [
    {
        "name": "codebin_lookup",
        "description": "Instantly looks up a function, class, variable, or type definition from the binary index without reading source files.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol_name": {
                    "type": "string",
                    "description": "The name or qualified path of the symbol to retrieve (e.g. 'calculate_tax' or 'src/auth.py::login')."
                },
                "project_dir": {
                    "type": "string",
                    "description": "Optional root directory of the project. Defaults to current directory.",
                    "default": "."
                }
            },
            "required": ["symbol_name"]
        }
    },
    {
        "name": "codebin_search",
        "description": "Searches for symbols matching keywords across the codebase index.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Keywords or substrings to match against symbol names and docstrings."
                },
                "symbol_type": {
                    "type": "string",
                    "enum": ["F", "C", "V", "T", "M"],
                    "description": "Optional filter: 'F' (Function), 'C' (Class), 'V' (Variable), 'T' (Type), 'M' (Method)."
                },
                "project_dir": {
                    "type": "string",
                    "description": "Optional root directory of the project.",
                    "default": "."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "codebin_scan",
        "description": "Scans the codebase to detect new, modified, or deleted symbols and updates the binary cache.",
        "parameters": {
            "type": "object",
            "properties": {
                "project_dir": {
                    "type": "string",
                    "description": "Root directory of the project to scan.",
                    "default": "."
                }
            }
        }
    }
]


if __name__ == "__main__":
    print(json.dumps(TOOL_SCHEMAS, indent=2))
