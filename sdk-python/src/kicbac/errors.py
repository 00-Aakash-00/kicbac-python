"""Error taxonomy for the Kicbac SDK.

Hierarchy::

    KicbacError
    ├── APIError                  gateway/transport problems (response=3, HTTP, parsing)
    │   ├── AuthenticationError   bad/missing security key (also raised at construction)
    │   ├── InvalidRequestError   gateway code 300 rejections + client-side validation
    │   ├── RateLimitError        gateway code 301 or HTTP 429 — never auto-retried
    │   ├── ProcessorError        gateway codes 400-461
    │   └── APIConnectionError    wraps httpx.TransportError (original as __cause__)
    │       └── APITimeoutError   wraps httpx timeout classes
    ├── SignatureVerificationError  webhook signature problems
    └── WebhookPayloadError         verified webhook with an unusable body

Declines (``response=2``) are **results**, never exceptions — see
``kicbac.TransactionDeclined``.
"""

from __future__ import annotations

from collections.abc import Mapping

from kicbac._redact import redact_params, redact_text

__all__ = [
    "APIConnectionError",
    "APIError",
    "APITimeoutError",
    "AuthenticationError",
    "InvalidRequestError",
    "KicbacError",
    "ProcessorError",
    "RateLimitError",
    "SignatureVerificationError",
    "WebhookPayloadError",
]


class KicbacError(Exception):
    """Base class for every exception raised by this SDK."""


class APIError(KicbacError):
    """A gateway request failed (response=3, transport error, or unparseable reply).

    ``params`` (the request form fields) and ``raw_body`` (the gateway reply)
    are redacted at construction; they are safe to log.
    """

    def __init__(
        self,
        message: str,
        *,
        response_code: int | None = None,
        response_text: str | None = None,
        params: Mapping[str, str] | None = None,
        raw_body: str | None = None,
    ) -> None:
        message = redact_text(message)
        super().__init__(message)
        self.message = message
        self.response_code = response_code
        self.response_text = redact_text(response_text) if response_text is not None else None
        self.params = redact_params(params) if params is not None else None
        self.raw_body = redact_text(raw_body) if raw_body is not None else None

    def __str__(self) -> str:
        return self.message

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(message={self.message!r}, "
            f"response_code={self.response_code!r}, response_text={self.response_text!r})"
        )


class AuthenticationError(APIError):
    """The gateway rejected the security key (or no key was configured)."""


class InvalidRequestError(APIError):
    """The request was malformed or rejected by the gateway (code 300).

    Also raised by client-side validation before any network call, in which
    case ``response_code`` is ``None``.
    """


class RateLimitError(APIError):
    """Gateway rate limit hit (code 301 or HTTP 429).

    Never auto-retried by the SDK: immediately retrying may extend the delay
    before transactions are allowed again. Back off before resubmitting.
    """


class ProcessorError(APIError):
    """The processor returned an error (codes 400-461)."""


class APIConnectionError(APIError):
    """The gateway could not be reached. The original httpx error is ``__cause__``.

    For ``transact.php`` this is only raised after failures where no request
    bytes were sent (or retries were exhausted) — the transaction was NOT
    submitted twice. If the failure happened mid-response (e.g. a read error),
    the charge may still have gone through: reconcile via the Query API before
    resubmitting.
    """


class APITimeoutError(APIConnectionError):
    """The request to the gateway timed out (httpx timeout classes)."""


class SignatureVerificationError(KicbacError):
    """The webhook signature header is missing, malformed, or does not match."""


class WebhookPayloadError(KicbacError):
    """The webhook signature verified but the payload is not a usable event."""
