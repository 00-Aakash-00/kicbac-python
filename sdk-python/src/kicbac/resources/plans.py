"""Recurring plan operations (``recurring=add_plan`` / ``edit_plan``).

The gateway has no delete-plan API; retire a plan by deleting its
subscriptions and no longer referencing the plan id.
"""

from __future__ import annotations

from collections.abc import Mapping

import httpx

from kicbac._core import plan_result
from kicbac._encode import encode_amount
from kicbac.errors import InvalidRequestError
from kicbac.models.results import PlanResult
from kicbac.resources._base import AsyncResource, SyncResource
from kicbac.types import Money

__all__ = ["AsyncPlans", "Plans"]


def _frequency_params(
    day_frequency: int | None,
    month_frequency: int | None,
    day_of_month: int | None,
    *,
    required: bool,
) -> dict[str, str]:
    """``day_frequency`` XOR (``month_frequency`` AND ``day_of_month``)."""
    if day_frequency is not None:
        if month_frequency is not None or day_of_month is not None:
            raise InvalidRequestError(
                "day_frequency cannot be combined with month_frequency/day_of_month "
                "— the gateway accepts one schedule style per plan"
            )
        if day_frequency < 1:
            raise InvalidRequestError("day_frequency must be a positive number of days")
        return {"day_frequency": str(day_frequency)}
    if month_frequency is not None or day_of_month is not None:
        if month_frequency is None or day_of_month is None:
            raise InvalidRequestError(
                "month_frequency and day_of_month must be set together "
                "(e.g. month_frequency=1, day_of_month=15 bills on the 15th monthly)"
            )
        if not 1 <= month_frequency <= 24:
            raise InvalidRequestError("month_frequency must be 1 through 24")
        if not 1 <= day_of_month <= 31:
            raise InvalidRequestError("day_of_month must be 1 through 31")
        return {"month_frequency": str(month_frequency), "day_of_month": str(day_of_month)}
    if required:
        raise InvalidRequestError(
            "a billing schedule is required: pass day_frequency, or month_frequency "
            "together with day_of_month"
        )
    return {}


def _create_params(
    plan_id: str,
    *,
    name: str,
    amount: Money,
    payments: int | None,
    day_frequency: int | None,
    month_frequency: int | None,
    day_of_month: int | None,
    extra_params: Mapping[str, str] | None,
) -> dict[str, str]:
    params: dict[str, str] = {
        "recurring": "add_plan",
        "plan_id": plan_id,
        "plan_name": name,
        "plan_amount": encode_amount(amount, field="amount"),
    }
    if payments is not None:
        params["plan_payments"] = str(payments)
    params.update(_frequency_params(day_frequency, month_frequency, day_of_month, required=True))
    if extra_params is not None:
        params.update(extra_params)
    return params


def _update_params(
    plan_id: str,
    *,
    name: str | None,
    amount: Money | None,
    payments: int | None,
    day_frequency: int | None,
    month_frequency: int | None,
    day_of_month: int | None,
    extra_params: Mapping[str, str] | None,
) -> dict[str, str]:
    params: dict[str, str] = {"recurring": "edit_plan", "current_plan_id": plan_id}
    if name is not None:
        params["plan_name"] = name
    if amount is not None:
        params["plan_amount"] = encode_amount(amount, field="amount")
    if payments is not None:
        params["plan_payments"] = str(payments)
    params.update(_frequency_params(day_frequency, month_frequency, day_of_month, required=False))
    if extra_params is not None:
        params.update(extra_params)
    return params


class Plans(SyncResource):
    """Sync recurring-plan operations. There is no ``delete`` (gateway limitation)."""

    def create(
        self,
        plan_id: str,
        *,
        name: str,
        amount: Money,
        payments: int | None = None,
        day_frequency: int | None = None,
        month_frequency: int | None = None,
        day_of_month: int | None = None,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> PlanResult:
        """Create a plan. ``payments=0`` means "until canceled" (the gateway
        requires ``plan_payments``; pass it explicitly)."""
        params = _create_params(
            plan_id,
            name=name,
            amount=amount,
            payments=payments,
            day_frequency=day_frequency,
            month_frequency=month_frequency,
            day_of_month=day_of_month,
            extra_params=extra_params,
        )
        return self._transact(params, plan_result, timeout=timeout)

    def update(
        self,
        plan_id: str,
        *,
        name: str | None = None,
        amount: Money | None = None,
        payments: int | None = None,
        day_frequency: int | None = None,
        month_frequency: int | None = None,
        day_of_month: int | None = None,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> PlanResult:
        """Edit a plan (``recurring=edit_plan``). Careful: existing subscribers'
        billing changes with the plan."""
        params = _update_params(
            plan_id,
            name=name,
            amount=amount,
            payments=payments,
            day_frequency=day_frequency,
            month_frequency=month_frequency,
            day_of_month=day_of_month,
            extra_params=extra_params,
        )
        return self._transact(params, plan_result, timeout=timeout)


class AsyncPlans(AsyncResource):
    """Async recurring-plan operations. There is no ``delete`` (gateway limitation)."""

    async def create(
        self,
        plan_id: str,
        *,
        name: str,
        amount: Money,
        payments: int | None = None,
        day_frequency: int | None = None,
        month_frequency: int | None = None,
        day_of_month: int | None = None,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> PlanResult:
        """Create a plan. ``payments=0`` means "until canceled" (the gateway
        requires ``plan_payments``; pass it explicitly)."""
        params = _create_params(
            plan_id,
            name=name,
            amount=amount,
            payments=payments,
            day_frequency=day_frequency,
            month_frequency=month_frequency,
            day_of_month=day_of_month,
            extra_params=extra_params,
        )
        return await self._transact(params, plan_result, timeout=timeout)

    async def update(
        self,
        plan_id: str,
        *,
        name: str | None = None,
        amount: Money | None = None,
        payments: int | None = None,
        day_frequency: int | None = None,
        month_frequency: int | None = None,
        day_of_month: int | None = None,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> PlanResult:
        """Edit a plan (``recurring=edit_plan``). Careful: existing subscribers'
        billing changes with the plan."""
        params = _update_params(
            plan_id,
            name=name,
            amount=amount,
            payments=payments,
            day_frequency=day_frequency,
            month_frequency=month_frequency,
            day_of_month=day_of_month,
            extra_params=extra_params,
        )
        return await self._transact(params, plan_result, timeout=timeout)
