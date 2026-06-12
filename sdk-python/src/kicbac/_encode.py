"""Value encoding/validation for gateway form fields. Pure functions only."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Context, Decimal, Inexact
from typing import cast
from urllib.parse import urlencode

from kicbac.errors import InvalidRequestError
from kicbac.types import BillingParams, ShippingParams

_AMOUNT_RE = re.compile(r"\d{1,8}(\.\d{1,2})?")
_DATE_RE = re.compile(r"\d{8}")
_DATETIME_RE = re.compile(r"\d{14}")
_TWO_PLACES = Decimal("0.01")
_INEXACT_TRAPS = Context(traps=[Inexact])

MAX_DUP_SECONDS = 7862400
MAX_MERCHANT_DEFINED_FIELD = 20


def encode_amount(value: str | Decimal, *, field: str = "amount", allow_zero: bool = False) -> str:
    """Validate a money amount and return the gateway ``x.xx`` string.

    Floats are rejected outright (binary floats cannot represent cents
    exactly); pass ``"19.99"`` or ``Decimal("19.99")``.
    """
    if isinstance(value, Decimal):
        try:
            quantized = value.quantize(_TWO_PLACES, context=_INEXACT_TRAPS)
        except Inexact:
            raise InvalidRequestError(
                f"{field}={value} has more than 2 decimal places; "
                "amounts are charged in cents — round it yourself first"
            ) from None
        text = f"{quantized:f}"
    elif isinstance(value, str):
        text = value
    else:
        raise TypeError(
            f"{field} must be a str or Decimal, not {type(value).__name__} "
            "(floats lose cents); pass '19.99' or Decimal('19.99')"
        )
    if _AMOUNT_RE.fullmatch(text) is None:
        raise InvalidRequestError(
            f"invalid {field} {text!r}: expected a decimal string like '19.99' "
            "(up to 8 integer digits and 2 decimal places, no sign)"
        )
    if not allow_zero and Decimal(text) == 0:
        raise InvalidRequestError(f"{field} must be greater than zero")
    return text


def encode_bool(value: bool) -> str:
    return "true" if value else "false"


def encode_date(value: date | str, *, field: str) -> str:
    """Return a gateway ``YYYYMMDD`` date string."""
    if isinstance(value, date):
        return value.strftime("%Y%m%d")
    if _DATE_RE.fullmatch(value) is None:
        raise InvalidRequestError(f"invalid {field} {value!r}: expected YYYYMMDD or datetime.date")
    return value


def encode_datetime(value: datetime | date | str, *, field: str) -> str:
    """Return a gateway ``YYYYMMDDhhmmss`` timestamp string."""
    if isinstance(value, datetime):
        return value.strftime("%Y%m%d%H%M%S")
    if isinstance(value, date):
        return value.strftime("%Y%m%d") + "000000"
    if _DATETIME_RE.fullmatch(value) is not None:
        return value
    if _DATE_RE.fullmatch(value) is not None:
        return value + "000000"
    raise InvalidRequestError(
        f"invalid {field} {value!r}: expected YYYYMMDDhhmmss, YYYYMMDD, or a datetime/date"
    )


def encode_csv(value: str | Sequence[str], *, field: str) -> str:
    """Comma-join a sequence of filter values (or pass a string through)."""
    if isinstance(value, str):
        return value
    joined = ",".join(value)
    if not joined:
        raise InvalidRequestError(f"{field} must not be an empty sequence")
    return joined


def encode_dup_seconds(value: int) -> str:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("dup_seconds must be an int")
    if not 0 <= value <= MAX_DUP_SECONDS:
        raise InvalidRequestError(
            f"dup_seconds={value} out of range: must be 0 (disable) to {MAX_DUP_SECONDS}"
        )
    return str(value)


def merchant_defined_fields(values: Mapping[int, str]) -> dict[str, str]:
    """Map ``{1: "v"}`` to ``{"merchant_defined_field_1": "v"}`` (slots 1-20)."""
    encoded: dict[str, str] = {}
    for number, value in values.items():
        if not 1 <= number <= MAX_MERCHANT_DEFINED_FIELD:
            raise InvalidRequestError(
                f"merchant_defined_fields key {number} out of range: the gateway "
                f"supports merchant_defined_field_1 through _{MAX_MERCHANT_DEFINED_FIELD}"
            )
        encoded[f"merchant_defined_field_{number}"] = value
    return encoded


# Billing fields are sent to the gateway under their own names; shipping
# fields use the gateway's shipping_* spellings (Direct Post API pp. 6-7).
_BILLING_KEYS = frozenset(BillingParams.__annotations__)
_SHIPPING_KEY_MAP = {
    "first_name": "shipping_firstname",
    "last_name": "shipping_lastname",
    "company": "shipping_company",
    "address1": "shipping_address1",
    "address2": "shipping_address2",
    "city": "shipping_city",
    "state": "shipping_state",
    "zip": "shipping_zip",
    "country": "shipping_country",
    "email": "shipping_email",
}


def encode_billing(billing: BillingParams) -> dict[str, str]:
    """Validate billing keys and return them as gateway form fields."""
    encoded: dict[str, str] = {}
    for key, value in cast("Mapping[str, str]", billing).items():
        if key not in _BILLING_KEYS:
            raise InvalidRequestError(
                f"unknown billing field {key!r}: expected one of {sorted(_BILLING_KEYS)}"
            )
        encoded[key] = value
    return encoded


def encode_shipping(shipping: ShippingParams) -> dict[str, str]:
    """Map shipping keys to the gateway's ``shipping_*`` form fields."""
    encoded: dict[str, str] = {}
    for key, value in cast("Mapping[str, str]", shipping).items():
        gateway_key = _SHIPPING_KEY_MAP.get(key)
        if gateway_key is None:
            raise InvalidRequestError(
                f"unknown shipping field {key!r}: expected one of {sorted(_SHIPPING_KEY_MAP)}"
            )
        encoded[gateway_key] = value
    return encoded


def put(params: dict[str, str], key: str, value: str | None) -> None:
    """Add ``key=value`` unless the value is None (None means "omit")."""
    if value is not None:
        params[key] = value


def form_encode(params: Mapping[str, str]) -> bytes:
    """Encode params as an application/x-www-form-urlencoded body (UTF-8)."""
    return urlencode(params).encode("ascii")
