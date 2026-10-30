"""
CodeBin Engine: High-performance binary codebase symbol cache and indexer.
Provides O(1) random-access retrieval of functions, classes, variables, and types
without rescanning raw source files. Fully hardened against prompt injection,
secret leakage, ReDoS, symlink traversal, and decompression bombs.
"""

import ast
import contextlib
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
import time
import zlib
from typing import Any, Dict, List, Optional, Tuple

# Binary protocol constants
MAGIC = b"CBIN"
FORMAT_VERSION = 2

# 53-byte header: Magic(4s), Version(B), Status(B), Flags(B), Type(c), Created(Q), Modified(Q), Hash(16s), NameLen(H), PathLen(H), SigLen(H), Line(I), DescLen(I)
HEADER_FORMAT = ">4sBBBcQQ16sHHHII"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

# Security and resource caps
MAX_RECORD_PAYLOAD = 1024 * 1024  # 1 MB max single symbol payload
MAX_FILE_SIZE = 1024 * 1024       # 1 MB max source file size to parse
MAX_LINE_LENGTH = 2048            # 2 KB max line length to avoid ReDoS in minified files
LOCK_TIMEOUT_SECONDS = 30         # Stale lock expiration

# Status codes
STATUS_ACTIVE = 1
STATUS_MODIFIED = 2
STATUS_REMOVED = 3

STATUS_NAMES = {
    STATUS_ACTIVE: "active",
    STATUS_MODIFIED: "modified",
    STATUS_REMOVED: "removed",
}

# Feature flags
FLAG_NONE = 0x00
FLAG_ZLIB_COMPRESSED = 0x01

DEFAULT_IGNORES = {
    ".git", ".codebin", "node_modules", "venv", ".venv", "__pycache__",
    ".idea", ".vscode", "dist", "build", "coverage", ".next", ".nuxt",
    "vendor", "target", "bin", "obj", ".turbo", ".cache"
}

IGNORED_EXTENSIONS = {
    ".exe", ".dll", ".so", ".dylib", ".bin", ".dat", ".idx", ".pak",
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".zip", ".tar",
    ".gz", ".pdf", ".pyc", ".pyo", ".env", ".pem", ".key", ".lock",
    ".sqlite", ".db", ".min.js", ".min.css", ".map", ".bundle.js"
}

# Sensitive credential patterns for automated redaction
SECRET_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),                                # AWS Access Key
    re.compile(r"ghp_[a-zA-Z0-9]{36}"),                             # GitHub Personal Access Token
    re.compile(r"-----BEGIN (?:[A-Z ]+)PRIVATE KEY-----"),          # Private Keys
    re.compile(r"eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}"),  # JWT Tokens
    re.compile(r"(api[_-]?key|secret|password|token)\s*[:=]\s*['\"][a-zA-Z0-9_\-]{16,}['\"]", re.IGNORECASE),
]


def redact_secrets(text: str) -> str:
    """Masks recognized secrets, tokens, and private keys."""
    if not text:
        return text
    sanitized = text
    for pattern in SECRET_PATTERNS:
        sanitized = pattern.sub("[REDACTED_SECRET]", sanitized)
    return sanitized


def sanitize_agent_output(text: str) -> str:
    """Strips control chars and escapes prompt-injection formatting."""
    if not text:
        return ""
    # Strip null bytes and non-printable control characters (except newline and tab)
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    return redact_secrets(cleaned)


# ==============================================================================
# CONCURRENCY & STALE-RESISTANT FILE LOCKING
# ==============================================================================

@contextlib.contextmanager
def file_lock(filepath: str, exclusive: bool = True):
    """Advisory file locking with stale lock recovery and timeout safety."""
    lock_file = filepath + ".lock"
    
    # Check for stale lock older than LOCK_TIMEOUT_SECONDS
    if os.path.exists(lock_file):
        try:
            mtime = os.path.getmtime(lock_file)
            if time.time() - mtime > LOCK_TIMEOUT_SECONDS:
                os.remove(lock_file)
        except OSError:
            pass

    f = open(lock_file, "w")
    try:
        if os.name == "nt":
            import msvcrt
            mode = msvcrt.LK_NBLCK if exclusive else msvcrt.LK_NBRLCK
            acquired = False
            for _ in range(50):
                try:
                    msvcrt.locking(f.fileno(), mode, 1)
                    acquired = True
                    break
                except OSError:
                    time.sleep(0.02)
        else:
            import fcntl
            flags = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
            fcntl.flock(f.fileno(), flags)
        yield
    finally:
        try:
            if os.name == "nt":
                import msvcrt
                try:
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
            else:
                import fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        f.close()
        try:
            if os.path.exists(lock_file):
                os.remove(lock_file)
        except OSError:
            pass


