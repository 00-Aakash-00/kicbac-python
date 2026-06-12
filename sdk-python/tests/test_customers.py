from __future__ import annotations

from urllib.parse import parse_qs

import httpx
import pytest
from conftest import TRANSACT_URL, approved_body, gateway_body, maybe_await

from kicbac import TransactionDeclined, VaultResult
from kicbac.errors import InvalidRequestError


def sent_fields(route) -> dict[str, list[str]]:
    return parse_qs(route.calls.last.request.content.decode(), keep_blank_values=True)


async def test_create_with_payment_token(client, respx_mock):
    route = respx_mock.post(TRANSACT_URL).mock(
        return_value=httpx.Response(
            200,
            text=gateway_body(
                response="1",
                responsetext="Customer Added",
                response_code="100",
                customer_vault_id="cv-123",
            ),
        )
    )
    result = await maybe_await(
        client.customers.create(
            payment_token="tok_abc",
            billing={"first_name": "Jane", "email": "jane@example.com"},
            shipping={"city": "Chicago"},
        )
    )
    assert sent_fields(route) == {
        "security_key": ["test_key"],
        "customer_vault": ["add_customer"],
        "payment_token": ["tok_abc"],
        "first_name": ["Jane"],
        "email": ["jane@example.com"],
        "shipping_city": ["Chicago"],
    }
    assert isinstance(result, VaultResult)
    assert result.ok is True
    assert result.customer_vault_id == "cv-123"


async def test_create_with_source_transaction(client, respx_mock):
    route = respx_mock.post(TRANSACT_URL).mock(
        return_value=httpx.Response(200, text=approved_body())
    )
    await maybe_await(
        client.customers.create(source_transaction_id="987", customer_vault_id="cv-1")
    )
    fields = sent_fields(route)
    assert fields["source_transaction_id"] == ["987"]
    assert fields["customer_vault_id"] == ["cv-1"]


async def test_create_requires_a_payment_source(client, respx_mock):
    route = respx_mock.post(TRANSACT_URL)
    with pytest.raises(InvalidRequestError, match="no payment data"):
        await maybe_await(client.customers.create())
    with pytest.raises(InvalidRequestError, match="not both"):
        await maybe_await(client.customers.create(payment_token="tok", source_transaction_id="987"))
    assert route.call_count == 0


async def test_update_and_delete(client, respx_mock):
    route = respx_mock.post(TRANSACT_URL).mock(
        return_value=httpx.Response(200, text=approved_body())
    )
    await maybe_await(client.customers.update("cv-1", billing={"zip": "60601"}))
    assert sent_fields(route) == {
        "security_key": ["test_key"],
        "customer_vault": ["update_customer"],
        "customer_vault_id": ["cv-1"],
        "zip": ["60601"],
    }
    await maybe_await(client.customers.delete("cv-1"))
    assert sent_fields(route) == {
        "security_key": ["test_key"],
        "customer_vault": ["delete_customer"],
        "customer_vault_id": ["cv-1"],
    }


async def test_charge_runs_vault_sale(client, respx_mock):
    route = respx_mock.post(TRANSACT_URL).mock(
        return_value=httpx.Response(200, text=approved_body())
    )
    result = await maybe_await(
        client.customers.charge(
            "cv-1",
            amount="25.00",
            billing_id="b2",
            initiated_by="merchant",
            stored_credential_indicator="used",
            initial_transaction_id="111",
            order_id="ord-9",
        )
    )
    assert sent_fields(route) == {
        "security_key": ["test_key"],
        "type": ["sale"],
        "customer_vault_id": ["cv-1"],
        "amount": ["25.00"],
        "billing_id": ["b2"],
        "initiated_by": ["merchant"],
        "stored_credential_indicator": ["used"],
        "initial_transaction_id": ["111"],
        "orderid": ["ord-9"],
    }
    assert result.ok is True


async def test_charge_decline_is_a_result_not_an_exception(client, respx_mock):
    respx_mock.post(TRANSACT_URL).mock(
        return_value=httpx.Response(
            200,
            text=gateway_body(
                response="2",
                responsetext="Insufficient funds",
                response_code="202",
                transactionid="555",
            ),
        )
    )
    result = await maybe_await(client.customers.charge("cv-1", amount="25.00"))
    assert isinstance(result, TransactionDeclined)
    assert result.ok is False
    assert result.response_code == 202


async def test_billing_record_lifecycle(client, respx_mock):
    route = respx_mock.post(TRANSACT_URL).mock(
        return_value=httpx.Response(200, text=approved_body())
    )
    await maybe_await(
        client.customers.add_billing(
            "cv-1",
            payment_token="tok_new",
            billing_id="b2",
            priority=1,
            billing={"zip": "10001"},
        )
    )
    assert sent_fields(route) == {
        "security_key": ["test_key"],
        "customer_vault": ["add_billing"],
        "customer_vault_id": ["cv-1"],
        "billing_id": ["b2"],
        "payment_token": ["tok_new"],
        "priority": ["1"],
        "zip": ["10001"],
    }
    await maybe_await(client.customers.update_billing("cv-1", "b2", priority=2))
    assert sent_fields(route) == {
        "security_key": ["test_key"],
        "customer_vault": ["update_billing"],
        "customer_vault_id": ["cv-1"],
        "billing_id": ["b2"],
        "priority": ["2"],
    }
    await maybe_await(client.customers.delete_billing("cv-1", "b2"))
    assert sent_fields(route) == {
        "security_key": ["test_key"],
        "customer_vault": ["delete_billing"],
        "customer_vault_id": ["cv-1"],
        "billing_id": ["b2"],
    }
