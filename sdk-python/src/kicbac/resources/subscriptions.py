"""Subscription operations (``recurring=add/update/delete_subscription``)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

import httpx

from kicbac._core import subscription_result
from kicbac._encode import encode_amount, encode_billing, encode_bool, encode_date, put
from kicbac.errors import InvalidRequestError
from kicbac.models.results import SubscriptionResult
from kicbac.resources._base import AsyncResource, SyncResource
from kicbac.resources.plans import _frequency_params
from kicbac.types import BillingParams, Money

__all__ = ["AsyncSubscriptions", "Subscriptions"]


def _create_params(
    plan_id: str,
    *,
    customer_vault_id: str | None,
    payment_token: str | None,
    start_date: date | str | None,
    order_id: str | None,
    order_description: str | None,
    billing: BillingParams | None,
    extra_params: Mapping[str, str] | None,
) -> dict[str, str]:
    if customer_vault_id is not None and payment_token is not None:
        raise InvalidRequestError("pass either customer_vault_id or payment_token, not both")
    if customer_vault_id is None and payment_token is None and not extra_params:
        raise InvalidRequestError(
            "no payment source for the subscription: pass customer_vault_id or "
            "payment_token (from Kicbac.js)"
        )
    params: dict[str, str] = {"recurring": "add_subscription", "plan_id": plan_id}
    put(params, "customer_vault_id", customer_vault_id)
    put(params, "payment_token", payment_token)
    if start_date is not None:
        params["start_date"] = encode_date(start_date, field="start_date")
    put(params, "orderid", order_id)
    put(params, "order_description", order_description)
    if billing is not None:
        params.update(encode_billing(billing))
    if extra_params is not None:
        params.update(extra_params)
    return params


def _update_params(
    subscription_id: str,
    *,
    paused: bool | None,
    amount: Money | None,
    payments: int | None,
    day_frequency: int | None,
    month_frequency: int | None,
    day_of_month: int | None,
    start_date: date | str | None,
    payment_token: str | None,
    extra_params: Mapping[str, str] | None,
) -> dict[str, str]:
    params: dict[str, str] = {
        "recurring": "update_subscription",
        "subscription_id": subscription_id,
    }
    if paused is not None:
        params["paused_subscription"] = encode_bool(paused)
    if amount is not None:
        params["plan_amount"] = encode_amount(amount, field="amount")
    if payments is not None:
        params["plan_payments"] = str(payments)
    params.update(_frequency_params(day_frequency, month_frequency, day_of_month, required=False))
    if start_date is not None:
        params["start_date"] = encode_date(start_date, field="start_date")
    put(params, "payment_token", payment_token)
    if extra_params is not None:
        params.update(extra_params)
    return params


def _delete_params(
    subscription_id: str, *, extra_params: Mapping[str, str] | None
) -> dict[str, str]:
    params: dict[str, str] = {
        "recurring": "delete_subscription",
        "subscription_id": subscription_id,
    }
    if extra_params is not None:
        params.update(extra_params)
    return params


class Subscriptions(SyncResource):
    """Sync subscription operations."""

    def create(
        self,
        plan_id: str,
        *,
        customer_vault_id: str | None = None,
        payment_token: str | None = None,
        start_date: date | str | None = None,
        order_id: str | None = None,
        order_description: str | None = None,
        billing: BillingParams | None = None,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> SubscriptionResult:
        """Subscribe a payment source to an existing plan (``add_subscription``)."""
        params = _create_params(
            plan_id,
            customer_vault_id=customer_vault_id,
            payment_token=payment_token,
            start_date=start_date,
            order_id=order_id,
            order_description=order_description,
            billing=billing,
            extra_params=extra_params,
        )
        return self._transact(params, subscription_result, timeout=timeout)

    def update(
        self,
        subscription_id: str,
        *,
        paused: bool | None = None,
        amount: Money | None = None,
        payments: int | None = None,
        day_frequency: int | None = None,
        month_frequency: int | None = None,
        day_of_month: int | None = None,
        start_date: date | str | None = None,
        payment_token: str | None = None,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> SubscriptionResult:
        """Update a subscription; ``paused=True/False`` maps to ``paused_subscription``."""
        params = _update_params(
            subscription_id,
            paused=paused,
            amount=amount,
            payments=payments,
            day_frequency=day_frequency,
            month_frequency=month_frequency,
            day_of_month=day_of_month,
            start_date=start_date,
            payment_token=payment_token,
            extra_params=extra_params,
        )
        return self._transact(params, subscription_result, timeout=timeout)

    def delete(
        self,
        subscription_id: str,
        *,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> SubscriptionResult:
        """Cancel a subscription (``delete_subscription``); no further charges."""
        params = _delete_params(subscription_id, extra_params=extra_params)
        return self._transact(params, subscription_result, timeout=timeout)


class AsyncSubscriptions(AsyncResource):
    """Async subscription operations."""

    async def create(
        self,
        plan_id: str,
        *,
        customer_vault_id: str | None = None,
        payment_token: str | None = None,
        start_date: date | str | None = None,
        order_id: str | None = None,
        order_description: str | None = None,
        billing: BillingParams | None = None,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> SubscriptionResult:
        """Subscribe a payment source to an existing plan (``add_subscription``)."""
        params = _create_params(
            plan_id,
            customer_vault_id=customer_vault_id,
            payment_token=payment_token,
            start_date=start_date,
            order_id=order_id,
            order_description=order_description,
            billing=billing,
            extra_params=extra_params,
        )
        return await self._transact(params, subscription_result, timeout=timeout)

    async def update(
        self,
        subscription_id: str,
        *,
        paused: bool | None = None,
        amount: Money | None = None,
        payments: int | None = None,
        day_frequency: int | None = None,
        month_frequency: int | None = None,
        day_of_month: int | None = None,
        start_date: date | str | None = None,
        payment_token: str | None = None,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> SubscriptionResult:
        """Update a subscription; ``paused=True/False`` maps to ``paused_subscription``."""
        params = _update_params(
            subscription_id,
            paused=paused,
            amount=amount,
            payments=payments,
            day_frequency=day_frequency,
            month_frequency=month_frequency,
            day_of_month=day_of_month,
            start_date=start_date,
            payment_token=payment_token,
            extra_params=extra_params,
        )
        return await self._transact(params, subscription_result, timeout=timeout)

    async def delete(
        self,
        subscription_id: str,
        *,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> SubscriptionResult:
        """Cancel a subscription (``delete_subscription``); no further charges."""
        params = _delete_params(subscription_id, extra_params=extra_params)
        return await self._transact(params, subscription_result, timeout=timeout)