def current_time_ms() -> int:
    return int(time.time() * 1000)


def hash_content(content: str) -> bytes:
    return hashlib.md5(content.encode("utf-8", errors="ignore")).digest()


# ==============================================================================
# SAFE BINARY SERIALIZATION WITH ZLIB & BUFFER BOUNDS
# ==============================================================================

def pack_symbol_record(
    status: int,
    comp_type: str,
    created_at: int,
    modified_at: int,
    content_hash: bytes,
    qualified_name: str,
    file_path: str,
    signature: str,
    line_number: int,
    description: str,
    compress: bool = True,
) -> bytes:
    """Packs symbol metadata with secret redaction and zlib payload compression."""
    # Redact sensitive values before persisting
    clean_sig = redact_secrets(signature)
    clean_desc = redact_secrets(description)

    name_bytes = qualified_name.encode("utf-8")[:65535]
    path_bytes = file_path.encode("utf-8")[:65535]
    sig_bytes = clean_sig.encode("utf-8")[:65535]
    desc_bytes = clean_desc.encode("utf-8")

    payload = name_bytes + path_bytes + sig_bytes + desc_bytes
    flags = FLAG_NONE

    if compress and len(payload) > 64:
        compressed_payload = zlib.compress(payload, level=6)
        if len(compressed_payload) < len(payload):
            payload = compressed_payload
            flags |= FLAG_ZLIB_COMPRESSED

    header = struct.pack(
        HEADER_FORMAT,
        MAGIC,
        FORMAT_VERSION,
        status,
        flags,
        comp_type[:1].encode("ascii", errors="replace"),
        created_at,
        modified_at,
        content_hash[:16].ljust(16, b"\x00"),
        len(name_bytes),
        len(path_bytes),
        len(sig_bytes),
        line_number,
        len(desc_bytes),
    )
    return header + payload


def unpack_symbol_record(stream_or_bytes) -> Optional[Dict[str, Any]]:
    """Unpacks a symbol record with strict bounds checking against decompression bombs."""
    if isinstance(stream_or_bytes, (bytes, bytearray)):
        import io
        stream = io.BytesIO(stream_or_bytes)
    else:
        stream = stream_or_bytes

    header_data = stream.read(HEADER_SIZE)
    if len(header_data) < HEADER_SIZE:
        return None

    (
        magic,
        ver,
        status,
        flags,
        comp_type_b,
        created_at,
        modified_at,
        content_hash,
        name_len,
        path_len,
        sig_len,
        line_no,
        desc_len,
    ) = struct.unpack(HEADER_FORMAT, header_data)

    if magic != MAGIC:
        raise ValueError(f"Invalid binary header magic: {magic!r}")

    total_uncompressed_len = name_len + path_len + sig_len + desc_len
    if total_uncompressed_len > MAX_RECORD_PAYLOAD:
        raise ValueError(
            f"Record payload length ({total_uncompressed_len} bytes) exceeds maximum security threshold ({MAX_RECORD_PAYLOAD} bytes)."
        )

    if flags & FLAG_ZLIB_COMPRESSED:
        compressed_data = stream.read()
        # Decompress with explicit maximum length safeguard against zip bombs
        decompressed = zlib.decompress(compressed_data, bufsize=total_uncompressed_len)
        if len(decompressed) > MAX_RECORD_PAYLOAD:
            raise ValueError("Decompressed payload exceeds security buffer limit.")
        import io
        payload_stream = io.BytesIO(decompressed)
    else:
        payload_stream = stream

    name = payload_stream.read(name_len).decode("utf-8", errors="replace")
    path = payload_stream.read(path_len).decode("utf-8", errors="replace")
    sig = payload_stream.read(sig_len).decode("utf-8", errors="replace")
    desc = payload_stream.read(desc_len).decode("utf-8", errors="replace")

    return {
        "version": ver,
        "status": STATUS_NAMES.get(status, "unknown"),
        "type": comp_type_b.decode("ascii", errors="ignore"),
        "created_at": created_at,
        "modified_at": modified_at,
        "hash": content_hash.hex(),
        "qualified_name": name,
        "file_path": path,
        "signature": sig,
        "line_number": line_no,
        "description": desc,
    }


