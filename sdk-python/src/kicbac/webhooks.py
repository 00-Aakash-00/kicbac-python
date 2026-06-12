"""Webhook signature verification.

``Webhook-Signature: t=<nonce>,s=<hex sig>`` where the signature is
``HMAC_SHA256(signing_key, nonce + "." + raw_body_bytes)``. Verification is
over the **exact raw request bytes** — re-serialising the JSON first will
always fail.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re

from pydantic import ValidationError

from kicbac.errors import SignatureVerificationError, WebhookPayloadError
from kicbac.models.webhook import WebhookEvent

__all__ = ["construct_event"]

_SIG_HEADER_RE = re.compile(r"t=([^,]+),s=([0-9a-fA-F]{64})")
_REQUIRED_KEYS = ("event_id", "event_type", "event_body")


def construct_event(payload: bytes, sig_header: str | None, signing_key: str) -> WebhookEvent:
    """Verify a webhook delivery and return the parsed :class:`WebhookEvent`.

    ``t=`` is a random nonce, NOT a timestamp — there is no tolerance window
    to enforce; deduplicate redeliveries with ``event.event_id`` instead.

    Raises:
        TypeError: ``payload`` is a ``str`` (verification needs raw bytes).
        SignatureVerificationError: header missing/malformed or signature mismatch.
        WebhookPayloadError: signature verified but the body is not a usable event.
    """
    if isinstance(payload, str):
        raise TypeError(
            "pass the raw request body bytes "
            "(e.g. request.get_data() / await request.body()), not str"
        )
    if not signing_key:
        raise ValueError(
            "signing_key must be the non-empty webhook signing key from Settings > Webhooks"
        )
    if sig_header is None or sig_header == "":
        raise SignatureVerificationError("missing Webhook-Signature header")
    match = _SIG_HEADER_RE.fullmatch(sig_header.strip())
    if match is None:
        raise SignatureVerificationError(
            "malformed Webhook-Signature header: expected 't=<nonce>,s=<64 hex chars>', "
            f"got {sig_header!r}"
        )
    nonce, signature = match.group(1), match.group(2)
    expected = hmac.new(
        signing_key.encode("utf-8"),
        nonce.encode("utf-8") + b"." + bytes(payload),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature.lower()):
        raise SignatureVerificationError(
            "webhook signature does not match: check that the signing key is the one shown "
            "in Settings > Webhooks and that you verified the exact raw request bytes "
            "(no re-serialisation, trailing newlines included)"
        )
    try:
        parsed = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise WebhookPayloadError(
            "webhook signature verified but the body is not valid JSON"
        ) from exc
    if not isinstance(parsed, dict):
        raise WebhookPayloadError("webhook signature verified but the body is not a JSON object")
    missing = [key for key in _REQUIRED_KEYS if key not in parsed]
    if missing:
        raise WebhookPayloadError(f"webhook JSON is missing required key(s): {', '.join(missing)}")
    try:
        return WebhookEvent.model_validate(parsed)
    except ValidationError as exc:
        raise WebhookPayloadError(f"webhook JSON has malformed envelope fields: {exc}") from exc


class WebhooksNamespace:
    """Bound as ``client.webhooks`` so the verifier is reachable from a client."""

    construct_event = staticmethod(construct_event)
