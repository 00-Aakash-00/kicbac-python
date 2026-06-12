"""Redaction of PCI/credential fields before anything becomes loggable.

Applied by every error constructor so that ``str()``/``repr()`` of exceptions
(and anything a merchant logs from them) never leaks card data or keys.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

REDACTED = "[REDACTED]"

# Field values that must never appear at all.
_FULL_REDACT_FIELDS = frozenset({"cvv", "checkaba", "security_key", "payment_token"})
# Field values masked to their last 4 characters.
_LAST4_FIELDS = frozenset({"ccnumber", "checkaccount"})

_FULL_FIELD_RE = re.compile(r"(?i)\b(cvv|checkaba|security_key|payment_token)=([^&\s]*)")
_LAST4_FIELD_RE = re.compile(r"(?i)\b(ccnumber|checkaccount)=([^&\s]*)")
# Standalone 13-19 digit runs look like PANs; mask all but the last 4 digits.
_PAN_RUN_RE = re.compile(r"(?<!\d)\d{13,19}(?!\d)")


def _mask_last4(value: str) -> str:
    return "************" + value[-4:] if len(value) >= 4 else "************"


def redact_params(params: Mapping[str, str]) -> dict[str, str]:
    """Return a copy of form params with sensitive values masked."""
    redacted: dict[str, str] = {}
    for key, value in params.items():
        lowered = key.lower()
        if lowered in _FULL_REDACT_FIELDS:
            redacted[key] = REDACTED
        elif lowered in _LAST4_FIELDS:
            redacted[key] = _mask_last4(value)
        else:
            redacted[key] = value
    return redacted


def redact_text(text: str) -> str:
    """Mask sensitive ``key=value`` pairs and PAN-like digit runs in raw text."""
    text = _FULL_FIELD_RE.sub(lambda m: f"{m.group(1)}={REDACTED}", text)
    text = _LAST4_FIELD_RE.sub(lambda m: f"{m.group(1)}={_mask_last4(m.group(2))}", text)
    return _PAN_RUN_RE.sub(lambda m: _mask_last4(m.group(0)), text)
