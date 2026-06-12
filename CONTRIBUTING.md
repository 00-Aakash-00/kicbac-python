# Contributing

Thanks for improving the Kicbac Python SDK.

## Setup

```sh
cd sdk-python
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## Checks

```sh
cd sdk-python
.venv/bin/pytest
.venv/bin/mypy --strict src
.venv/bin/ruff check src tests
.venv/bin/ruff format --check src tests
.venv/bin/python -m build
```

## Guardrails

- Do not add raw-PAN convenience APIs. Use `payment_token`.
- Do not loosen retry behavior for `transact.php`.
- Keep sync and async clients sharing the same request-building and response-parsing code.
- Keep webhook verification byte-exact and constant-time.
- Keep shared tests pointed at `openapi/data/response-codes.json` and `openapi/webhooks/vectors.json`.
