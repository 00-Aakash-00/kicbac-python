"""Public input types for the Kicbac SDK.

``BillingParams``/``ShippingParams`` keys mirror the Direct Post API
transaction-variable names (billing fields are passed through verbatim;
shipping fields map to the gateway's ``shipping_*`` spellings).
"""

from __future__ import annotations

from decimal import Decimal
from typing import TypedDict, Union

__all__ = ["BillingParams", "Money", "ShippingParams"]

# Gateway amounts are exact decimal strings ("x.xx"); floats are rejected at
# runtime because binary floats cannot represent cents exactly.
Money = Union[str, Decimal]  # noqa: UP007 - readable alias in rendered docs


class BillingParams(TypedDict, total=False):
    """Billing-address fields (gateway names ``first_name`` ... ``email``)."""

    first_name: str
    last_name: str
    company: str
    address1: str
    address2: str
    city: str
    state: str
    zip: str
    country: str
    phone: str
    fax: str
    email: str


class ShippingParams(TypedDict, total=False):
    """Shipping-address fields (mapped to the gateway's ``shipping_*`` names)."""

    first_name: str
    last_name: str
    company: str
    address1: str
    address2: str
    city: str
    state: str
    zip: str
    country: str
    email: str
