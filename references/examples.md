# CodeBin Real-World Use Cases & Practical Examples

This document demonstrates concrete scenarios where **CodeBin** should be used by developers and AI agents to save tokens, accelerate workflows, and maintain deterministic codebase context.

---

## Scenario 1: Exploring Large Codebases Without Context Window Exhaustion

### The Problem
A user asks: *"What does our `processPayment` pipeline do?"*  
In traditional agent setups, the AI reads 15 files (`checkout.ts`, `stripe.ts`, `paypal.ts`, `database.ts`, `types.ts`, etc.), loading over **45,000 tokens** into context. The session slows down, context degradation begins, and token costs spike.

### The CodeBin Solution
The agent calls `codebin_lookup("processPayment")`.

```python
from scripts.tool_codebin import codebin_lookup

result = codebin_lookup("processPayment")
```

**Output (< 100 tokens consumed):**
```json
{
  "found": true,
  "name": "src/services/billing.ts::processPayment",
  "type": "F",
  "status": "active",
  "signature": "export async function processPayment(orderId: string, amount: number, method: PaymentMethod): Promise<PaymentReceipt>",
  "file": "src/services/billing.ts",
  "line": 142,
  "description": "Orchestrates multi-provider transactions with automatic retries and webhook dispatch.",
  "created_at": 1730000000000,
  "modified_at": 1730250000000
}
```
**Result:** The AI answers accurately in 2 seconds, saving **99.8% of tokens**.

---

## Scenario 2: Verifying Function Parameters Before Refactoring

### The Problem
When refactoring or adding a feature, an AI needs to know the exact parameters of a utility function in another directory without switching files.

### The CodeBin Solution
The AI executes a lookup on `format_currency`:

```python
result = codebin_lookup("format_currency")
```

```json
{
  "found": true,
  "name": "utils/finance.py::format_currency",
  "type": "F",
  "status": "active",
  "signature": "def format_currency(amount: float, currency_code: str = 'USD', precision: int = 2) -> str",
  "file": "utils/finance.py",
  "line": 18,
  "description": "Formats numeric values into localized currency strings with ISO symbol prefixes."
}
```

The agent writes the calling code with exact parameter names and types without ever reading `utils/finance.py`.

---

## Scenario 3: Fuzzy / Natural Language Concept Search

### The Problem
The user asks: *"Where in the codebase do we handle user authentication session validation?"*  
The user doesn't know the exact function name (`verify_jwt_token`).

### The CodeBin Solution
The agent calls `codebin_search` with query keywords:

```python
from scripts.tool_codebin import codebin_search

results = codebin_search("user session validation")
```

**Output:**
```json
{
  "count": 2,
  "matches": [
    {
      "name": "verify_jwt_token",
      "qualified_name": "src/security/auth.py::verify_jwt_token",
      "type": "F",
      "file": "src/security/auth.py",
      "line": 56,
      "description": "Decodes and validates user session credentials, signature, and expiration."
    },
    {
      "name": "SessionValidator",
      "qualified_name": "src/middleware/session.py::SessionValidator",
      "type": "C",
      "file": "src/middleware/session.py",
      "line": 12,
      "description": "Middleware interceptor ensuring valid user session cookie presence."
    }
  ]
}
```

---

## Scenario 4: Change & Tombstone Auditing ("Did someone delete X?")

### The Problem
During development, a developer asks: *"Did we delete the legacy webhook handler or is it still in the codebase?"*

### The CodeBin Solution
The agent looks up the symbol:

```python
result = codebin_lookup("src/api/webhooks.py::handle_legacy_event")
```

```json
{
  "found": true,
  "name": "src/api/webhooks.py::handle_legacy_event",
  "type": "F",
  "status": "removed",
  "signature": "",
  "file": "src/api/webhooks.py",
  "line": 84,
  "description": "[Symbol has been removed from codebase]",
  "created_at": 1729000000000,
  "modified_at": 1730248000000
}
```
**Result:** The AI explains: *"The function `handle_legacy_event` was removed during the recent code scan at timestamp 1730248000000."*

---

## Scenario 5: Multi-Language Full-Stack Projects

### The Problem
In full-stack repositories (e.g. Next.js TypeScript frontend + FastAPI Python backend), an AI agent needs to coordinate data models across both sides.

### The CodeBin Solution
CodeBin extracts symbols from both ecosystems into the unified binary repository:
- `frontend/src/types/user.ts::UserDTO` (Type)
- `frontend/src/api/user.ts::fetchUserProfile` (Function with JSDoc)
- `backend/app/models.py::UserModel` (SQLAlchemy / Pydantic Class)
- `backend/app/routes.py::get_user` (FastAPI route with `@app.get` decorator)

The agent can query symbols across the whole stack seamlessly.

---

## Scenario 6: Model Context Protocol (MCP) Configuration

To use CodeBin inside **Claude Desktop**, **Cursor**, or **Windsurf**, add CodeBin to your MCP configuration file:

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
The AI assistant will automatically consult CodeBin when answering technical codebase questions.
