"""Pure request-building / response-parsing logic shared by sync and async.

Everything here is side-effect free so the ``Kicbac`` and ``AsyncKicbac``
clients cannot drift apart: both build byte-identical request bodies and run
the same outcome decisions. Only ``_transport.py`` duplicates code.
"""

from __future__ import annotations

import random
import re
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import parse_qsl

from kicbac._constants import (
    AUTH_FAIL_PATTERN,
    ERROR_CLASS_BY_CODE,
    QUERY_PATH,
    TRANSACT_PATH,
)
from kicbac._encode import form_encode
from kicbac.errors import (
    APIError,
    AuthenticationError,
    InvalidRequestError,
    ProcessorError,
    RateLimitError,
)
from kicbac.models.results import (
    InvoiceResult,
    PlanResult,
    SubscriptionResult,
    TransactionApproved,
    TransactionDeclined,
    VaultResult,
)

_AUTH_FAIL_RE = re.compile(AUTH_FAIL_PATTERN, re.IGNORECASE)

_ERROR_CLASSES: dict[str, type[APIError]] = {
    "InvalidRequestError": InvalidRequestError,
    "RateLimitError": RateLimitError,
    "ProcessorError": ProcessorError,
}


@dataclass(frozen=True)
class RequestSpec:
    """A fully-built gateway request: POST ``path`` with form ``data``."""

    path: str
    data: dict[str, str]

    @property
    def body(self) -> bytes:
        return form_encode(self.data)


def build_transact_request(security_key: str, params: Mapping[str, str]) -> RequestSpec:
    return RequestSpec(TRANSACT_PATH, {"security_key": security_key, **params})


def build_query_request(security_key: str, params: Mapping[str, str]) -> RequestSpec:
    return RequestSpec(QUERY_PATH, {"security_key": security_key, **params})


def parse_transact_body(body: str) -> dict[str, str]:
    """Parse a transact.php form-encoded response body into a field dict."""
    pairs: list[tuple[str, str]] = parse_qsl(body, keep_blank_values=True)
    return dict(pairs)


def backoff_delay(attempt: int) -> float:
    """Jittered exponential backoff for retry attempt 0, 1, ... (seconds)."""
    return min(2.0, 0.5 * 2.0**attempt) * random.uniform(0.5, 1.0)  # noqa: S311 - jitter, not crypto


def classify_gateway_error(response_code: int | None, response_text: str) -> type[APIError]:
    """Map a ``response=3`` reply to its exception class."""
    if response_code is not None:
        class_name = ERROR_CLASS_BY_CODE.get(response_code)
        if class_name == "RateLimitError":
            return RateLimitError
        if class_name == "ProcessorError" or (class_name is None and response_code >= 400):
            return ProcessorError
    if _AUTH_FAIL_RE.search(response_text):
        return AuthenticationError
    return InvalidRequestError


def _parse_response_code(fields: Mapping[str, str]) -> int | None:
    raw = fields.get("response_code", "")
    return int(raw) if raw.isdigit() else None


def raise_for_error(
    fields: Mapping[str, str],
    *,
    raw_body: str,
    request_params: Mapping[str, str] | None = None,
) -> None:
    """Raise the right APIError for malformed bodies and ``response=3`` replies."""
    response = fields.get("response")
    if response not in ("1", "2", "3"):
        raise APIError(
            "unexpected reply from gateway: missing or invalid 'response' field "
            f"(got {response!r}); the raw body is attached as .raw_body",
            params=dict(request_params) if request_params is not None else None,
            raw_body=raw_body,
        )
    if response != "3":
        return
    response_code = _parse_response_code(fields)
    response_text = fields.get("responsetext", "")
    error_class = classify_gateway_error(response_code, response_text)
    detail = response_text or "no responsetext provided"
    if error_class is AuthenticationError:
        message = (
            f"gateway rejected the security key (code {response_code}): {detail} — "
            "check the key in Settings > Security Keys and that it matches this environment"
        )
    elif error_class is RateLimitError:
        message = f"gateway rate limit exceeded (code {response_code}): {detail}"
    elif error_class is ProcessorError:
        message = f"processor error (code {response_code}): {detail}"
    else:
        message = f"gateway rejected the request (code {response_code}): {detail}"
    raise error_class(
        message,
        response_code=response_code,
        response_text=response_text,
        params=dict(request_params) if request_params is not None else None,
        raw_body=raw_body,
    )


def decide_outcome(
    fields: Mapping[str, str],
    *,
    raw_body: str,
    request_params: Mapping[str, str] | None = None,
) -> TransactionApproved | TransactionDeclined:
    """Turn parsed transact.php fields into a result, raising for errors."""
    raise_for_error(fields, raw_body=raw_body, request_params=request_params)
    raw = dict(fields)
    response_code = _parse_response_code(fields) or 0
    if fields["response"] == "1":
        return TransactionApproved(
            transaction_id=fields.get("transactionid", ""),
            auth_code=fields.get("authcode") or None,
            avs_response=fields.get("avsresponse") or None,
            cvv_response=fields.get("cvvresponse") or None,
            order_id=fields.get("orderid") or None,
            response_code=response_code,
            response_text=fields.get("responsetext", ""),
            customer_vault_id=fields.get("customer_vault_id") or None,
            raw=raw,
        )
    return TransactionDeclined(
        response_code=response_code,
        message=fields.get("responsetext", ""),
        transaction_id=fields.get("transactionid") or None,
        avs_response=fields.get("avsresponse") or None,
        cvv_response=fields.get("cvvresponse") or None,
        raw=raw,
    )


def vault_result(
    fields: Mapping[str, str],
    *,
    raw_body: str,
    request_params: Mapping[str, str] | None = None,
) -> VaultResult:
    raise_for_error(fields, raw_body=raw_body, request_params=request_params)
    return VaultResult(
        ok=fields.get("response") == "1",
        response_code=_parse_response_code(fields) or 0,
        response_text=fields.get("responsetext", ""),
        raw=dict(fields),
        customer_vault_id=fields.get("customer_vault_id") or None,
    )


def plan_result(
    fields: Mapping[str, str],
    *,
    raw_body: str,
    request_params: Mapping[str, str] | None = None,
) -> PlanResult:
    raise_for_error(fields, raw_body=raw_body, request_params=request_params)
    return PlanResult(
        ok=fields.get("response") == "1",
        response_code=_parse_response_code(fields) or 0,
        response_text=fields.get("responsetext", ""),
        raw=dict(fields),
        plan_id=fields.get("plan_id") or None,
    )


def subscription_result(
    fields: Mapping[str, str],
    *,
    raw_body: str,
    request_params: Mapping[str, str] | None = None,
) -> SubscriptionResult:
    raise_for_error(fields, raw_body=raw_body, request_params=request_params)
    return SubscriptionResult(
        ok=fields.get("response") == "1",
        response_code=_parse_response_code(fields) or 0,
        response_text=fields.get("responsetext", ""),
        raw=dict(fields),
        subscription_id=fields.get("subscription_id") or None,
    )


def invoice_result(
    fields: Mapping[str, str],
    *,
    raw_body: str,
    request_params: Mapping[str, str] | None = None,
) -> InvoiceResult:
    raise_for_error(fields, raw_body=raw_body, request_params=request_params)
    return InvoiceResult(
        ok=fields.get("response") == "1",
        response_code=_parse_response_code(fields) or 0,
        response_text=fields.get("responsetext", ""),
        raw=dict(fields),
        invoice_id=fields.get("invoice_id") or None,
    )