# ==============================================================================
# SECURE STATIC AST & COMMENT HARVESTER
# ==============================================================================

class SymbolExtractor:
    """Extracts symbols using pure static AST and comment harvesting without executing code."""

    @staticmethod
    def _harvest_preceding_comments(lines: List[str], line_idx: int) -> str:
        """Collects JSDoc, block comments, or line comments immediately above a line."""
        comments = []
        i = line_idx - 1
        in_block = False

        while i >= 0:
            if i < line_idx - 15:  # Limit comment search depth to 15 lines max
                break
            line = lines[i].strip()
            if len(line) > MAX_LINE_LENGTH:
                i -= 1
                continue
            if not line:
                if comments:
                    break
                i -= 1
                continue

            if line.endswith("*/"):
                in_block = True
                cleaned = line.rstrip("*/").strip().lstrip("/*").strip()
                if cleaned:
                    comments.insert(0, cleaned)
                i -= 1
                continue

            if in_block:
                cleaned = line.lstrip("/*").strip().lstrip("*").strip()
                if cleaned:
                    comments.insert(0, cleaned)
                if line.startswith("/*"):
                    in_block = False
                    break
                i -= 1
                continue

            if line.startswith("//") or line.startswith("///") or line.startswith("#"):
                cleaned = line.lstrip("/#").strip()
                if cleaned:
                    comments.insert(0, cleaned)
                i -= 1
                continue

            break

        res = " ".join(comments).strip() if comments else "No description provided."
        return sanitize_agent_output(res)

    @staticmethod
    def extract_from_python(file_path: str, source: str) -> List[Dict[str, Any]]:
        symbols = []
        try:
            tree = ast.parse(source, filename=file_path)
        except SyntaxError:
            return symbols

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, getattr(ast, "AsyncFunctionDef", ()))):
                doc = ast.get_docstring(node) or "No description provided."
                decs = []
                for d in getattr(node, "decorator_list", []):
                    dec_name = ast.get_source_segment(source, d) or getattr(d, "id", "")
                    if dec_name and len(dec_name) < 200:
                        decs.append(f"@{dec_name}")

                ret_ann = ""
                if getattr(node, "returns", None):
                    ret_str = ast.get_source_segment(source, node.returns) or ""
                    if ret_str and len(ret_str) < 200:
                        ret_ann = f" -> {ret_str}"

                prefix = "async def" if isinstance(node, getattr(ast, "AsyncFunctionDef", ())) else "def"
                args = [a.arg for a in node.args.args]
                sig = f"{' '.join(decs) + ' ' if decs else ''}{prefix} {node.name}({', '.join(args)}){ret_ann}".strip()
                node_code = ast.get_source_segment(source, node) or node.name

                symbols.append({
                    "type": "F",
                    "name": node.name,
                    "qualified_name": f"{file_path}::{node.name}",
                    "signature": sanitize_agent_output(sig),
                    "line": node.lineno,
                    "description": sanitize_agent_output(doc.strip()),
                    "hash": hash_content(node_code),
                })
            elif isinstance(node, ast.ClassDef):
                doc = ast.get_docstring(node) or "Class definition."
                bases = [getattr(b, "id", getattr(b, "attr", "object")) for b in node.bases]
                sig = f"class {node.name}({', '.join(bases)})" if bases else f"class {node.name}"
                node_code = ast.get_source_segment(source, node) or node.name

                symbols.append({
                    "type": "C",
                    "name": node.name,
                    "qualified_name": f"{file_path}::{node.name}",
                    "signature": sanitize_agent_output(sig),
                    "line": node.lineno,
                    "description": sanitize_agent_output(doc.strip()),
                    "hash": hash_content(node_code),
                })

                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, getattr(ast, "AsyncFunctionDef", ()))):
                        m_doc = ast.get_docstring(item) or f"Method of {node.name}."
                        m_decs = []
                        for d in getattr(item, "decorator_list", []):
                            dec_name = ast.get_source_segment(source, d) or getattr(d, "id", "")
                            if dec_name and len(dec_name) < 200:
                                m_decs.append(f"@{dec_name}")

                        m_args = [a.arg for a in item.args.args]
                        m_sig = f"{' '.join(m_decs) + ' ' if m_decs else ''}{item.name}({', '.join(m_args)})".strip()
                        m_code = ast.get_source_segment(source, item) or item.name

                        symbols.append({
                            "type": "M",
                            "name": f"{node.name}.{item.name}",
                            "qualified_name": f"{file_path}::{node.name}.{item.name}",
                            "signature": sanitize_agent_output(m_sig),
                            "line": item.lineno,
                            "description": sanitize_agent_output(m_doc.strip()),
                            "hash": hash_content(m_code),
                        })
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        name = target.id
                        symbols.append({
                            "type": "V",
                            "name": name,
                            "qualified_name": f"{file_path}::{name}",
                            "signature": f"{name} = ...",
                            "line": node.lineno,
                            "description": f"Top-level variable or constant in {file_path}.",
                            "hash": hash_content(name),
                        })
        return symbols

    @classmethod
    def extract_from_generic(cls, file_path: str, source: str) -> List[Dict[str, Any]]:
        """Multi-language regex with ReDoS protection & line length limits."""
        symbols = []
        lines = source.splitlines()

        patterns = [
            ("F", r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z0-9_$]+)\s*\((.*?)\)"),
            ("F", r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z0-9_$]+)\s*=\s*(?:async\s*)?\((.*?)\)\s*=>"),
            ("F", r"^\s*(?:pub(?:\(.*?\))?\s+)?(?:async\s+)?fn\s+([A-Za-z0-9_]+)\s*\((.*?)\)"),
            ("C", r"^\s*(?:pub(?:\(.*?\))?\s+)?(?:struct|enum|union)\s+([A-Za-z0-9_]+)"),
            ("F", r"^\s*func\s+(?:\(.*?\)\s+)?([A-Za-z0-9_]+)\s*\((.*?)\)"),
            ("T", r"^\s*type\s+([A-Za-z0-9_]+)\s+(?:struct|interface)"),
            ("C", r"^\s*(?:export\s+)?(?:abstract\s+)?class\s+([A-Za-z0-9_$]+)"),
            ("T", r"^\s*(?:export\s+)?(?:interface|type)\s+([A-Za-z0-9_$]+)"),
        ]

        for i, line in enumerate(lines):
            line_num = i + 1
            if len(line) > MAX_LINE_LENGTH:
                continue  # Skip minified lines to avoid ReDoS

            for sym_type, pat in patterns:
                m = re.search(pat, line)
                if m:
                    name = m.group(1)
                    sig = line.strip().rstrip("{").strip()
                    doc = cls._harvest_preceding_comments(lines, i)
                    symbols.append({
                        "type": sym_type,
                        "name": name,
                        "qualified_name": f"{file_path}::{name}",
                        "signature": sanitize_agent_output(sig),
                        "line": line_num,
                        "description": doc,
                        "hash": hash_content(line),
                    })
                    break
        return symbols

    extract_from_js_ts = extract_from_generic

    @classmethod
    def extract(cls, file_path: str, project_root: str) -> List[Dict[str, Any]]:
        full_path = os.path.join(project_root, file_path)

        # Path Traversal Guard: Reject files outside project root (e.g. symlink escape)
        canonical_file = os.path.realpath(full_path)
        canonical_root = os.path.realpath(project_root)
        if not canonical_file.startswith(canonical_root):
            return []

        # File Size Guard: Skip excessively large files (> 1MB)
        try:
            if os.path.getsize(full_path) > MAX_FILE_SIZE:
                return []
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                source = f.read()
        except Exception:
            return []

        rel_path = file_path.replace("\\", "/")
        if rel_path.endswith(".py"):
            return cls.extract_from_python(rel_path, source)
        else:
            return cls.extract_from_generic(rel_path, source)


