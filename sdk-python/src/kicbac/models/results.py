"""Typed results for transact.php operations.

``response=1`` -> ``TransactionApproved`` (``ok=True``); ``response=2`` ->
``TransactionDeclined`` (``ok=False``, never an exception); ``response=3``
raises — see ``kicbac.errors``.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import Field

from kicbac.models.base import KicbacModel

__all__ = [
    "InvoiceResult",
    "PlanResult",
    "SubscriptionResult",
    "TransactionApproved",
    "TransactionDeclined",
    "TransactionResult",
    "VaultResult",
]


class TransactionApproved(KicbacModel):
    ok: Literal[True] = True
    transaction_id: str
    auth_code: str | None = None
    avs_response: str | None = None
    cvv_response: str | None = None
    order_id: str | None = None
    response_code: int
    response_text: str
    customer_vault_id: str | None = None
    raw: dict[str, str]


class TransactionDeclined(KicbacModel):
    ok: Literal[False] = False
    response_code: int
    message: str
    transaction_id: str | None = None
    avs_response: str | None = None
    cvv_response: str | None = None
    raw: dict[str, str]


TransactionResult = Annotated[
    Union[TransactionApproved, TransactionDeclined],  # noqa: UP007 - pydantic discriminator
    Field(discriminator="ok"),
]


class _OperationResult(KicbacModel):
    ok: bool
    response_code: int
    response_text: str
    raw: dict[str, str]


class VaultResult(_OperationResult):
    customer_vault_id: str | None = None


class PlanResult(_OperationResult):
    plan_id: str | None = None


class SubscriptionResult(_OperationResult):
    subscription_id: str | None = None


class InvoiceResult(_OperationResult):
    invoice_id: str | None = None
