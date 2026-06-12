from __future__ import annotations

from datetime import date
from decimal import Decimal
from urllib.parse import parse_qs

import httpx
import pytest
import respx
from conftest import TRANSACT_URL, approved_body, maybe_await

from kicbac import AsyncKicbac, Kicbac, TransactionApproved
from kicbac.errors import InvalidRequestError


def sent_fields(route) -> dict[str, list[str]]:
    return parse_qs(route.calls.last.request.content.decode(), keep_blank_values=True)


async def test_sale_sends_exact_form_fields(client, respx_mock):
    route = respx_mock.post(TRANSACT_URL).mock(
        return_value=httpx.Response(200, text=approved_body(customer_vault_id="cv9"))
    )
    result = await maybe_await(
        client.transactions.sale(
            amount=Decimal("49.5"),
            payment_token="tok_abc",
            order_id="ord-77",
            order_description="2 widgets",
            po_number="PO-1",
            currency="USD",
            ip_address="203.0.113.9",
            billing={"first_name": "Jane", "last_name": "Doe", "zip": "60601"},
            shipping={"first_name": "Jane", "city": "Chicago"},
            initiated_by="customer",
            stored_credential_indicator="stored",
            test_mode=True,
            dup_seconds=120,
            merchant_defined_fields={3: "blue"},
            extra_params={"descriptor": "ACME*WIDGETS"},
        )
    )
    assert sent_fields(route) == {
        "security_key": ["test_key"],
        "type": ["sale"],
        "amount": ["49.50"],
        "payment_token": ["tok_abc"],
        "orderid": ["ord-77"],
        "order_description": ["2 widgets"],
        "ponumber": ["PO-1"],
        "currency": ["USD"],
        "ipaddress": ["203.0.113.9"],
        "first_name": ["Jane"],
        "last_name": ["Doe"],
        "zip": ["60601"],
        "shipping_firstname": ["Jane"],
        "shipping_city": ["Chicago"],
        "initiated_by": ["customer"],
        "stored_credential_indicator": ["stored"],
        "test_mode": ["enabled"],
        "dup_seconds": ["120"],
        "merchant_defined_field_3": ["blue"],
        "descriptor": ["ACME*WIDGETS"],
    }
    assert isinstance(result, TransactionApproved)
    assert result.customer_vault_id == "cv9"
    assert result.auth_code == "123456"


async def test_authorize_uses_type_auth(client, respx_mock):
    route = respx_mock.post(TRANSACT_URL).mock(
        return_value=httpx.Response(200, text=approved_body())
    )
    await maybe_await(client.transactions.authorize(amount="20.00", payment_token="tok"))
    assert sent_fields(route)["type"] == ["auth"]


async def test_validate_sends_no_amount(client, respx_mock):
    route = respx_mock.post(TRANSACT_URL).mock(
        return_value=httpx.Response(200, text=approved_body())
    )
    await maybe_await(client.transactions.validate(payment_token="tok"))
    fields = sent_fields(route)
    assert fields["type"] == ["validate"]
    assert "amount" not in fields


async def test_credit_uses_type_credit(client, respx_mock):
    route = respx_mock.post(TRANSACT_URL).mock(
        return_value=httpx.Response(200, text=approved_body())
    )
    await maybe_await(client.transactions.credit(amount="5.00", payment_token="tok"))
    assert sent_fields(route)["type"] == ["credit"]


async def test_capture_full_and_partial(client, respx_mock):
    route = respx_mock.post(TRANSACT_URL).mock(
        return_value=httpx.Response(200, text=approved_body())
    )
    await maybe_await(client.transactions.capture("12345"))
    fields = sent_fields(route)
    assert fields == {
        "security_key": ["test_key"],
        "type": ["capture"],
        "transactionid": ["12345"],
    }
    await maybe_await(client.transactions.capture("12345", amount="9.99"))
    assert sent_fields(route)["amount"] == ["9.99"]


async def test_void_with_reason(client, respx_mock):
    route = respx_mock.post(TRANSACT_URL).mock(
        return_value=httpx.Response(200, text=approved_body())
    )
    await maybe_await(client.transactions.void("12345", void_reason="user_cancel"))
    assert sent_fields(route) == {
        "security_key": ["test_key"],
        "type": ["void"],
        "transactionid": ["12345"],
        "void_reason": ["user_cancel"],
    }


async def test_refund_omits_amount_for_full_refund(client, respx_mock):
    route = respx_mock.post(TRANSACT_URL).mock(
        return_value=httpx.Response(200, text=approved_body())
    )
    await maybe_await(client.transactions.refund("12345"))
    assert "amount" not in sent_fields(route)
    await maybe_await(client.transactions.refund("12345", amount="0.00"))
    assert sent_fields(route)["amount"] == ["0.00"]


async def test_update_shipping_details(client, respx_mock):
    route = respx_mock.post(TRANSACT_URL).mock(
        return_value=httpx.Response(200, text=approved_body())
    )
    await maybe_await(
        client.transactions.update(
            "12345",
            shipping_carrier="ups",
            tracking_number="1Z999",
            shipping_date=date(2026, 6, 15),
            order_description="updated",
        )
    )
    assert sent_fields(route) == {
        "security_key": ["test_key"],
        "type": ["update"],
        "transactionid": ["12345"],
        "shipping_carrier": ["ups"],
        "tracking_number": ["1Z999"],
        "shipping_date": ["20260615"],
        "order_description": ["updated"],
    }


async def test_sale_without_payment_method_fails_before_any_request(client, respx_mock):
    route = respx_mock.post(TRANSACT_URL)
    with pytest.raises(InvalidRequestError, match="no payment method") as excinfo:
        await maybe_await(client.transactions.sale(amount="10.00"))
    assert excinfo.value.response_code is None
    assert route.call_count == 0


async def test_sale_rejects_float_amount(client, respx_mock):
    with pytest.raises(TypeError, match="str or Decimal"):
        await maybe_await(
            client.transactions.sale(amount=10.0, payment_token="tok")  # type: ignore[arg-type]
        )


@respx.mock
async def test_sync_and_async_clients_send_byte_identical_bodies():
    """Anti-drift: the two client flavours must build the same request bytes."""
    route = respx.post(TRANSACT_URL).mock(return_value=httpx.Response(200, text=approved_body()))
    kwargs = {
        "amount": Decimal("12.30"),
        "payment_token": "tok_drift",
        "order_id": "ord-1",
        "currency": "USD",
        "billing": {"first_name": "Ann", "zip": "10001"},
        "shipping": {"city": "NYC"},
        "test_mode": True,
        "dup_seconds": 60,
        "merchant_defined_fields": {1: "x"},
        "extra_params": {"descriptor": "D"},
    }
    with Kicbac(security_key="test_key") as sync_client:
        sync_client.transactions.sale(**kwargs)
    sync_bytes = route.calls.last.request.content
    async with AsyncKicbac(security_key="test_key") as async_client:
        await async_client.transactions.sale(**kwargs)
    async_bytes = route.calls.last.request.content
    assert sync_bytes == async_bytes
    assert b"test_mode=enabled" in sync_bytes
