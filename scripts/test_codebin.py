"""
Comprehensive self-check and verification test suite for CodeBin.
Tests binary packing/unpacking with zlib compression, JSDoc harvesting,
decorator preservation, incremental scanning, change tracking,
tombstoning, direct O(1) seek lookups, token search, and compaction.
"""

import os
import shutil
import sys
import tempfile
import time

_current_dir = os.path.dirname(os.path.abspath(__file__))
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from codebin_engine import (
    CodeBinManager,
    SymbolExtractor,
    STATUS_ACTIVE,
    STATUS_MODIFIED,
    STATUS_REMOVED,
    pack_symbol_record,
    unpack_symbol_record,
)


def test_pack_unpack_compression_roundtrip():
    hash_bytes = b"0123456789abcdef"
    large_desc = "Detailed explanation of cryptographic hashing. " * 20

    record_bytes = pack_symbol_record(
        status=STATUS_ACTIVE,
        comp_type="F",
        created_at=1730000000000,
        modified_at=1730000000000,
        content_hash=hash_bytes,
        qualified_name="crypto/signer.py::sign_payload",
        file_path="crypto/signer.py",
        signature="@dataclass async def sign_payload(payload: bytes, key: str) -> str",
        line_number=25,
        description=large_desc,
        compress=True,
    )

    unpacked = unpack_symbol_record(record_bytes)
    assert unpacked is not None, "Failed to unpack record"
    assert unpacked["status"] == "active"
    assert unpacked["type"] == "F"
    assert unpacked["qualified_name"] == "crypto/signer.py::sign_payload"
    assert unpacked["signature"] == "@dataclass async def sign_payload(payload: bytes, key: str) -> str"
    assert unpacked["description"] == large_desc
    assert unpacked["hash"] == hash_bytes.hex()
    print("✓ test_pack_unpack_compression_roundtrip passed")


def test_jsdoc_and_decorator_extraction():
    # 1. Test JSDoc in TypeScript
    ts_code = (
        "/**\n"
        " * Generates a signed JWT session cookie.\n"
        " * @param userId - Unique user identifier\n"
        " */\n"
        "export async function generateSession(userId: string): Promise<string> {\n"
        "  return 'token';\n"
        "}\n"
    )
    ts_symbols = SymbolExtractor.extract_from_generic("src/auth.ts", ts_code)
    assert len(ts_symbols) == 1, f"Expected 1 TS symbol, got {len(ts_symbols)}"
    assert ts_symbols[0]["name"] == "generateSession"
    assert "Generates a signed JWT session cookie" in ts_symbols[0]["description"]
    assert "@param userId" in ts_symbols[0]["description"]

    # 2. Test Python Decorators & Return Type
    py_code = (
        "@app.get('/metrics')\n"
        "@cache(ttl=60)\n"
        "async def get_system_metrics(filter_level: str) -> dict:\n"
        "    '''Retrieves server health and CPU load statistics.'''\n"
        "    return {}\n"
    )
    py_symbols = SymbolExtractor.extract_from_python("api/metrics.py", py_code)
    assert len(py_symbols) == 1
    assert py_symbols[0]["name"] == "get_system_metrics"
    assert "@app.get('/metrics')" in py_symbols[0]["signature"]
    assert "async def get_system_metrics" in py_symbols[0]["signature"]
    assert "-> dict" in py_symbols[0]["signature"]
    assert "Retrieves server health" in py_symbols[0]["description"]

    print("✓ test_jsdoc_and_decorator_extraction passed")


def test_codebin_lifecycle_and_token_search():
    tmp_dir = tempfile.mkdtemp(prefix="codebin_test_")
    try:
        # Create dummy Python & TS files
        py_file = os.path.join(tmp_dir, "auth_service.py")
        with open(py_file, "w", encoding="utf-8") as f:
            f.write(
                '"""Auth module"""\n\n'
                "def authenticate(username, token):\n"
                '    """Validates user session credentials against database."""\n'
                "    return True\n\n"
                "class UserManager:\n"
                '    """Handles user accounts and profile lifecycle."""\n'
                "    def get_user(self, user_id):\n"
                '        """Fetches profile record."""\n'
                "        return {}\n"
            )

        ts_file = os.path.join(tmp_dir, "client.ts")
        with open(ts_file, "w", encoding="utf-8") as f:
            f.write(
                "/** Handles HTTP network retry logic. */\n"
                "export async function fetchRetry(url: string) {\n"
                "  return fetch(url);\n"
                "}\n"
            )

        mgr = CodeBinManager(tmp_dir)

        # 1. Initial scan
        stats1 = mgr.scan()
        assert stats1["added"] == 4, f"Expected 4 added symbols, got {stats1['added']}"
        assert stats1["modified"] == 0

        # 2. Direct seek lookup
        auth_rec = mgr.lookup("authenticate")
        assert auth_rec is not None
        assert "Validates user session" in auth_rec["description"]

        ts_rec = mgr.lookup("fetchRetry")
        assert ts_rec is not None
        assert "HTTP network retry logic" in ts_rec["description"]

        # 3. Multi-token search (natural language query)
        matches = mgr.search("user credentials")
        assert len(matches) >= 1
        assert matches[0]["name"] == "authenticate"

        retry_matches = mgr.search("network retry")
        assert len(retry_matches) >= 1
        assert retry_matches[0]["name"] == "fetchRetry"

        # 4. Modify file (incremental update)
        time.sleep(0.05)
        with open(py_file, "w", encoding="utf-8") as f:
            f.write(
                '"""Auth module"""\n\n'
                "def authenticate(username, token):\n"
                '    """Updated: Validates user session credentials with MFA."""\n'
                "    return True\n\n"
                "class UserManager:\n"
                '    """Handles user accounts and profile lifecycle."""\n'
                "    def get_user(self, user_id):\n"
                '        """Fetches profile record."""\n'
                "        return {}\n"
            )

        stats2 = mgr.scan()
        assert stats2["modified"] == 1
        assert stats2["unchanged"] == 3

        auth_updated = mgr.lookup("authenticate")
        assert auth_updated["status"] == "modified"
        assert "with MFA" in auth_updated["description"]

        # 5. Delete symbol (tombstone)
        time.sleep(0.05)
        os.remove(ts_file)
        stats3 = mgr.scan()
        assert stats3["removed"] == 1

        ts_deleted = mgr.lookup("client.ts::fetchRetry")
        assert ts_deleted["status"] == "removed"

        # 6. Compaction (purge tombstones)
        c_stats = mgr.compact()
        assert c_stats["purged"] == 1
        assert c_stats["retained"] == 3
        assert mgr.lookup("client.ts::fetchRetry") is None

        print("✓ test_codebin_lifecycle_and_token_search passed")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    test_pack_unpack_compression_roundtrip()
    test_jsdoc_and_decorator_extraction()
    test_codebin_lifecycle_and_token_search()
    print("\nALL CODEBIN ENHANCED TESTS PASSED!")
