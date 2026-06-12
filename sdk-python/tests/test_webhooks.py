"""Webhook verification driven entirely by openapi/webhooks/vectors.json.

Both SDKs (Node + Python) must pass the identical golden vector set.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from kicbac import Kicbac, WebhookEvent
from kicbac.errors import SignatureVerificationError, WebhookPayloadError
from kicbac.webhooks import construct_event

_VECTORS_JSON = Path(__file__).resolve().parents[2] / "openapi" / "webhooks" / "vectors.json"
FIXTURE = json.loads(_VECTORS_JSON.read_text())
VECTORS = FIXTURE["vectors"]

EXPECTED_ERRORS = {
    "missing_header": SignatureVerificationError,
    "format_error": SignatureVerificationError,
    "signature_mismatch": SignatureVerificationError,
    "payload_error": WebhookPayloadError,
    "envelope_error": WebhookPayloadError,
}


@pytest.mark.parametrize("vector", VECTORS, ids=lambda vector: vector["name"])
def test_golden_vector(vector):
    payload = base64.b64decode(vector["payload_base64"])
    sig_header = vector["sig_header"]
    signing_key = vector["signing_key"]
    if vector["expect"] == "event":
        event = construct_event(payload, sig_header, signing_key)
        assert isinstance(event, WebhookEvent)
        assert event.event_type == vector["event_type"]
        assert event.event_id
        assert isinstance(event.event_body, dict)
    else:
        with pytest.raises(EXPECTED_ERRORS[vector["expect"]]):
            construct_event(payload, sig_header, signing_key)


def test_str_payload_raises_type_error():
    vector = next(v for v in VECTORS if v["expect"] == "event")
    payload_text = base64.b64decode(vector["payload_base64"]).decode()
    with pytest.raises(TypeError, match="raw request body bytes"):
        construct_event(payload_text, vector["sig_header"], vector["signing_key"])


def test_empty_signing_key_rejected():
    vector = next(v for v in VECTORS if v["expect"] == "event")
    payload = base64.b64decode(vector["payload_base64"])
    with pytest.raises(ValueError, match="signing_key"):
        construct_event(payload, vector["sig_header"], "")


def test_event_convenience_properties():
    vector = next(v for v in VECTORS if v["name"] == "valid-real-transaction-sale-success")
    payload = base64.b64decode(vector["payload_base64"])
    event = construct_event(payload, vector["sig_header"], vector["signing_key"])
    assert event.merchant_id == "1234"
    assert event.is_test_mode is True


def test_construct_event_is_bound_on_clients():
    vector = next(v for v in VECTORS if v["expect"] == "event")
    payload = base64.b64decode(vector["payload_base64"])
    with Kicbac(security_key="test_key") as client:
        event = client.webhooks.construct_event(
            payload, vector["sig_header"], vector["signing_key"]
        )
    assert event.event_type == vector["event_type"]
