"""The ``Kicbac`` (sync) and ``AsyncKicbac`` clients."""

from __future__ import annotations

import os
from types import TracebackType

import httpx

from kicbac._constants import DEFAULT_BASE_URL, DEFAULT_MAX_RETRIES, DEFAULT_TIMEOUT
from kicbac._transport import AsyncTransport, SyncTransport
from kicbac.errors import AuthenticationError
from kicbac.resources import (
    AsyncCustomers,
    AsyncInvoices,
    AsyncPlans,
    AsyncQuery,
    AsyncSubscriptions,
    AsyncTransactions,
    Customers,
    Invoices,
    Plans,
    Query,
    Subscriptions,
    Transactions,
)
from kicbac.webhooks import WebhooksNamespace

__all__ = ["AsyncKicbac", "Kicbac"]

_ENV_KEY = "KICBAC_SECURITY_KEY"


def _resolve_security_key(security_key: str | None) -> str:
    key = security_key if security_key is not None else os.environ.get(_ENV_KEY)
    if not key:
        raise AuthenticationError(
            "no security key configured: pass Kicbac(security_key=...) or set the "
            f"{_ENV_KEY} environment variable (keys are issued in the gateway control "
            "panel under Settings > Security Keys)"
        )
    return key


class Kicbac:
    """Synchronous Kicbac gateway client.

    The ``timeout`` given here (default 30s total / 5s connect) is sent with
    every request, including on a bring-your-own ``http_client``; per-call
    ``timeout=`` arguments override it.
    """

    def __init__(
        self,
        *,
        security_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float | httpx.Timeout = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        http_client: httpx.Client | None = None,
    ) -> None:
        key = _resolve_security_key(security_key)
        self._base_url = base_url
        self._owns_http = http_client is None
        self._http = httpx.Client() if http_client is None else http_client
        transport = SyncTransport(
            self._http, base_url=base_url, max_retries=max_retries, timeout=timeout
        )
        self.transactions = Transactions(transport, key)
        self.customers = Customers(transport, key)
        self.plans = Plans(transport, key)
        self.subscriptions = Subscriptions(transport, key)
        self.invoices = Invoices(transport, key)
        self.query = Query(transport, key)
        self.webhooks = WebhooksNamespace()

    def close(self) -> None:
        """Close the underlying HTTP client (no-op for bring-your-own clients)."""
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> Kicbac:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"Kicbac(base_url={self._base_url!r}, security_key='[REDACTED]')"


class AsyncKicbac:
    """Asynchronous Kicbac gateway client (identical surface, ``async`` methods).

    Query reports return ``AsyncIterator``s; everything else mirrors
    :class:`Kicbac`.
    """

    def __init__(
        self,
        *,
        security_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float | httpx.Timeout = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        key = _resolve_security_key(security_key)
        self._base_url = base_url
        self._owns_http = http_client is None
        self._http = httpx.AsyncClient() if http_client is None else http_client
        transport = AsyncTransport(
            self._http, base_url=base_url, max_retries=max_retries, timeout=timeout
        )
        self.transactions = AsyncTransactions(transport, key)
        self.customers = AsyncCustomers(transport, key)
        self.plans = AsyncPlans(transport, key)
        self.subscriptions = AsyncSubscriptions(transport, key)
        self.invoices = AsyncInvoices(transport, key)
        self.query = AsyncQuery(transport, key)
        self.webhooks = WebhooksNamespace()

    async def aclose(self) -> None:
        """Close the underlying HTTP client (no-op for bring-your-own clients)."""
        if self._owns_http:
            await self._http.aclose()

    async def __aenter__(self) -> AsyncKicbac:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    def __repr__(self) -> str:
        return f"AsyncKicbac(base_url={self._base_url!r}, security_key='[REDACTED]')"
