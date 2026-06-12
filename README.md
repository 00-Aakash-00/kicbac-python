# Kicbac Python SDK

Official Python SDK for the Kicbac payments gateway.

The package provides sync and async clients, typed results, Customer Vault, recurring billing, Query API support, and webhook verification.

## Install

```sh
pip install kicbac
```

## Quickstart

```python
import kicbac

client = kicbac.Kicbac()  # reads KICBAC_SECURITY_KEY

result = client.transactions.sale(
    amount="49.99",
    payment_token=token_from_collect_js,
)

if result.ok:
    print(result.transaction_id)
else:
    print("declined", result.response_code, result.message)
```

## Safety model

- Tokenize card and bank data in Kicbac.js hosted fields before calling your server.
- Send `payment_token` to this SDK. Do not send raw card numbers, CVV, routing numbers, or bank account numbers.
- `response=2` is a typed decline result and should be handled in normal control flow.
- `response=3`, authentication failures, processor errors, rate limits, validation errors, and transport failures raise typed exceptions.
- `transact.php` is not idempotent. The SDK only retries charge requests when it can prove no bytes were sent.

## Webhooks

Verify against the exact raw request bytes:

```python
import kicbac
from kicbac.errors import SignatureVerificationError, WebhookPayloadError

try:
    event = kicbac.construct_event(
        raw_body_bytes,
        request_headers.get("Webhook-Signature"),
        webhook_signing_key,
    )
except (SignatureVerificationError, WebhookPayloadError):
    return 400
```

The signature header is `Webhook-Signature: t=<nonce>,s=<sig>`. The signature is HMAC-SHA256 over `nonce + "." + rawBody`.

## Development

```sh
cd sdk-python
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
.venv/bin/mypy --strict src
.venv/bin/ruff check src tests
.venv/bin/ruff format --check src tests
.venv/bin/python -m build
```

The `openapi/` directory contains shared public fixtures used by tests. Keep it in sync with the JavaScript SDK repository.
