from __future__ import annotations

import httpx
import pytest
from conftest import TRANSACT_URL, gateway_body, maybe_await

from kicbac._redact import redact_params, redact_text
from kicbac.errors import APIError, ProcessorError

PAN = "4111111111111111"


class TestRedactParams:
    def test_fully_redacted_fields(self):
        params = {
            "cvv": "123",
            "checkaba": "490000018",
            "security_key": "sk_live_secret",
            "payment_token": "tok_secret",
            "amount": "10.00",
        }
        redacted = redact_params(params)
        assert redacted == {
            "cvv": "[REDACTED]",
            "checkaba": "[REDACTED]",
            "security_key": "[REDACTED]",
            "payment_token": "[REDACTED]",
            "amount": "10.00",
        }

    def test_last4_fields(self):
        redacted = redact_params({"ccnumber": PAN, "checkaccount": "24413815"})
        assert redacted == {
            "ccnumber": "************1111",
            "checkaccount": "************3815",
        }

    def test_case_insensitive_keys(self):
        assert redact_params({"CVV": "123"}) == {"CVV": "[REDACTED]"}

    def test_original_mapping_untouched(self):
        params = {"cvv": "123"}
        redact_params(params)
        assert params["cvv"] == "123"


class TestRedactText:
    def test_form_encoded_fields_masked(self):
        text = f"ccnumber={PAN}&cvv=999&security_key=sk_123&amount=1.00"
        redacted = redact_text(text)
        assert PAN not in redacted
        assert "999" not in redacted
        assert "sk_123" not in redacted
        assert "ccnumber=************1111" in redacted
        assert "amount=1.00" in redacted

    def test_bare_pan_runs_masked(self):
        redacted = redact_text(f"customer typed {PAN} into notes")
        assert PAN not in redacted
        assert "************1111" in redacted

    def test_short_and_long_digit_runs_left_alone(self):
        assert redact_text("order 123456789012 ok") == "order 123456789012 ok"  # 12 digits
        twenty = "1" * 20
        assert redact_text(f"id {twenty}") == f"id {twenty}"


class TestErrorRedaction:
    def test_constructor_redacts_params_and_raw_body(self):
        error = APIError(
            f"gateway said ccnumber={PAN} was bad",
            params={"security_key": "sk_live_secret", "ccnumber": PAN, "amount": "1.00"},
            raw_body=f"response=3&responsetext=bad card {PAN}",
        )
        for loggable in (str(error), repr(error), error.message):
            assert PAN not in loggable
            assert "sk_live_secret" not in loggable
        assert error.params == {
            "security_key": "[REDACTED]",
            "ccnumber": "************1111",
            "amount": "1.00",
        }
        assert error.raw_body is not None
        assert PAN not in error.raw_body

    def test_response_text_redacted(self):
        error = ProcessorError("processor error", response_text=f"declined {PAN}")
        assert error.response_text is not None
        assert PAN not in error.response_text


async def test_live_error_path_redacts_request_and_response(client, respx_mock):
    body = gateway_body(
        response="3",
        responsetext=f"Rejected card {PAN}",
        response_code="300",
    )
    respx_mock.post(TRANSACT_URL).mock(return_value=httpx.Response(200, text=body))
    with pytest.raises(APIError) as excinfo:
        await maybe_await(
            client.transactions.sale(
                amount="1.00",
                payment_token="tok_super_secret",
                extra_params={"cvv": "999"},
            )
        )
    error = excinfo.value
    assert error.params is not None
    assert error.params["security_key"] == "[REDACTED]"
    assert error.params["payment_token"] == "[REDACTED]"
    assert error.params["cvv"] == "[REDACTED]"
    assert error.raw_body is not None
    assert PAN not in error.raw_body
    assert PAN not in str(error)
    assert PAN not in repr(error)
