"""Shared plumbing for resource classes.

Sync and async resources differ only in awaiting the transport; all request
building and response parsing is delegated to pure functions in
``kicbac._core`` so the two client flavours cannot drift apart.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, TypeVar

import httpx

from kicbac._core import build_transact_request, parse_transact_body
from kicbac._transport import AsyncTransport, SyncTransport

T_co = TypeVar("T_co", covariant=True)


class ResponseParser(Protocol[T_co]):
    """Shape of the pure ``kicbac._core`` result builders."""

    def __call__(
        self,
        fields: Mapping[str, str],
        *,
        raw_body: str,
        request_params: Mapping[str, str] | None = None,
    ) -> T_co: ...


class SyncResource:
    def __init__(self, transport: SyncTransport, security_key: str) -> None:
        self._transport = transport
        self._security_key = security_key

    def _transact(
        self,
        params: Mapping[str, str],
        parse: ResponseParser[T_co],
        *,
        timeout: float | httpx.Timeout | None,
    ) -> T_co:
        spec = build_transact_request(self._security_key, params)
        body = self._transport.request(spec, timeout=timeout)
        return parse(parse_transact_body(body), raw_body=body, request_params=spec.data)


class AsyncResource:
    def __init__(self, transport: AsyncTransport, security_key: str) -> None:
        self._transport = transport
        self._security_key = security_key

    async def _transact(
        self,
        params: Mapping[str, str],
        parse: ResponseParser[T_co],
        *,
        timeout: float | httpx.Timeout | None,
    ) -> T_co:
        spec = build_transact_request(self._security_key, params)
        body = await self._transport.request(spec, timeout=timeout)
        return parse(parse_transact_body(body), raw_body=body, request_params=spec.data)
