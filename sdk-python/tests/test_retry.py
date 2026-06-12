"""Double-charge invariant: which httpx failures are retried, and where.

transact.php: retried ONLY on pre-send failures (ConnectError/ConnectTimeout/
PoolTimeout). Mid-flight failures (Read*/Write*/RemoteProtocolError) are never
retried — the charge may have gone through. query.php retries everything.
HTTP 429 is never retried anywhere.
"""

from __future__ import annotations

import httpx
import pytest
from conftest import QUERY_URL, TRANSACT_URL, approved_body, collect, maybe_await

import kicbac._transport as transport_mod
from kicbac.errors import APIConnectionError, APITimeoutError, RateLimitError

# (endpoint, exception, expected call count, expected error class)
# max_retries=2, so retryable failures are attempted 1 + 2 = 3 times.
RETRY_TABLE = [
    ("transact", httpx.ConnectError("boom"), 3, APIConnectionError),
    ("transact", httpx.ConnectTimeout("boom"), 3, APITimeoutError),
    ("transact", httpx.PoolTimeout("boom"), 3, APITimeoutError),
    ("transact", httpx.ReadTimeout("boom"), 1, APITimeoutError),
    ("transact", httpx.WriteTimeout("boom"), 1, APITimeoutError),
    ("transact", httpx.ReadError("boom"), 1, APIConnectionError),
    ("transact", httpx.WriteError("boom"), 1, APIConnectionError),
    ("transact", httpx.RemoteProtocolError("boom"), 1, APIConnectionError),
    ("query", httpx.ConnectError("boom"), 3, APIConnectionError),
    ("query", httpx.ConnectTimeout("boom"), 3, APITimeoutError),
    ("query", httpx.PoolTimeout("boom"), 3, APITimeoutError),
    ("query", httpx.ReadTimeout("boom"), 3, APITimeoutError),
    ("query", httpx.WriteTimeout("boom"), 3, APITimeoutError),
    ("query", httpx.ReadError("boom"), 3, APIConnectionError),
    ("query", httpx.WriteError("boom"), 3, APIConnectionError),
    ("query", httpx.RemoteProtocolError("boom"), 3, APIConnectionError),
]


@pytest.fixture
def recorded_sleeps(monkeypatch):
    delays: list[float] = []

    def fake_sleep(seconds: float) -> None:
        delays.append(seconds)

    async def fake_async_sleep(seconds: float) -> None:
        delays.append(seconds)

    monkeypatch.setattr(transport_mod, "_sleep", fake_sleep)
    monkeypatch.setattr(transport_mod, "_async_sleep", fake_async_sleep)
    return delays


async def _call(client, endpoint: str):
    if endpoint == "transact":
        return await maybe_await(client.transactions.sale(amount="10.00", payment_token="tok"))
    return await collect(client.query.transactions())


@pytest.mark.parametrize(
    ("endpoint", "exc", "expected_calls", "expected_error"),
    RETRY_TABLE,
    ids=[f"{endpoint}-{type(exc).__name__}" for endpoint, exc, _, _ in RETRY_TABLE],
)
async def test_retry_table(
    client, respx_mock, recorded_sleeps, endpoint, exc, expected_calls, expected_error
):
    url = TRANSACT_URL if endpoint == "transact" else QUERY_URL
    route = respx_mock.post(url).mock(side_effect=exc)
    with pytest.raises(expected_error) as excinfo:
        await _call(client, endpoint)
    assert route.call_count == expected_calls
    assert len(recorded_sleeps) == expected_calls - 1
    assert excinfo.value.__cause__ is exc


async def test_transact_mid_flight_failure_error_says_reconcile(
    client, respx_mock, recorded_sleeps
):
    respx_mock.post(TRANSACT_URL).mock(side_effect=httpx.ReadTimeout("boom"))
    with pytest.raises(APITimeoutError, match="reconcile"):
        await _call(client, "transact")
    assert recorded_sleeps == []  # never slept: never retried


async def test_connect_failure_recovers_on_retry(client, respx_mock, recorded_sleeps):
    route = respx_mock.post(TRANSACT_URL)
    route.side_effect = [
        httpx.ConnectError("boom"),
        httpx.Response(200, text=approved_body()),
    ]
    result = await maybe_await(client.transactions.sale(amount="10.00", payment_token="tok"))
    assert result.ok is True
    assert route.call_count == 2
    assert len(recorded_sleeps) == 1


async def test_sleeps_follow_jittered_exponential_backoff(client, respx_mock, recorded_sleeps):
    respx_mock.post(TRANSACT_URL).mock(side_effect=httpx.ConnectError("boom"))
    with pytest.raises(APIConnectionError):
        await _call(client, "transact")
    assert len(recorded_sleeps) == 2
    # attempt 0: min(2.0, 0.5) * uniform(0.5, 1.0) -> [0.25, 0.5]
    assert 0.25 <= recorded_sleeps[0] <= 0.5
    # attempt 1: min(2.0, 1.0) * uniform(0.5, 1.0) -> [0.5, 1.0]
    assert 0.5 <= recorded_sleeps[1] <= 1.0


@pytest.mark.parametrize("endpoint", ["transact", "query"])
async def test_http_429_raises_rate_limit_error_without_retry(
    client, respx_mock, recorded_sleeps, endpoint
):
    url = TRANSACT_URL if endpoint == "transact" else QUERY_URL
    route = respx_mock.post(url).mock(return_value=httpx.Response(429, text="Too Many Requests"))
    with pytest.raises(RateLimitError, match="429"):
        await _call(client, endpoint)
    assert route.call_count == 1
    assert recorded_sleeps == []


async def test_max_retries_zero_disables_retries(respx_mock, recorded_sleeps):
    from kicbac import Kicbac

    route = respx_mock.post(TRANSACT_URL).mock(side_effect=httpx.ConnectError("boom"))
    with (
        Kicbac(security_key="test_key", max_retries=0) as client,
        pytest.raises(APIConnectionError),
    ):
        client.transactions.sale(amount="10.00", payment_token="tok")
    assert route.call_count == 1
    assert recorded_sleeps == []
