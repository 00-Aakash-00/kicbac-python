"""transact.php transaction operations (sale/auth/capture/void/refund/...).

PCI guardrail: there are deliberately no raw-PAN kwargs (``ccnumber``/``cvv``)
— tokenize with Kicbac.js and pass ``payment_token``. ``extra_params`` is the
documented escape hatch for gateway fields the SDK does not model.

TODO(v2): ``type=offline`` and ``type=complete_partial_payment`` are out of
scope for v1.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Literal

import httpx

from kicbac._core import decide_outcome
from kicbac._encode import (
    encode_amount,
    encode_billing,
    encode_date,
    encode_dup_seconds,
    encode_shipping,
    put,
)
from kicbac._encode import (
    merchant_defined_fields as encode_mdf,
)
from kicbac.errors import InvalidRequestError
from kicbac.models.results import TransactionResult
from kicbac.resources._base import AsyncResource, SyncResource
from kicbac.types import BillingParams, Money, ShippingParams

__all__ = ["AsyncTransactions", "Transactions"]

VoidReason = Literal[
    "fraud",
    "user_cancel",
    "icc_rejected",
    "icc_card_removed",
    "icc_no_confirmation",
    "pos_timeout",
]
ShippingCarrier = Literal["ups", "fedex", "dhl", "usps"]


def _charge_params(
    type_: str,
    *,
    amount: Money | None,
    payment_token: str | None,
    customer_vault_id: str | None,
    billing_id: str | None,
    order_id: str | None,
    order_description: str | None,
    po_number: str | None,
    currency: str | None,
    ip_address: str | None,
    billing: BillingParams | None,
    shipping: ShippingParams | None,
    initiated_by: Literal["customer", "merchant"] | None,
    stored_credential_indicator: Literal["stored", "used"] | None,
    initial_transaction_id: str | None,
    test_mode: bool,
    dup_seconds: int | None,
    merchant_defined_fields: Mapping[int, str] | None,
    extra_params: Mapping[str, str] | None,
) -> dict[str, str]:
    if payment_token is None and customer_vault_id is None and not extra_params:
        raise InvalidRequestError(
            f"no payment method for type={type_}: pass payment_token (from Kicbac.js) or "
            "customer_vault_id, or supply gateway payment fields via extra_params"
        )
    params: dict[str, str] = {"type": type_}
    if amount is not None:
        params["amount"] = encode_amount(amount)
    put(params, "payment_token", payment_token)
    put(params, "customer_vault_id", customer_vault_id)
    put(params, "billing_id", billing_id)
    put(params, "orderid", order_id)
    put(params, "order_description", order_description)
    put(params, "ponumber", po_number)
    put(params, "currency", currency)
    put(params, "ipaddress", ip_address)
    if billing is not None:
        params.update(encode_billing(billing))
    if shipping is not None:
        params.update(encode_shipping(shipping))
    put(params, "initiated_by", initiated_by)
    put(params, "stored_credential_indicator", stored_credential_indicator)
    put(params, "initial_transaction_id", initial_transaction_id)
    if test_mode:
        params["test_mode"] = "enabled"
    if dup_seconds is not None:
        params["dup_seconds"] = encode_dup_seconds(dup_seconds)
    if merchant_defined_fields is not None:
        params.update(encode_mdf(merchant_defined_fields))
    if extra_params is not None:
        params.update(extra_params)
    return params


def _capture_params(
    transaction_id: str,
    *,
    amount: Money | None,
    extra_params: Mapping[str, str] | None,
) -> dict[str, str]:
    params: dict[str, str] = {"type": "capture", "transactionid": transaction_id}
    if amount is not None:
        params["amount"] = encode_amount(amount)
    if extra_params is not None:
        params.update(extra_params)
    return params


def _void_params(
    transaction_id: str,
    *,
    void_reason: VoidReason | None,
    extra_params: Mapping[str, str] | None,
) -> dict[str, str]:
    params: dict[str, str] = {"type": "void", "transactionid": transaction_id}
    put(params, "void_reason", void_reason)
    if extra_params is not None:
        params.update(extra_params)
    return params


def _refund_params(
    transaction_id: str,
    *,
    amount: Money | None,
    extra_params: Mapping[str, str] | None,
) -> dict[str, str]:
    params: dict[str, str] = {"type": "refund", "transactionid": transaction_id}
    if amount is not None:
        # 0.00 is the gateway's way of saying "refund the full settled amount".
        params["amount"] = encode_amount(amount, allow_zero=True)
    if extra_params is not None:
        params.update(extra_params)
    return params


def _update_params(
    transaction_id: str,
    *,
    shipping_carrier: ShippingCarrier | None,
    tracking_number: str | None,
    shipping_date: date | str | None,
    order_description: str | None,
    extra_params: Mapping[str, str] | None,
) -> dict[str, str]:
    params: dict[str, str] = {"type": "update", "transactionid": transaction_id}
    put(params, "shipping_carrier", shipping_carrier)
    put(params, "tracking_number", tracking_number)
    if shipping_date is not None:
        params["shipping_date"] = encode_date(shipping_date, field="shipping_date")
    put(params, "order_description", order_description)
    if extra_params is not None:
        params.update(extra_params)
    return params


class Transactions(SyncResource):
    """Sync transaction operations. Declines are returned (``ok=False``), never raised."""

    def sale(
        self,
        *,
        amount: Money,
        payment_token: str | None = None,
        customer_vault_id: str | None = None,
        billing_id: str | None = None,
        order_id: str | None = None,
        order_description: str | None = None,
        po_number: str | None = None,
        currency: str | None = None,
        ip_address: str | None = None,
        billing: BillingParams | None = None,
        shipping: ShippingParams | None = None,
        initiated_by: Literal["customer", "merchant"] | None = None,
        stored_credential_indicator: Literal["stored", "used"] | None = None,
        initial_transaction_id: str | None = None,
        test_mode: bool = False,
        dup_seconds: int | None = None,
        merchant_defined_fields: Mapping[int, str] | None = None,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> TransactionResult:
        """Charge immediately (``type=sale``): flagged for settlement on approval."""
        params = _charge_params(
            "sale",
            amount=amount,
            payment_token=payment_token,
            customer_vault_id=customer_vault_id,
            billing_id=billing_id,
            order_id=order_id,
            order_description=order_description,
            po_number=po_number,
            currency=currency,
            ip_address=ip_address,
            billing=billing,
            shipping=shipping,
            initiated_by=initiated_by,
            stored_credential_indicator=stored_credential_indicator,
            initial_transaction_id=initial_transaction_id,
            test_mode=test_mode,
            dup_seconds=dup_seconds,
            merchant_defined_fields=merchant_defined_fields,
            extra_params=extra_params,
        )
        return self._transact(params, decide_outcome, timeout=timeout)

    def authorize(
        self,
        *,
        amount: Money,
        payment_token: str | None = None,
        customer_vault_id: str | None = None,
        billing_id: str | None = None,
        order_id: str | None = None,
        order_description: str | None = None,
        po_number: str | None = None,
        currency: str | None = None,
        ip_address: str | None = None,
        billing: BillingParams | None = None,
        shipping: ShippingParams | None = None,
        initiated_by: Literal["customer", "merchant"] | None = None,
        stored_credential_indicator: Literal["stored", "used"] | None = None,
        initial_transaction_id: str | None = None,
        test_mode: bool = False,
        dup_seconds: int | None = None,
        merchant_defined_fields: Mapping[int, str] | None = None,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> TransactionResult:
        """Authorize without settling (``type=auth``); settle later with :meth:`capture`."""
        params = _charge_params(
            "auth",
            amount=amount,
            payment_token=payment_token,
            customer_vault_id=customer_vault_id,
            billing_id=billing_id,
            order_id=order_id,
            order_description=order_description,
            po_number=po_number,
            currency=currency,
            ip_address=ip_address,
            billing=billing,
            shipping=shipping,
            initiated_by=initiated_by,
            stored_credential_indicator=stored_credential_indicator,
            initial_transaction_id=initial_transaction_id,
            test_mode=test_mode,
            dup_seconds=dup_seconds,
            merchant_defined_fields=merchant_defined_fields,
            extra_params=extra_params,
        )
        return self._transact(params, decide_outcome, timeout=timeout)

    def credit(
        self,
        *,
        amount: Money,
        payment_token: str | None = None,
        customer_vault_id: str | None = None,
        billing_id: str | None = None,
        order_id: str | None = None,
        order_description: str | None = None,
        currency: str | None = None,
        billing: BillingParams | None = None,
        test_mode: bool = False,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> TransactionResult:
        """Push funds to a card not originally charged here (``type=credit``).

        Most accounts have credits disabled — prefer :meth:`refund`.
        """
        params = _charge_params(
            "credit",
            amount=amount,
            payment_token=payment_token,
            customer_vault_id=customer_vault_id,
            billing_id=billing_id,
            order_id=order_id,
            order_description=order_description,
            po_number=None,
            currency=currency,
            ip_address=None,
            billing=billing,
            shipping=None,
            initiated_by=None,
            stored_credential_indicator=None,
            initial_transaction_id=None,
            test_mode=test_mode,
            dup_seconds=None,
            merchant_defined_fields=None,
            extra_params=extra_params,
        )
        return self._transact(params, decide_outcome, timeout=timeout)

    def validate(
        self,
        *,
        payment_token: str | None = None,
        customer_vault_id: str | None = None,
        billing: BillingParams | None = None,
        initiated_by: Literal["customer", "merchant"] | None = None,
        stored_credential_indicator: Literal["stored", "used"] | None = None,
        initial_transaction_id: str | None = None,
        test_mode: bool = False,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> TransactionResult:
        """Account verification without an authorization (``type=validate``, no amount)."""
        params = _charge_params(
            "validate",
            amount=None,
            payment_token=payment_token,
            customer_vault_id=customer_vault_id,
            billing_id=None,
            order_id=None,
            order_description=None,
            po_number=None,
            currency=None,
            ip_address=None,
            billing=billing,
            shipping=None,
            initiated_by=initiated_by,
            stored_credential_indicator=stored_credential_indicator,
            initial_transaction_id=initial_transaction_id,
            test_mode=test_mode,
            dup_seconds=None,
            merchant_defined_fields=None,
            extra_params=extra_params,
        )
        return self._transact(params, decide_outcome, timeout=timeout)

    def capture(
        self,
        transaction_id: str,
        *,
        amount: Money | None = None,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> TransactionResult:
        """Flag an authorization for settlement; ``amount`` ≤ the authorized amount."""
        params = _capture_params(transaction_id, amount=amount, extra_params=extra_params)
        return self._transact(params, decide_outcome, timeout=timeout)

    def void(
        self,
        transaction_id: str,
        *,
        void_reason: VoidReason | None = None,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> TransactionResult:
        """Cancel an unsettled sale or captured authorization."""
        params = _void_params(transaction_id, void_reason=void_reason, extra_params=extra_params)
        return self._transact(params, decide_outcome, timeout=timeout)

    def refund(
        self,
        transaction_id: str,
        *,
        amount: Money | None = None,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> TransactionResult:
        """Reverse a settled transaction; omit ``amount`` for a full refund."""
        params = _refund_params(transaction_id, amount=amount, extra_params=extra_params)
        return self._transact(params, decide_outcome, timeout=timeout)

    def update(
        self,
        transaction_id: str,
        *,
        shipping_carrier: ShippingCarrier | None = None,
        tracking_number: str | None = None,
        shipping_date: date | str | None = None,
        order_description: str | None = None,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> TransactionResult:
        """Attach order/shipping details to a previous transaction (``type=update``)."""
        params = _update_params(
            transaction_id,
            shipping_carrier=shipping_carrier,
            tracking_number=tracking_number,
            shipping_date=shipping_date,
            order_description=order_description,
            extra_params=extra_params,
        )
        return self._transact(params, decide_outcome, timeout=timeout)


class AsyncTransactions(AsyncResource):
    """Async transaction operations. Declines are returned (``ok=False``), never raised."""

    async def sale(
        self,
        *,
        amount: Money,
        payment_token: str | None = None,
        customer_vault_id: str | None = None,
        billing_id: str | None = None,
        order_id: str | None = None,
        order_description: str | None = None,
        po_number: str | None = None,
        currency: str | None = None,
        ip_address: str | None = None,
        billing: BillingParams | None = None,
        shipping: ShippingParams | None = None,
        initiated_by: Literal["customer", "merchant"] | None = None,
        stored_credential_indicator: Literal["stored", "used"] | None = None,
        initial_transaction_id: str | None = None,
        test_mode: bool = False,
        dup_seconds: int | None = None,
        merchant_defined_fields: Mapping[int, str] | None = None,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> TransactionResult:
        """Charge immediately (``type=sale``): flagged for settlement on approval."""
        params = _charge_params(
            "sale",
            amount=amount,
            payment_token=payment_token,
            customer_vault_id=customer_vault_id,
            billing_id=billing_id,
            order_id=order_id,
            order_description=order_description,
            po_number=po_number,
            currency=currency,
            ip_address=ip_address,
            billing=billing,
            shipping=shipping,
            initiated_by=initiated_by,
            stored_credential_indicator=stored_credential_indicator,
            initial_transaction_id=initial_transaction_id,
            test_mode=test_mode,
            dup_seconds=dup_seconds,
            merchant_defined_fields=merchant_defined_fields,
            extra_params=extra_params,
        )
        return await self._transact(params, decide_outcome, timeout=timeout)

    async def authorize(
        self,
        *,
        amount: Money,
        payment_token: str | None = None,
        customer_vault_id: str | None = None,
        billing_id: str | None = None,
        order_id: str | None = None,
        order_description: str | None = None,
        po_number: str | None = None,
        currency: str | None = None,
        ip_address: str | None = None,
        billing: BillingParams | None = None,
        shipping: ShippingParams | None = None,
        initiated_by: Literal["customer", "merchant"] | None = None,
        stored_credential_indicator: Literal["stored", "used"] | None = None,
        initial_transaction_id: str | None = None,
        test_mode: bool = False,
        dup_seconds: int | None = None,
        merchant_defined_fields: Mapping[int, str] | None = None,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> TransactionResult:
        """Authorize without settling (``type=auth``); settle later with :meth:`capture`."""
        params = _charge_params(
            "auth",
            amount=amount,
            payment_token=payment_token,
            customer_vault_id=customer_vault_id,
            billing_id=billing_id,
            order_id=order_id,
            order_description=order_description,
            po_number=po_number,
            currency=currency,
            ip_address=ip_address,
            billing=billing,
            shipping=shipping,
            initiated_by=initiated_by,
            stored_credential_indicator=stored_credential_indicator,
            initial_transaction_id=initial_transaction_id,
            test_mode=test_mode,
            dup_seconds=dup_seconds,
            merchant_defined_fields=merchant_defined_fields,
            extra_params=extra_params,
        )
        return await self._transact(params, decide_outcome, timeout=timeout)

    async def credit(
        self,
        *,
        amount: Money,
        payment_token: str | None = None,
        customer_vault_id: str | None = None,
        billing_id: str | None = None,
        order_id: str | None = None,
        order_description: str | None = None,
        currency: str | None = None,
        billing: BillingParams | None = None,
        test_mode: bool = False,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> TransactionResult:
        """Push funds to a card not originally charged here (``type=credit``).

        Most accounts have credits disabled — prefer :meth:`refund`.
        """
        params = _charge_params(
            "credit",
            amount=amount,
            payment_token=payment_token,
            customer_vault_id=customer_vault_id,
            billing_id=billing_id,
            order_id=order_id,
            order_description=order_description,
            po_number=None,
            currency=currency,
            ip_address=None,
            billing=billing,
            shipping=None,
            initiated_by=None,
            stored_credential_indicator=None,
            initial_transaction_id=None,
            test_mode=test_mode,
            dup_seconds=None,
            merchant_defined_fields=None,
            extra_params=extra_params,
        )
        return await self._transact(params, decide_outcome, timeout=timeout)

    async def validate(
        self,
        *,
        payment_token: str | None = None,
        customer_vault_id: str | None = None,
        billing: BillingParams | None = None,
        initiated_by: Literal["customer", "merchant"] | None = None,
        stored_credential_indicator: Literal["stored", "used"] | None = None,
        initial_transaction_id: str | None = None,
        test_mode: bool = False,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> TransactionResult:
        """Account verification without an authorization (``type=validate``, no amount)."""
        params = _charge_params(
            "validate",
            amount=None,
            payment_token=payment_token,
            customer_vault_id=customer_vault_id,
            billing_id=None,
            order_id=None,
            order_description=None,
            po_number=None,
            currency=None,
            ip_address=None,
            billing=billing,
            shipping=None,
            initiated_by=initiated_by,
            stored_credential_indicator=stored_credential_indicator,
            initial_transaction_id=initial_transaction_id,
            test_mode=test_mode,
            dup_seconds=None,
            merchant_defined_fields=None,
            extra_params=extra_params,
        )
        return await self._transact(params, decide_outcome, timeout=timeout)

    async def capture(
        self,
        transaction_id: str,
        *,
        amount: Money | None = None,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> TransactionResult:
        """Flag an authorization for settlement; ``amount`` ≤ the authorized amount."""
        params = _capture_params(transaction_id, amount=amount, extra_params=extra_params)
        return await self._transact(params, decide_outcome, timeout=timeout)

    async def void(
        self,
        transaction_id: str,
        *,
        void_reason: VoidReason | None = None,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> TransactionResult:
        """Cancel an unsettled sale or captured authorization."""
        params = _void_params(transaction_id, void_reason=void_reason, extra_params=extra_params)
        return await self._transact(params, decide_outcome, timeout=timeout)

    async def refund(
        self,
        transaction_id: str,
        *,
        amount: Money | None = None,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> TransactionResult:
        """Reverse a settled transaction; omit ``amount`` for a full refund."""
        params = _refund_params(transaction_id, amount=amount, extra_params=extra_params)
        return await self._transact(params, decide_outcome, timeout=timeout)

    async def update(
        self,
        transaction_id: str,
        *,
        shipping_carrier: ShippingCarrier | None = None,
        tracking_number: str | None = None,
        shipping_date: date | str | None = None,
        order_description: str | None = None,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> TransactionResult:
        """Attach order/shipping details to a previous transaction (``type=update``)."""
        params = _update_params(
            transaction_id,
            shipping_carrier=shipping_carrier,
            tracking_number=tracking_number,
            shipping_date=shipping_date,
            order_description=order_description,
            extra_params=extra_params,
        )
        return await self._transact(params, decide_outcome, timeout=timeout)
