"""Default and per-call timeouts must reach the underlying httpx request."""

from __future__ import annotations

import httpx
from conftest import QUERY_URL, TRANSACT_URL, approved_body, collect, maybe_await

from kicbac import AsyncKicbac, Kicbac

EMPTY_XML = "<nm_response></nm_response>"


def request_timeout(route) -> dict[str, float | None]:
    return route.calls.last.request.extensions["timeout"]


async def test_default_timeout_is_30s_with_5s_connect(client, respx_mock):
    route = respx_mock.post(TRANSACT_URL).mock(
        return_value=httpx.Response(200, text=approved_body())
    )
    await maybe_await(client.transactions.sale(amount="1.00", payment_token="tok"))
    timeout = request_timeout(route)
    assert timeout["connect"] == 5.0
    assert timeout["read"] == 30.0
    assert timeout["write"] == 30.0
    assert timeout["pool"] == 30.0


async def test_per_call_timeout_overrides_default(client, respx_mock):
    route = respx_mock.post(TRANSACT_URL).mock(
        return_value=httpx.Response(200, text=approved_body())
    )
    await maybe_await(client.transactions.sale(amount="1.00", payment_token="tok", timeout=3.0))
    assert request_timeout(route) == {
        "connect": 3.0,
        "read": 3.0,
        "write": 3.0,
        "pool": 3.0,
    }


async def test_per_call_httpx_timeout_object(client, respx_mock):
    route = respx_mock.post(TRANSACT_URL).mock(
        return_value=httpx.Response(200, text=approved_body())
    )
    await maybe_await(
        client.transactions.sale(
            amount="1.00",
            payment_token="tok",
            timeout=httpx.Timeout(10.0, connect=2.0),
        )
    )
    timeout = request_timeout(route)
    assert timeout["connect"] == 2.0
    assert timeout["read"] == 10.0


async def test_query_per_call_timeout(client, respx_mock):
    route = respx_mock.post(QUERY_URL).mock(return_value=httpx.Response(200, text=EMPTY_XML))
    await collect(client.query.transactions(timeout=7.0))
    assert request_timeout(route)["read"] == 7.0


async def test_client_level_timeout_applies_everywhere(respx_mock):
    route = respx_mock.post(TRANSACT_URL).mock(
        return_value=httpx.Response(200, text=approved_body())
    )
    with Kicbac(security_key="test_key", timeout=12.0) as sync_client:
        sync_client.transactions.sale(amount="1.00", payment_token="tok")
    assert request_timeout(route)["read"] == 12.0
    async with AsyncKicbac(security_key="test_key", timeout=12.0) as async_client:
        await async_client.transactions.sale(amount="1.00", payment_token="tok")
    assert request_timeout(route)["read"] == 12.0
