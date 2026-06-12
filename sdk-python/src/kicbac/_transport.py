"""HTTP transports: the only sync/async-duplicated code in the SDK.

Double-charge invariant (do not weaken): ``transact.php`` POSTs are retried
ONLY on failures where no request bytes were sent (``httpx.ConnectError``,
``httpx.ConnectTimeout``, ``httpx.PoolTimeout``). Read/write/protocol errors
after the request may have been sent are NEVER retried for transact —
the gateway may have processed the charge. ``query.php`` is idempotent and
retries all transport errors. HTTP 429 / gateway code 301 are never retried.
"""

from __future__ import annotations

import asyncio
import time

import httpx

from kicbac._constants import QUERY_PATH, TRANSACT_PATH
from kicbac._core import RequestSpec, backoff_delay
from kicbac.errors import APIConnectionError, APITimeoutError, RateLimitError

_FORM_HEADERS = {"Content-Type": "application/x-www-form-urlencoded"}

# Failures guaranteed to happen before any request bytes reach the gateway.
PRE_SEND_ERRORS: tuple[type[httpx.TransportError], ...] = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.PoolTimeout,
)
# query.php is idempotent, so mid-flight failures may be retried too.
QUERY_RETRYABLE_ERRORS: tuple[type[httpx.TransportError], ...] = (
    *PRE_SEND_ERRORS,
    httpx.WriteError,
    httpx.WriteTimeout,
    httpx.ReadError,
    httpx.ReadTimeout,
    httpx.RemoteProtocolError,
)

# Module-level so tests can monkeypatch the sleeps.
_sleep = time.sleep
_async_sleep = asyncio.sleep


def _retryable_for(path: str) -> tuple[type[httpx.TransportError], ...]:
    # Anything that is not query.php gets the conservative transact policy.
    return QUERY_RETRYABLE_ERRORS if path == QUERY_PATH else PRE_SEND_ERRORS


def _connection_error(
    exc: httpx.TransportError, *, path: str, attempts: int, spec: RequestSpec
) -> APIConnectionError:
    error_class = APITimeoutError if isinstance(exc, httpx.TimeoutException) else APIConnectionError
    name = type(exc).__name__
    if isinstance(exc, PRE_SEND_ERRORS):
        detail = (
            f"could not connect ({name}) after {attempts} attempt(s); "
            "no request bytes were sent, so it is safe to retry"
        )
    elif path == TRANSACT_PATH:
        detail = (
            f"{name} after the request was sent; the transaction MAY still have been "
            "processed by the gateway — do not blindly resubmit; reconcile with the "
            "Query API (client.query.transactions) first"
        )
    else:
        detail = f"{name} after retries were exhausted; the query is safe to retry"
    return error_class(f"request to {path} failed: {detail}", params=spec.data)


def _rate_limit_error(response: httpx.Response, *, spec: RequestSpec) -> RateLimitError:
    return RateLimitError(
        "gateway returned HTTP 429 (system-wide rate limit); the SDK never retries "
        "rate-limited requests — back off before resubmitting",
        params=spec.data,
        raw_body=response.text,
    )


class SyncTransport:
    def __init__(
        self,
        http: httpx.Client,
        *,
        base_url: str,
        max_retries: int,
        timeout: float | httpx.Timeout,
    ) -> None:
        self._http = http
        self._base_url = base_url.rstrip("/")
        self._max_retries = max_retries
        self._timeout = timeout

    def request(self, spec: RequestSpec, *, timeout: float | httpx.Timeout | None = None) -> str:
        retry_on = _retryable_for(spec.path)
        url = self._base_url + spec.path
        body = spec.body
        attempt = 0
        while True:
            try:
                response = self._http.request(
                    "POST",
                    url,
                    content=body,
                    headers=_FORM_HEADERS,
                    timeout=self._timeout if timeout is None else timeout,
                )
            except httpx.TransportError as exc:
                if isinstance(exc, retry_on) and attempt < self._max_retries:
                    _sleep(backoff_delay(attempt))
                    attempt += 1
                    continue
                raise _connection_error(
                    exc, path=spec.path, attempts=attempt + 1, spec=spec
                ) from exc
            if response.status_code == 429:
                raise _rate_limit_error(response, spec=spec)
            return response.text


class AsyncTransport:
    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        base_url: str,
        max_retries: int,
        timeout: float | httpx.Timeout,
    ) -> None:
        self._http = http
        self._base_url = base_url.rstrip("/")
        self._max_retries = max_retries
        self._timeout = timeout

    async def request(
        self, spec: RequestSpec, *, timeout: float | httpx.Timeout | None = None
    ) -> str:
        retry_on = _retryable_for(spec.path)
        url = self._base_url + spec.path
        body = spec.body
        attempt = 0
        while True:
            try:
                response = await self._http.request(
                    "POST",
                    url,
                    content=body,
                    headers=_FORM_HEADERS,
                    timeout=self._timeout if timeout is None else timeout,
                )
            except httpx.TransportError as exc:
                if isinstance(exc, retry_on) and attempt < self._max_retries:
                    await _async_sleep(backoff_delay(attempt))
                    attempt += 1
                    continue
                raise _connection_error(
                    exc, path=spec.path, attempts=attempt + 1, spec=spec
                ) from exc
            if response.status_code == 429:
                raise _rate_limit_error(response, spec=spec)
            return response.text
