"""Customer Vault operations (``customer_vault=...`` on transact.php)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

import httpx

from kicbac._core import decide_outcome, vault_result
from kicbac._encode import (
    encode_amount,
    encode_billing,
    encode_dup_seconds,
    encode_shipping,
    put,
)
from kicbac._encode import (
    merchant_defined_fields as encode_mdf,
)
from kicbac.errors import InvalidRequestError
from kicbac.models.results import TransactionResult, VaultResult
from kicbac.resources._base import AsyncResource, SyncResource
from kicbac.types import BillingParams, Money, ShippingParams

__all__ = ["AsyncCustomers", "Customers"]


def _create_params(
    *,
    payment_token: str | None,
    source_transaction_id: str | None,
    customer_vault_id: str | None,
    billing_id: str | None,
    billing: BillingParams | None,
    shipping: ShippingParams | None,
    extra_params: Mapping[str, str] | None,
) -> dict[str, str]:
    if payment_token is not None and source_transaction_id is not None:
        raise InvalidRequestError("pass either payment_token or source_transaction_id, not both")
    if payment_token is None and source_transaction_id is None and not extra_params:
        raise InvalidRequestError(
            "no payment data to store: pass payment_token (from Kicbac.js) or "
            "source_transaction_id (an existing gateway transaction id)"
        )
    params: dict[str, str] = {"customer_vault": "add_customer"}
    put(params, "payment_token", payment_token)
    put(params, "source_transaction_id", source_transaction_id)
    put(params, "customer_vault_id", customer_vault_id)
    put(params, "billing_id", billing_id)
    if billing is not None:
        params.update(encode_billing(billing))
    if shipping is not None:
        params.update(encode_shipping(shipping))
    if extra_params is not None:
        params.update(extra_params)
    return params


def _update_params(
    customer_vault_id: str,
    *,
    payment_token: str | None,
    billing_id: str | None,
    billing: BillingParams | None,
    shipping: ShippingParams | None,
    extra_params: Mapping[str, str] | None,
) -> dict[str, str]:
    params: dict[str, str] = {
        "customer_vault": "update_customer",
        "customer_vault_id": customer_vault_id,
    }
    put(params, "payment_token", payment_token)
    put(params, "billing_id", billing_id)
    if billing is not None:
        params.update(encode_billing(billing))
    if shipping is not None:
        params.update(encode_shipping(shipping))
    if extra_params is not None:
        params.update(extra_params)
    return params


def _delete_params(
    customer_vault_id: str, *, extra_params: Mapping[str, str] | None
) -> dict[str, str]:
    params: dict[str, str] = {
        "customer_vault": "delete_customer",
        "customer_vault_id": customer_vault_id,
    }
    if extra_params is not None:
        params.update(extra_params)
    return params


def _charge_params(
    customer_vault_id: str,
    *,
    amount: Money,
    billing_id: str | None,
    order_id: str | None,
    order_description: str | None,
    currency: str | None,
    initiated_by: Literal["customer", "merchant"] | None,
    stored_credential_indicator: Literal["stored", "used"] | None,
    initial_transaction_id: str | None,
    test_mode: bool,
    dup_seconds: int | None,
    merchant_defined_fields: Mapping[int, str] | None,
    extra_params: Mapping[str, str] | None,
) -> dict[str, str]:
    params: dict[str, str] = {
        "type": "sale",
        "customer_vault_id": customer_vault_id,
        "amount": encode_amount(amount),
    }
    put(params, "billing_id", billing_id)
    put(params, "orderid", order_id)
    put(params, "order_description", order_description)
    put(params, "currency", currency)
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


def _billing_params(
    action: str,
    customer_vault_id: str,
    *,
    billing_id: str | None,
    payment_token: str | None,
    priority: int | None,
    billing: BillingParams | None,
    extra_params: Mapping[str, str] | None,
) -> dict[str, str]:
    params: dict[str, str] = {
        "customer_vault": action,
        "customer_vault_id": customer_vault_id,
    }
    put(params, "billing_id", billing_id)
    put(params, "payment_token", payment_token)
    if priority is not None:
        params["priority"] = str(priority)
    if billing is not None:
        params.update(encode_billing(billing))
    if extra_params is not None:
        params.update(extra_params)
    return params


class Customers(SyncResource):
    """Sync Customer Vault operations."""

    def create(
        self,
        *,
        payment_token: str | None = None,
        source_transaction_id: str | None = None,
        customer_vault_id: str | None = None,
        billing_id: str | None = None,
        billing: BillingParams | None = None,
        shipping: ShippingParams | None = None,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> VaultResult:
        """Store a customer (``customer_vault=add_customer``).

        Omit ``customer_vault_id`` to let the gateway generate one (returned on
        the result).
        """
        params = _create_params(
            payment_token=payment_token,
            source_transaction_id=source_transaction_id,
            customer_vault_id=customer_vault_id,
            billing_id=billing_id,
            billing=billing,
            shipping=shipping,
            extra_params=extra_params,
        )
        return self._transact(params, vault_result, timeout=timeout)

    def update(
        self,
        customer_vault_id: str,
        *,
        payment_token: str | None = None,
        billing_id: str | None = None,
        billing: BillingParams | None = None,
        shipping: ShippingParams | None = None,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> VaultResult:
        """Update a stored customer (``customer_vault=update_customer``)."""
        params = _update_params(
            customer_vault_id,
            payment_token=payment_token,
            billing_id=billing_id,
            billing=billing,
            shipping=shipping,
            extra_params=extra_params,
        )
        return self._transact(params, vault_result, timeout=timeout)

    def delete(
        self,
        customer_vault_id: str,
        *,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> VaultResult:
        """Delete a stored customer (``customer_vault=delete_customer``)."""
        params = _delete_params(customer_vault_id, extra_params=extra_params)
        return self._transact(params, vault_result, timeout=timeout)

    def charge(
        self,
        customer_vault_id: str,
        *,
        amount: Money,
        billing_id: str | None = None,
        order_id: str | None = None,
        order_description: str | None = None,
        currency: str | None = None,
        initiated_by: Literal["customer", "merchant"] | None = None,
        stored_credential_indicator: Literal["stored", "used"] | None = None,
        initial_transaction_id: str | None = None,
        test_mode: bool = False,
        dup_seconds: int | None = None,
        merchant_defined_fields: Mapping[int, str] | None = None,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> TransactionResult:
        """Run a sale against a stored customer's payment method."""
        params = _charge_params(
            customer_vault_id,
            amount=amount,
            billing_id=billing_id,
            order_id=order_id,
            order_description=order_description,
            currency=currency,
            initiated_by=initiated_by,
            stored_credential_indicator=stored_credential_indicator,
            initial_transaction_id=initial_transaction_id,
            test_mode=test_mode,
            dup_seconds=dup_seconds,
            merchant_defined_fields=merchant_defined_fields,
            extra_params=extra_params,
        )
        return self._transact(params, decide_outcome, timeout=timeout)

    def add_billing(
        self,
        customer_vault_id: str,
        *,
        payment_token: str | None = None,
        billing_id: str | None = None,
        priority: int | None = None,
        billing: BillingParams | None = None,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> VaultResult:
        """Add a billing record to a customer (``customer_vault=add_billing``)."""
        params = _billing_params(
            "add_billing",
            customer_vault_id,
            billing_id=billing_id,
            payment_token=payment_token,
            priority=priority,
            billing=billing,
            extra_params=extra_params,
        )
        return self._transact(params, vault_result, timeout=timeout)

    def update_billing(
        self,
        customer_vault_id: str,
        billing_id: str,
        *,
        payment_token: str | None = None,
        priority: int | None = None,
        billing: BillingParams | None = None,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> VaultResult:
        """Update a billing record (``customer_vault=update_billing``)."""
        params = _billing_params(
            "update_billing",
            customer_vault_id,
            billing_id=billing_id,
            payment_token=payment_token,
            priority=priority,
            billing=billing,
            extra_params=extra_params,
        )
        return self._transact(params, vault_result, timeout=timeout)

    def delete_billing(
        self,
        customer_vault_id: str,
        billing_id: str,
        *,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> VaultResult:
        """Delete a billing record (``customer_vault=delete_billing``)."""
        params = _billing_params(
            "delete_billing",
            customer_vault_id,
            billing_id=billing_id,
            payment_token=None,
            priority=None,
            billing=None,
            extra_params=extra_params,
        )
        return self._transact(params, vault_result, timeout=timeout)


class AsyncCustomers(AsyncResource):
    """Async Customer Vault operations."""

    async def create(
        self,
        *,
        payment_token: str | None = None,
        source_transaction_id: str | None = None,
        customer_vault_id: str | None = None,
        billing_id: str | None = None,
        billing: BillingParams | None = None,
        shipping: ShippingParams | None = None,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> VaultResult:
        """Store a customer (``customer_vault=add_customer``).

        Omit ``customer_vault_id`` to let the gateway generate one (returned on
        the result).
        """
        params = _create_params(
            payment_token=payment_token,
            source_transaction_id=source_transaction_id,
            customer_vault_id=customer_vault_id,
            billing_id=billing_id,
            billing=billing,
            shipping=shipping,
            extra_params=extra_params,
        )
        return await self._transact(params, vault_result, timeout=timeout)

    async def update(
        self,
        customer_vault_id: str,
        *,
        payment_token: str | None = None,
        billing_id: str | None = None,
        billing: BillingParams | None = None,
        shipping: ShippingParams | None = None,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> VaultResult:
        """Update a stored customer (``customer_vault=update_customer``)."""
        params = _update_params(
            customer_vault_id,
            payment_token=payment_token,
            billing_id=billing_id,
            billing=billing,
            shipping=shipping,
            extra_params=extra_params,
        )
        return await self._transact(params, vault_result, timeout=timeout)

    async def delete(
        self,
        customer_vault_id: str,
        *,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> VaultResult:
        """Delete a stored customer (``customer_vault=delete_customer``)."""
        params = _delete_params(customer_vault_id, extra_params=extra_params)
        return await self._transact(params, vault_result, timeout=timeout)

    async def charge(
        self,
        customer_vault_id: str,
        *,
        amount: Money,
        billing_id: str | None = None,
        order_id: str | None = None,
        order_description: str | None = None,
        currency: str | None = None,
        initiated_by: Literal["customer", "merchant"] | None = None,
        stored_credential_indicator: Literal["stored", "used"] | None = None,
        initial_transaction_id: str | None = None,
        test_mode: bool = False,
        dup_seconds: int | None = None,
        merchant_defined_fields: Mapping[int, str] | None = None,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> TransactionResult:
        """Run a sale against a stored customer's payment method."""
        params = _charge_params(
            customer_vault_id,
            amount=amount,
            billing_id=billing_id,
            order_id=order_id,
            order_description=order_description,
            currency=currency,
            initiated_by=initiated_by,
            stored_credential_indicator=stored_credential_indicator,
            initial_transaction_id=initial_transaction_id,
            test_mode=test_mode,
            dup_seconds=dup_seconds,
            merchant_defined_fields=merchant_defined_fields,
            extra_params=extra_params,
        )
        return await self._transact(params, decide_outcome, timeout=timeout)

    async def add_billing(
        self,
        customer_vault_id: str,
        *,
        payment_token: str | None = None,
        billing_id: str | None = None,
        priority: int | None = None,
        billing: BillingParams | None = None,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> VaultResult:
        """Add a billing record to a customer (``customer_vault=add_billing``)."""
        params = _billing_params(
            "add_billing",
            customer_vault_id,
            billing_id=billing_id,
            payment_token=payment_token,
            priority=priority,
            billing=billing,
            extra_params=extra_params,
        )
        return await self._transact(params, vault_result, timeout=timeout)

    async def update_billing(
        self,
        customer_vault_id: str,
        billing_id: str,
        *,
        payment_token: str | None = None,
        priority: int | None = None,
        billing: BillingParams | None = None,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> VaultResult:
        """Update a billing record (``customer_vault=update_billing``)."""
        params = _billing_params(
            "update_billing",
            customer_vault_id,
            billing_id=billing_id,
            payment_token=payment_token,
            priority=priority,
            billing=billing,
            extra_params=extra_params,
        )
        return await self._transact(params, vault_result, timeout=timeout)

    async def delete_billing(
        self,
        customer_vault_id: str,
        billing_id: str,
        *,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> VaultResult:
        """Delete a billing record (``customer_vault=delete_billing``)."""
        params = _billing_params(
            "delete_billing",
            customer_vault_id,
            billing_id=billing_id,
            payment_token=None,
            priority=None,
            billing=None,
            extra_params=extra_params,
        )
        return await self._transact(params, vault_result, timeout=timeout)
