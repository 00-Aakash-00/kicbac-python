# kicbac

Official Python SDK for the [Kicbac](https://www.kicbac.com/) payments gateway. Sync and async clients, fully typed (`py.typed`, mypy `--strict` clean), zero raw-card handling.

```sh
pip install kicbac
```

## Quickstart (sync)

```python
import kicbac

client = kicbac.Kicbac()  # reads KICBAC_SECURITY_KEY from the environment

# `payment_token` comes from the browser (Kicbac.js / @kicbac/react) — raw
# card data never touches your server.
result = client.transactions.sale(amount="19.99", payment_token="tok_from_browser")

if result.ok:
    print("approved:", result.transaction_id, result.auth_code)
else:
    # Declines are RESULTS, not exceptions — branch on them, don't catch them.
    print("declined:", result.response_code, result.message)
```

## Async

```python
import asyncio
import kicbac

async def main() -> None:
    async with kicbac.AsyncKicbac() as client:
        result = await client.transactions.sale(amount="19.99", payment_token="tok")
        print(result.ok, result.response_code)

asyncio.run(main())
```

The sync `Kicbac` and async `AsyncKicbac` share identical method signatures; every
request-building and response-parsing path is the same pure code, so the two
clients can never drift.

## Save a card and charge it later (Customer Vault)

```python
client = kicbac.Kicbac()

vault = client.customers.create(payment_token="tok_from_browser")
# Later — a merchant-initiated charge of a stored credential:
charge = client.customers.charge(
    vault.customer_vault_id,
    amount="9.99",
    initiated_by="merchant",
    stored_credential_indicator="used",
    initial_transaction_id="<first transaction id>",
)
```

## Error handling

Declines (`response=2`) are typed results. Gateway/processor errors (`response=3`),
auth failures, rate limits, and transport failures are raised:

```python
from kicbac.errors import (
    AuthenticationError,   # bad security key
    RateLimitError,        # HTTP 429 or response_code 301
    ProcessorError,        # processor-side error (4xx response codes)
    APIConnectionError,    # network failure before/around the request
    APITimeoutError,       # request timed out
)

try:
    result = client.transactions.sale(amount="19.99", payment_token="tok")
except AuthenticationError:
    ...  # rotate / fix KICBAC_SECURITY_KEY
except APIConnectionError as exc:
    # transact.php is NOT idempotent and is NOT auto-retried after the request
    # may have been sent. Reconcile with client.query before retrying a charge.
    ...
```

## Query API

Reports are lazy iterators that fetch pages (`result_limit`/`page_number`)
only as you consume them:

```python
for txn in client.query.transactions(
    condition=["pendingsettlement", "complete"],
    start_date="20260101",
):
    print(txn.transaction_id, txn.condition, [a.action_type for a in txn.actions])

# AsyncKicbac returns AsyncIterators:
#   async for txn in client.query.transactions(...): ...
```

Also available: `query.customers()`, `query.subscriptions()`, `query.plans()`,
and `query.invoices()`.

## Webhooks

Verify the signature against the **exact raw request bytes** — never re-parse and
re-serialize first.

### FastAPI

```python
from fastapi import FastAPI, Request, Response
import kicbac
from kicbac.errors import SignatureVerificationError, WebhookPayloadError

app = FastAPI()

@app.post("/webhooks/kicbac")
async def kicbac_webhook(request: Request) -> Response:
    payload = await request.body()  # raw bytes
    sig = request.headers.get("Webhook-Signature")
    try:
        event = kicbac.construct_event(payload, sig, SIGNING_KEY)
    except (SignatureVerificationError, WebhookPayloadError):
        return Response(status_code=400)

    # Deduplicate on event.event_id — the gateway retries ~20x over 3 days.
    if event.event_type == "transaction.sale.success":
        ...
    return Response(status_code=200)
```

### Flask

```python
import kicbac
from flask import Flask, request

app = Flask(__name__)

@app.post("/webhooks/kicbac")
def kicbac_webhook():
    try:
        event = kicbac.construct_event(
            request.get_data(),  # exact bytes, not request.form/json
            request.headers.get("Webhook-Signature"),
            SIGNING_KEY,
        )
    except kicbac.errors.KicbacError:
        return "", 400
    ...
    return "", 200
```

## Notes

- Money is a `str` or `Decimal` (`"49.99"`); `float` is rejected to avoid cent-rounding bugs.
- Card/bank numbers, CVV, and the security key are never logged — they are redacted in every error.
- The signature header's `t=` value is a nonce, not a timestamp; deduplicate webhooks by `event_id`.
- Every call accepts `timeout=` (float or `httpx.Timeout`) and an
  `extra_params={"gateway_field": "value"}` escape hatch for fields the SDK
  does not model. Client defaults: 30 s total / 5 s connect timeout,
  `max_retries=2`, bring-your-own `http_client=` supported (never closed by
  the SDK).
- Retry policy: `transact.php` is retried only on failures where no request
  bytes were sent (`ConnectError`/`ConnectTimeout`/`PoolTimeout`); `query.php`
  retries all transport errors; HTTP 429 / code 301 are never retried.
