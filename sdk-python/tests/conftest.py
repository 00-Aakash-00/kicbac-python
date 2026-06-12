from __future__ import annotations

import inspect
from typing import Any
from urllib.parse import urlencode

import pytest

from kicbac import AsyncKicbac, Kicbac

BASE_URL = "https://kicbac.transactiongateway.com"
TRANSACT_URL = f"{BASE_URL}/api/transact.php"
QUERY_URL = f"{BASE_URL}/api/query.php"


@pytest.fixture(params=["sync", "async"])
async def client(request):
    """Yield a Kicbac then an AsyncKicbac client so every test runs against both."""
    if request.param == "sync":
        sync_client = Kicbac(security_key="test_key")
        yield sync_client
        sync_client.close()
    else:
        async_client = AsyncKicbac(security_key="test_key")
        yield async_client
        await async_client.aclose()


async def maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def collect(iterable: Any) -> list[Any]:
    """Drain a sync Iterator or an AsyncIterator into a list."""
    if hasattr(iterable, "__aiter__"):
        return [item async for item in iterable]
    return list(iterable)


async def take_one(iterable: Any) -> Any:
    if hasattr(iterable, "__aiter__"):
        return await iterable.__anext__()
    return next(iterable)


def gateway_body(**fields: str) -> str:
    return urlencode(fields)


def approved_body(**overrides: str) -> str:
    fields = {
        "response": "1",
        "responsetext": "SUCCESS",
        "authcode": "123456",
        "transactionid": "9876543210",
        "avsresponse": "N",
        "cvvresponse": "M",
        "orderid": "",
        "type": "sale",
        "response_code": "100",
    }
    fields.update(overrides)
    return urlencode(fields)
