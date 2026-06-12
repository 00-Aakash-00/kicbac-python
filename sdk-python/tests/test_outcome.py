"""Table-driven outcome tests over EVERY row of openapi/data/response-codes.json."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlencode

import httpx
import pytest
from conftest import TRANSACT_URL, gateway_body, maybe_await

import kicbac.errors
from kicbac import TransactionApproved, TransactionDeclined
from kicbac._constants import AUTH_FAIL_PATTERN, VENDORED_RESPONSE_CODES
from kicbac.errors import APIError, AuthenticationError

_SHARED_JSON = Path(__file__).resolve().parents[2] / "openapi" / "data" / "response-codes.json"
SHARED = json.loads(_SHARED_JSON.read_text())
CODES = SHARED["codes"]


def test_vendored_table_matches_shared_fixture():
    """The vendored copy in _constants.py must stay in sync with openapi/data/."""
    expected = tuple(
        (
            row["code"],
            row["text"],
            row["response"],
            row["outcome"],
            row.get("error_class"),
        )
        for row in CODES
    )
    assert expected == VENDORED_RESPONSE_CODES
    assert SHARED["auth_failure_pattern"] == AUTH_FAIL_PATTERN


def _body_for(row: dict) -> str:
    return urlencode(
        {
            "response": str(row["response"]),
            "responsetext": row["text"],
            "authcode": "123456" if row["response"] == 1 else "",
            "transactionid": "9876543210",
            "avsresponse": "N",
            "cvvresponse": "M",
            "orderid": "ord-1",
            "type": "sale",
            "response_code": str(row["code"]),
        }
    )


@pytest.mark.parametrize("row", CODES, ids=lambda row: f"code-{row['code']}")
async def test_every_response_code_row(row, client, respx_mock):
    respx_mock.post(TRANSACT_URL).mock(return_value=httpx.Response(200, text=_body_for(row)))

    def invoke():
        return client.transactions.sale(amount="10.00", payment_token="tok_123")

    if row["outcome"] == "approved":
        result = await maybe_await(invoke())
        assert isinstance(result, TransactionApproved)
        assert result.ok is True
        assert result.response_code == row["code"]
        assert result.transaction_id == "9876543210"
    elif row["outcome"] == "declined":
        result = await maybe_await(invoke())
        assert isinstance(result, TransactionDeclined)
        assert result.ok is False
        assert result.response_code == row["code"]
        assert result.message == row["text"]
    else:
        expected = getattr(kicbac.errors, row["error_class"])
        with pytest.raises(expected) as excinfo:
            await maybe_await(invoke())
        assert type(excinfo.value) is expected
        assert excinfo.value.response_code == row["code"]


async def test_code_300_with_auth_failure_text_raises_authentication_error(client, respx_mock):
    body = gateway_body(response="3", responsetext="Authentication Failed", response_code="300")
    respx_mock.post(TRANSACT_URL).mock(return_value=httpx.Response(200, text=body))
    with pytest.raises(AuthenticationError, match="security key"):
        await maybe_await(client.transactions.sale(amount="10.00", payment_token="tok"))


async def test_code_300_invalid_key_text_raises_authentication_error(client, respx_mock):
    body = gateway_body(response="3", responsetext="Invalid Security Key", response_code="300")
    respx_mock.post(TRANSACT_URL).mock(return_value=httpx.Response(200, text=body))
    with pytest.raises(AuthenticationError):
        await maybe_await(client.transactions.sale(amount="10.00", payment_token="tok"))


@pytest.mark.parametrize(
    "body",
    [
        "",
        "<html><body>Bad Gateway</body></html>",
        gateway_body(response="9", responsetext="bogus"),
        gateway_body(responsetext="no response field at all"),
    ],
    ids=["empty", "html", "response-9", "missing-response"],
)
async def test_malformed_bodies_raise_plain_api_error(body, client, respx_mock):
    respx_mock.post(TRANSACT_URL).mock(return_value=httpx.Response(200, text=body))
    with pytest.raises(APIError) as excinfo:
        await maybe_await(client.transactions.sale(amount="10.00", payment_token="tok"))
    assert type(excinfo.value) is APIError
    assert excinfo.value.raw_body is not None


async def test_unknown_error_code_above_400_maps_to_processor_error(client, respx_mock):
    body = gateway_body(response="3", responsetext="weird processor thing", response_code="455")
    respx_mock.post(TRANSACT_URL).mock(return_value=httpx.Response(200, text=body))
    with pytest.raises(kicbac.errors.ProcessorError):
        await maybe_await(client.transactions.sale(amount="10.00", payment_token="tok"))