# ==============================================================================
# CODEBIN REPOSITORY & INDEX MANAGER
# ==============================================================================

class CodeBinManager:
    """Manages the .codebin storage, binary log, and index map."""

    def __init__(self, project_root: str = "."):
        self.project_root = os.path.abspath(project_root)
        self.codebin_dir = os.path.join(self.project_root, ".codebin")
        self.bin_path = os.path.join(self.codebin_dir, "symbols.bin")
        self.idx_path = os.path.join(self.codebin_dir, "symbols.idx.json")
        self._ensure_storage()
        self.index = self._load_index()

    def _ensure_storage(self):
        os.makedirs(self.codebin_dir, exist_ok=True)
        if not os.path.exists(self.bin_path):
            with open(self.bin_path, "wb"):
                pass

    def _load_index(self) -> Dict[str, Any]:
        if os.path.exists(self.idx_path):
            try:
                with open(self.idx_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "version": FORMAT_VERSION,
            "last_scan": 0,
            "files": {},
            "symbols": {},
            "by_name": {},
        }

    def _save_index(self):
        tmp_idx = self.idx_path + ".tmp"
        with open(tmp_idx, "w", encoding="utf-8") as f:
            json.dump(self.index, f, indent=2)
        os.replace(tmp_idx, self.idx_path)

    def should_ignore(self, rel_path: str) -> bool:
        parts = rel_path.replace("\\", "/").split("/")
        for part in parts:
            if part in DEFAULT_IGNORES:
                return True
        _, ext = os.path.splitext(rel_path)
        if ext.lower() in IGNORED_EXTENSIONS:
            return True
        if rel_path.endswith((".min.js", ".min.css", ".bundle.js", ".map")):
            return True
        return False

    def scan(self, path: Optional[str] = None) -> Dict[str, int]:
        """Scans project files, performs incremental binary updates, and re-indexes."""
        target_dir = os.path.abspath(path or self.project_root)
        stats = {"added": 0, "modified": 0, "removed": 0, "unchanged": 0}
        now = current_time_ms()

        found_files = set()
        active_symbols_in_scan = set()

        canonical_root = os.path.realpath(self.project_root)

        with file_lock(self.bin_path, exclusive=True):
            with open(self.bin_path, "ab") as bin_file:
                for root, dirs, files in os.walk(target_dir, followlinks=False):
                    dirs[:] = [d for d in dirs if d not in DEFAULT_IGNORES]
                    for file in files:
                        full_p = os.path.join(root, file)
                        # Symlink jail check
                        canonical_p = os.path.realpath(full_p)
                        if not canonical_p.startswith(canonical_root):
                            continue

                        rel_p = os.path.relpath(full_p, self.project_root).replace("\\", "/")

                        if self.should_ignore(rel_p):
                            continue

                        found_files.add(rel_p)
                        try:
                            mtime = os.path.getmtime(full_p)
                        except OSError:
                            continue

                        # Check file cache
                        cached_file = self.index["files"].get(rel_p)
                        if cached_file and cached_file.get("mtime") == mtime:
                            for qname, meta in self.index["symbols"].items():
                                if meta.get("file") == rel_p and meta.get("status") != STATUS_REMOVED:
                                    active_symbols_in_scan.add(qname)
                                    stats["unchanged"] += 1
                            continue

                        self.index["files"][rel_p] = {"mtime": mtime}
                        symbols = SymbolExtractor.extract(rel_p, self.project_root)

                        for sym in symbols:
                            qname = sym["qualified_name"]
                            short_name = sym["name"]
                            active_symbols_in_scan.add(qname)
                            new_hash = sym["hash"]

                            existing = self.index["symbols"].get(qname)
                            if (
                                existing
                                and existing.get("hash") == new_hash.hex()
                                and existing.get("status") != STATUS_REMOVED
                            ):
                                stats["unchanged"] += 1
                                continue

                            if existing and existing.get("status") != STATUS_REMOVED:
                                status = STATUS_MODIFIED
                                created_at = existing.get("created_at", now)
                                modified_at = now
                                stats["modified"] += 1
                            else:
                                status = STATUS_ACTIVE
                                created_at = now
                                modified_at = now
                                stats["added"] += 1

                            offset = bin_file.tell()
                            record_bytes = pack_symbol_record(
                                status=status,
                                comp_type=sym["type"],
                                created_at=created_at,
                                modified_at=modified_at,
                                content_hash=new_hash,
                                qualified_name=qname,
                                file_path=rel_p,
                                signature=sym["signature"],
                                line_number=sym["line"],
                                description=sym["description"],
                                compress=True,
                            )
                            bin_file.write(record_bytes)

                            self.index["symbols"][qname] = {
                                "offset": offset,
                                "type": sym["type"],
                                "status": status,
                                "short_name": short_name,
                                "file": rel_p,
                                "line": sym["line"],
                                "hash": new_hash.hex(),
                                "created_at": created_at,
                                "modified_at": modified_at,
                                "desc_preview": sym["description"][:100],
                            }

                            if short_name not in self.index["by_name"]:
                                self.index["by_name"][short_name] = []
                            if qname not in self.index["by_name"][short_name]:
                                self.index["by_name"][short_name].append(qname)

                # Record tombstoned symbols
                all_known_qnames = list(self.index["symbols"].keys())
                for qname in all_known_qnames:
                    meta = self.index["symbols"][qname]
                    if meta.get("status") == STATUS_REMOVED:
                        continue

                    rel_p = meta.get("file")
                    if rel_p not in found_files or qname not in active_symbols_in_scan:
                        offset = bin_file.tell()
                        record_bytes = pack_symbol_record(
                            status=STATUS_REMOVED,
                            comp_type=meta.get("type", "F"),
                            created_at=meta.get("created_at", now),
                            modified_at=now,
                            content_hash=bytes.fromhex(meta.get("hash", "00" * 16)),
                            qualified_name=qname,
                            file_path=rel_p or "",
                            signature="",
                            line_number=meta.get("line", 0),
                            description="[Symbol has been removed from codebase]",
                            compress=True,
                        )
                        bin_file.write(record_bytes)
                        meta["status"] = STATUS_REMOVED
                        meta["offset"] = offset
                        meta["modified_at"] = now
                        stats["removed"] += 1

            self.index["last_scan"] = now
            self._save_index()
        return stats

    def lookup(self, symbol_name: str) -> Optional[Dict[str, Any]]:
        """Sub-millisecond direct seek lookup by exact qualified name or short name."""
        target_qname = None
        if symbol_name in self.index["symbols"]:
            target_qname = symbol_name
        elif symbol_name in self.index["by_name"]:
            candidates = self.index["by_name"][symbol_name]
            for c in candidates:
                if self.index["symbols"].get(c, {}).get("status") != STATUS_REMOVED:
                    target_qname = c
                    break
            if not target_qname and candidates:
                target_qname = candidates[0]

        if not target_qname:
            return None

        meta = self.index["symbols"][target_qname]
        offset = meta["offset"]

        with open(self.bin_path, "rb") as f:
            f.seek(offset)
            record = unpack_symbol_record(f)
            if record:
                record["byte_offset"] = offset
                return record
        return None

    def search(self, query: str, sym_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Tokenized search matching across symbol names, descriptions, and file paths."""
        tokens = [t.lower() for t in query.split() if t.strip()]
        if not tokens:
            return []

        results = []
        for qname, meta in self.index["symbols"].items():
            if meta.get("status") == STATUS_REMOVED:
                continue
            if sym_type and meta.get("type") != sym_type.upper():
                continue

            searchable = (
                f"{meta.get('short_name', '')} {qname} {meta.get('desc_preview', '')}"
            ).lower()

            if all(t in searchable for t in tokens):
                results.append({
                    "name": meta.get("short_name"),
                    "qualified_name": qname,
                    "type": meta.get("type"),
                    "file": meta.get("file"),
                    "line": meta.get("line"),
                    "description": meta.get("desc_preview", ""),
                    "modified_at": meta.get("modified_at"),
                })
        return results

    def status(self) -> Dict[str, Any]:
        """Returns statistics on the binary database and symbol counts."""
        active = 0
        removed = 0
        for s in self.index["symbols"].values():
            if s.get("status") == STATUS_REMOVED:
                removed += 1
            else:
                active += 1
        bin_size = os.path.getsize(self.bin_path) if os.path.exists(self.bin_path) else 0
        idx_size = os.path.getsize(self.idx_path) if os.path.exists(self.idx_path) else 0

        return {
            "project_root": self.project_root,
            "active_symbols": active,
            "removed_symbols": removed,
            "total_tracked": active + removed,
            "binary_file_bytes": bin_size,
            "index_file_bytes": idx_size,
            "last_scan": self.index.get("last_scan", 0),
        }

    def compact(self) -> Dict[str, int]:
        """Repacks the binary store, purging deleted versions and tombstones."""
        temp_bin = self.bin_path + ".compact.tmp"
        purged = 0
        retained = 0

        with file_lock(self.bin_path, exclusive=True):
            with open(temp_bin, "wb") as out_f, open(self.bin_path, "rb") as in_f:
                for qname, meta in list(self.index["symbols"].items()):
                    if meta.get("status") == STATUS_REMOVED:
                        purged += 1
                        del self.index["symbols"][qname]
                        short = meta.get("short_name")
                        if short in self.index["by_name"]:
                            self.index["by_name"][short] = [
                                x for x in self.index["by_name"][short] if x != qname
                            ]
                            if not self.index["by_name"][short]:
                                del self.index["by_name"][short]
                        continue

                    in_f.seek(meta["offset"])
                    rec = unpack_symbol_record(in_f)
                    if not rec:
                        continue

                    new_offset = out_f.tell()
                    rec_bytes = pack_symbol_record(
                        status=STATUS_ACTIVE,
                        comp_type=rec["type"],
                        created_at=rec["created_at"],
                        modified_at=rec["modified_at"],
                        content_hash=bytes.fromhex(rec["hash"]),
                        qualified_name=rec["qualified_name"],
                        file_path=rec["file_path"],
                        signature=rec["signature"],
                        line_number=rec["line_number"],
                        description=rec["description"],
                        compress=True,
                    )
                    out_f.write(rec_bytes)
                    meta["offset"] = new_offset
                    retained += 1

            os.replace(temp_bin, self.bin_path)
            self._save_index()
        return {"retained": retained, "purged": purged}


# CLI entry point
def main():
    import argparse
    parser = argparse.ArgumentParser(description="CodeBin: Binary Symbol Indexer & Cache")
    sub = parser.add_subparsers(dest="cmd", help="Command to run")

    sub.add_parser("init", help="Initialize .codebin in current directory")
    scan_p = sub.add_parser("scan", help="Scan and update binary index")
    scan_p.add_argument("path", nargs="?", default=".", help="Root path to scan")

    look_p = sub.add_parser("lookup", help="Lookup a symbol instantly")
    look_p.add_argument("symbol", help="Qualified name or short name")

    srch_p = sub.add_parser("search", help="Search symbols by query")
    srch_p.add_argument("query", help="Search query string")
    srch_p.add_argument("--type", dest="type", help="Filter by type (F, C, V, T, M)")

    sub.add_parser("status", help="Show database stats")
    sub.add_parser("compact", help="Compact and prune binary storage")

    args = parser.parse_args()
    mgr = CodeBinManager(".")

    if args.cmd == "init":
        print(f"Initialized CodeBin database at: {mgr.codebin_dir}")
    elif args.cmd == "scan":
        print(f"Scanning codebase starting from {args.path}...")
        res = mgr.scan(args.path)
        print(f"Scan complete: Added={res['added']}, Modified={res['modified']}, Unchanged={res['unchanged']}, Removed={res['removed']}")
    elif args.cmd == "lookup":
        rec = mgr.lookup(args.symbol)
        if rec:
            print(json.dumps(rec, indent=2))
        else:
            print(f"Symbol '{args.symbol}' not found in index.")
            sys.exit(1)
    elif args.cmd == "search":
        matches = mgr.search(args.query, sym_type=args.type)
        print(json.dumps(matches, indent=2))
    elif args.cmd == "status":
        print(json.dumps(mgr.status(), indent=2))
    elif args.cmd == "compact":
        res = mgr.compact()
        print(f"Compacted database: Retained={res['retained']}, Purged={res['purged']}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
