from __future__ import annotations

from urllib.parse import parse_qs

import httpx
import pytest
from conftest import TRANSACT_URL, gateway_body, maybe_await

from kicbac.errors import InvalidRequestError


def sent_fields(route) -> dict[str, list[str]]:
    return parse_qs(route.calls.last.request.content.decode(), keep_blank_values=True)


def ok_body(**overrides: str) -> str:
    fields = {"response": "1", "responsetext": "Success", "response_code": "100"}
    fields.update(overrides)
    return gateway_body(**fields)


async def test_create_sends_exact_fields(client, respx_mock):
    route = respx_mock.post(TRANSACT_URL).mock(
        return_value=httpx.Response(200, text=ok_body(invoice_id="inv-1"))
    )
    result = await maybe_await(
        client.invoices.create(
            amount="150.00",
            email="billing@example.com",
            payment_terms=30,
            payment_methods_allowed=["cc", "ck"],
            currency="USD",
            order_description="Consulting",
            billing={"first_name": "Jane"},
        )
    )
    assert sent_fields(route) == {
        "security_key": ["test_key"],
        "invoicing": ["add_invoice"],
        "amount": ["150.00"],
        "email": ["billing@example.com"],
        "payment_terms": ["30"],
        "payment_methods_allowed": ["cc,ck"],
        "currency": ["USD"],
        "order_description": ["Consulting"],
        "first_name": ["Jane"],
    }
    assert result.ok is True
    assert result.invoice_id == "inv-1"


async def test_create_default_payment_terms(client, respx_mock):
    route = respx_mock.post(TRANSACT_URL).mock(return_value=httpx.Response(200, text=ok_body()))
    await maybe_await(client.invoices.create(amount="10.00", email="a@b.co"))
    assert sent_fields(route)["payment_terms"] == ["upon_receipt"]


@pytest.mark.parametrize("terms", [-1, 1000, "net 30", True])
async def test_create_rejects_bad_payment_terms(client, respx_mock, terms):
    route = respx_mock.post(TRANSACT_URL)
    with pytest.raises(InvalidRequestError, match="payment_terms"):
        await maybe_await(
            client.invoices.create(amount="10.00", email="a@b.co", payment_terms=terms)
        )
    assert route.call_count == 0


async def test_update_send_close(client, respx_mock):
    route = respx_mock.post(TRANSACT_URL).mock(return_value=httpx.Response(200, text=ok_body()))
    await maybe_await(client.invoices.update("inv-1", amount="175.00"))
    assert sent_fields(route) == {
        "security_key": ["test_key"],
        "invoicing": ["update_invoice"],
        "invoice_id": ["inv-1"],
        "amount": ["175.00"],
    }
    await maybe_await(client.invoices.send("inv-1"))
    assert sent_fields(route) == {
        "security_key": ["test_key"],
        "invoicing": ["send_invoice"],
        "invoice_id": ["inv-1"],
    }
    await maybe_await(client.invoices.close("inv-1"))
    assert sent_fields(route) == {
        "security_key": ["test_key"],
        "invoicing": ["close_invoice"],
        "invoice_id": ["inv-1"],
    }
