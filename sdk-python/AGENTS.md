# AGENTS.md - `kicbac` Python SDK

Sync (`Kicbac`) + async (`AsyncKicbac`) client for the Kicbac gateway.

## Setup & gates

The `.venv` already exists with all dev deps — use it directly; never
`pip install` into it. (`uv` is not installed here; the `pyproject.toml` is
uv-compatible for when it is. Fresh setup, only if `.venv` is missing:
`python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"`.)

```sh
.venv/bin/pytest                       # offline suite (respx-mocked; never hits the gateway)
.venv/bin/mypy --strict src            # must be clean — public API has no `Any`
.venv/bin/ruff check src tests && .venv/bin/ruff format --check src tests
.venv/bin/python -m build              # wheel + sdist (must ship py.typed)
```

## Architecture (do not break)

- **`_core.py` is pure** (no I/O): `build_*_request`, `parse_transact_body`, `decide_outcome`. Both clients route through it so sync/async can't diverge — a test asserts byte-identical request bodies. Put new request/response logic here, not in the transport.
- **`_transport.py`** is the only sync/async-duplicated code: keep the two send loops mirror-identical.
- Resources define module-level pure param builders shared by the sync and async class in the same file.

## Non-negotiable invariants

- **Double-charge:** `transact.php` is retried ONLY on pre-send failures (`httpx.ConnectError`/`ConnectTimeout`/`PoolTimeout`). `ReadTimeout`/`WriteError`/`RemoteProtocolError` are NEVER retried on transact — the charge may already exist. `query.php` retries all of those. HTTP 429 / `response_code` 301 are never retried. Locked by `tests/test_retry.py` — do not loosen.
- **Declines are results, not exceptions:** `response=2` → `TransactionDeclined(ok=False)`; only `response=3`/transport failures raise.
- **Webhooks:** `construct_event` takes `bytes` (str → `TypeError`); HMAC-SHA256 over `nonce + "." + payload` exact bytes, `hmac.compare_digest`. Header parse is strict + bounded.
- **Redaction:** `ccnumber`/`cvv`/`checkaba`/`checkaccount`/`security_key`/`payment_token` are masked in every error message and repr (`_redact.py`). Never widen public types to leak raw card data; never add raw-PAN kwargs (use `extra_params` only for non-sensitive vars).

## Shared fixtures

Tests read the cross-language source of truth from the repo: `../openapi/data/response-codes.json` (outcome table — both SDKs must decode identically) and `../openapi/webhooks/vectors.json` (golden HMAC vectors). Don't fork these; regenerate vectors via `../openapi/scripts/make-vectors.mjs`.

## Sandbox tests

Live-gateway tests are marked `@pytest.mark.sandbox` and excluded by default (`addopts = -m 'not sandbox'`). They require real test credentials and must hard-assert the test base URL before any network call.
