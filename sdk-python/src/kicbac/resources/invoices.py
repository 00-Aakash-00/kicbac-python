"""Invoicing operations (``invoicing=add/update/send/close_invoice``)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import httpx

from kicbac._core import invoice_result
from kicbac._encode import encode_amount, encode_billing, encode_csv, encode_shipping, put
from kicbac.errors import InvalidRequestError
from kicbac.models.results import InvoiceResult
from kicbac.resources._base import AsyncResource, SyncResource
from kicbac.types import BillingParams, Money, ShippingParams

__all__ = ["AsyncInvoices", "Invoices"]


def _encode_payment_terms(value: str | int) -> str:
    if isinstance(value, bool) or (isinstance(value, int) and not 0 <= value <= 999):
        raise InvalidRequestError(
            f"invalid payment_terms {value!r}: expected 'upon_receipt' or days 0-999"
        )
    if isinstance(value, str) and value != "upon_receipt" and not value.isdigit():
        raise InvalidRequestError(
            f"invalid payment_terms {value!r}: expected 'upon_receipt' or days 0-999"
        )
    return str(value)


def _create_params(
    *,
    amount: Money,
    email: str,
    payment_terms: str | int,
    payment_methods_allowed: Sequence[str] | None,
    currency: str | None,
    order_id: str | None,
    order_description: str | None,
    customer_id: str | None,
    billing: BillingParams | None,
    shipping: ShippingParams | None,
    extra_params: Mapping[str, str] | None,
) -> dict[str, str]:
    params: dict[str, str] = {
        "invoicing": "add_invoice",
        "amount": encode_amount(amount),
        "email": email,
        "payment_terms": _encode_payment_terms(payment_terms),
    }
    if payment_methods_allowed is not None:
        params["payment_methods_allowed"] = encode_csv(
            payment_methods_allowed, field="payment_methods_allowed"
        )
    put(params, "currency", currency)
    put(params, "orderid", order_id)
    put(params, "order_description", order_description)
    put(params, "customer_id", customer_id)
    if billing is not None:
        params.update(encode_billing(billing))
    if shipping is not None:
        params.update(encode_shipping(shipping))
    if extra_params is not None:
        params.update(extra_params)
    return params


def _update_params(
    invoice_id: str,
    *,
    amount: Money | None,
    email: str | None,
    payment_terms: str | int | None,
    payment_methods_allowed: Sequence[str] | None,
    order_id: str | None,
    order_description: str | None,
    customer_id: str | None,
    billing: BillingParams | None,
    shipping: ShippingParams | None,
    extra_params: Mapping[str, str] | None,
) -> dict[str, str]:
    params: dict[str, str] = {"invoicing": "update_invoice", "invoice_id": invoice_id}
    if amount is not None:
        params["amount"] = encode_amount(amount)
    put(params, "email", email)
    if payment_terms is not None:
        params["payment_terms"] = _encode_payment_terms(payment_terms)
    if payment_methods_allowed is not None:
        params["payment_methods_allowed"] = encode_csv(
            payment_methods_allowed, field="payment_methods_allowed"
        )
    put(params, "orderid", order_id)
    put(params, "order_description", order_description)
    put(params, "customer_id", customer_id)
    if billing is not None:
        params.update(encode_billing(billing))
    if shipping is not None:
        params.update(encode_shipping(shipping))
    if extra_params is not None:
        params.update(extra_params)
    return params


def _action_params(
    action: str, invoice_id: str, *, extra_params: Mapping[str, str] | None
) -> dict[str, str]:
    params: dict[str, str] = {"invoicing": action, "invoice_id": invoice_id}
    if extra_params is not None:
        params.update(extra_params)
    return params


class Invoices(SyncResource):
    """Sync invoicing operations."""

    def create(
        self,
        *,
        amount: Money,
        email: str,
        payment_terms: str | int = "upon_receipt",
        payment_methods_allowed: Sequence[str] | None = None,
        currency: str | None = None,
        order_id: str | None = None,
        order_description: str | None = None,
        customer_id: str | None = None,
        billing: BillingParams | None = None,
        shipping: ShippingParams | None = None,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> InvoiceResult:
        """Create an invoice and email it to the customer (``add_invoice``).

        ``payment_methods_allowed`` values: ``cc`` (card), ``ck`` (check),
        ``cs`` (cash).
        """
        params = _create_params(
            amount=amount,
            email=email,
            payment_terms=payment_terms,
            payment_methods_allowed=payment_methods_allowed,
            currency=currency,
            order_id=order_id,
            order_description=order_description,
            customer_id=customer_id,
            billing=billing,
            shipping=shipping,
            extra_params=extra_params,
        )
        return self._transact(params, invoice_result, timeout=timeout)

    def update(
        self,
        invoice_id: str,
        *,
        amount: Money | None = None,
        email: str | None = None,
        payment_terms: str | int | None = None,
        payment_methods_allowed: Sequence[str] | None = None,
        order_id: str | None = None,
        order_description: str | None = None,
        customer_id: str | None = None,
        billing: BillingParams | None = None,
        shipping: ShippingParams | None = None,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> InvoiceResult:
        """Update an open invoice (does not re-send it; use :meth:`send`)."""
        params = _update_params(
            invoice_id,
            amount=amount,
            email=email,
            payment_terms=payment_terms,
            payment_methods_allowed=payment_methods_allowed,
            order_id=order_id,
            order_description=order_description,
            customer_id=customer_id,
            billing=billing,
            shipping=shipping,
            extra_params=extra_params,
        )
        return self._transact(params, invoice_result, timeout=timeout)

    def send(
        self,
        invoice_id: str,
        *,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> InvoiceResult:
        """Email an existing invoice to its billing address (``send_invoice``)."""
        params = _action_params("send_invoice", invoice_id, extra_params=extra_params)
        return self._transact(params, invoice_result, timeout=timeout)

    def close(
        self,
        invoice_id: str,
        *,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> InvoiceResult:
        """Close an open invoice (``close_invoice``)."""
        params = _action_params("close_invoice", invoice_id, extra_params=extra_params)
        return self._transact(params, invoice_result, timeout=timeout)


class AsyncInvoices(AsyncResource):
    """Async invoicing operations."""

    async def create(
        self,
        *,
        amount: Money,
        email: str,
        payment_terms: str | int = "upon_receipt",
        payment_methods_allowed: Sequence[str] | None = None,
        currency: str | None = None,
        order_id: str | None = None,
        order_description: str | None = None,
        customer_id: str | None = None,
        billing: BillingParams | None = None,
        shipping: ShippingParams | None = None,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> InvoiceResult:
        """Create an invoice and email it to the customer (``add_invoice``).

        ``payment_methods_allowed`` values: ``cc`` (card), ``ck`` (check),
        ``cs`` (cash).
        """
        params = _create_params(
            amount=amount,
            email=email,
            payment_terms=payment_terms,
            payment_methods_allowed=payment_methods_allowed,
            currency=currency,
            order_id=order_id,
            order_description=order_description,
            customer_id=customer_id,
            billing=billing,
            shipping=shipping,
            extra_params=extra_params,
        )
        return await self._transact(params, invoice_result, timeout=timeout)

    async def update(
        self,
        invoice_id: str,
        *,
        amount: Money | None = None,
        email: str | None = None,
        payment_terms: str | int | None = None,
        payment_methods_allowed: Sequence[str] | None = None,
        order_id: str | None = None,
        order_description: str | None = None,
        customer_id: str | None = None,
        billing: BillingParams | None = None,
        shipping: ShippingParams | None = None,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> InvoiceResult:
        """Update an open invoice (does not re-send it; use :meth:`send`)."""
        params = _update_params(
            invoice_id,
            amount=amount,
            email=email,
            payment_terms=payment_terms,
            payment_methods_allowed=payment_methods_allowed,
            order_id=order_id,
            order_description=order_description,
            customer_id=customer_id,
            billing=billing,
            shipping=shipping,
            extra_params=extra_params,
        )
        return await self._transact(params, invoice_result, timeout=timeout)

    async def send(
        self,
        invoice_id: str,
        *,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> InvoiceResult:
        """Email an existing invoice to its billing address (``send_invoice``)."""
        params = _action_params("send_invoice", invoice_id, extra_params=extra_params)
        return await self._transact(params, invoice_result, timeout=timeout)

    async def close(
        self,
        invoice_id: str,
        *,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> InvoiceResult:
        """Close an open invoice (``close_invoice``)."""
        params = _action_params("close_invoice", invoice_id, extra_params=extra_params)
        return await self._transact(params, invoice_result, timeout=timeout)
