"""
Model Context Protocol (MCP) Server for CodeBin.
Provides a standard stdio JSON-RPC interface for AI agents and IDEs
(Claude Desktop, Cursor, Windsurf, Antigravity).
"""

import json
import os
import sys

_scripts_dir = os.path.dirname(os.path.abspath(__file__))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from tool_codebin import (
    TOOL_SCHEMAS,
    codebin_lookup,
    codebin_search,
    codebin_scan,
    codebin_status,
)


def handle_request(req: dict) -> dict:
    req_id = req.get("id")
    method = req.get("method")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "codebin-mcp", "version": "1.0.0"},
            },
        }

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": schema["name"],
                        "description": schema["description"],
                        "inputSchema": schema["parameters"],
                    }
                    for schema in TOOL_SCHEMAS
                ]
            },
        }

    elif method == "tools/call":
        params = req.get("params", {})
        name = params.get("name")
        args = params.get("arguments", {})

        try:
            if name == "codebin_lookup":
                out = codebin_lookup(
                    symbol_name=args.get("symbol_name", ""),
                    project_dir=args.get("project_dir", "."),
                )
            elif name == "codebin_search":
                out = codebin_search(
                    query=args.get("query", ""),
                    symbol_type=args.get("symbol_type"),
                    project_dir=args.get("project_dir", "."),
                )
            elif name == "codebin_scan":
                out = codebin_scan(
                    project_dir=args.get("project_dir", "."),
                )
            elif name == "codebin_status":
                out = codebin_status(
                    project_dir=args.get("project_dir", "."),
                )
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Unknown tool: {name}"},
                }

            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {"type": "text", "text": json.dumps(out, indent=2)}
                    ]
                },
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32000, "message": str(e)},
            }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def main():
    """Stdio JSON-RPC loop."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            resp = handle_request(req)
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
        except Exception as e:
            err_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {e}"},
            }
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
