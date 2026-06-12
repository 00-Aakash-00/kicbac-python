from __future__ import annotations

from urllib.parse import parse_qs

import httpx
import pytest
from conftest import QUERY_URL, collect, maybe_await, take_one

from kicbac.errors import APIError, AuthenticationError, InvalidRequestError

TRANSACTION_PAGE = """<nm_response>
<transaction>
<transaction_id>2612675976</transaction_id>
<transaction_type>cc</transaction_type>
<condition>complete</condition>
<order_id>1234567890</order_id>
<first_name>John</first_name>
<last_name>Smith</last_name>
<address_1>123 Main St</address_1>
<cc_number>4xxxxxxxxxxx1111</cc_number>
<cc_exp>1215</cc_exp>
<currency>USD</currency>
<customer_vault_id></customer_vault_id>
<product>
<sku>RS-100</sku>
<quantity>1.0000</quantity>
<description>Red Shirt</description>
<amount>10.0000</amount>
</product>
<action>
<amount>11.00</amount>
<action_type>sale</action_type>
<date>20150312215205</date>
<success>1</success>
<response_code>100</response_code>
<response_text>SUCCESS</response_text>
</action>
<action>
<amount>11.00</amount>
<action_type>settle</action_type>
<date>20150313171503</date>
<success>1</success>
<response_code>100</response_code>
<response_text>ACCEPTED</response_text>
</action>
</transaction>
<transaction>
<transaction_id>999</transaction_id>
<condition>pendingsettlement</condition>
<order_description>Müller &amp; Söhne — 日本語</order_description>
</transaction>
</nm_response>"""


def _transaction_xml(transaction_id: int) -> str:
    return (
        "<transaction>"
        f"<transaction_id>{transaction_id}</transaction_id>"
        "<condition>complete</condition>"
        "<action><action_type>sale</action_type><success>1</success></action>"
        "</transaction>"
    )


def _page(*transaction_ids: int) -> str:
    rows = "".join(_transaction_xml(i) for i in transaction_ids)
    return f"<nm_response>{rows}</nm_response>"


def sent_query(route, call_index: int = -1) -> dict[str, list[str]]:
    return parse_qs(route.calls[call_index].request.content.decode(), keep_blank_values=True)


async def test_transactions_parse_records_actions_and_products(client, respx_mock):
    respx_mock.post(QUERY_URL).mock(return_value=httpx.Response(200, text=TRANSACTION_PAGE))
    transactions = await collect(client.query.transactions())
    assert len(transactions) == 2
    first = transactions[0]
    assert first.transaction_id == "2612675976"
    assert first.cc_number == "4xxxxxxxxxxx1111"
    assert first.customer_vault_id == ""
    assert [a.action_type for a in first.actions] == ["sale", "settle"]
    assert first.actions[0].response_text == "SUCCESS"
    assert [p.sku for p in first.products] == ["RS-100"]
    assert transactions[1].order_description == "Müller & Söhne — 日本語"


async def test_filters_are_encoded_and_sent(client, respx_mock):
    route = respx_mock.post(QUERY_URL).mock(
        return_value=httpx.Response(200, text="<nm_response></nm_response>")
    )
    await collect(
        client.query.transactions(
            condition=["pendingsettlement", "complete"],
            action_type="sale,refund",
            source=["api"],
            transaction_id=["1", "2"],
            order_id="ord-1",
            start_date="20260101",
            end_date="20260201120000",
        )
    )
    assert sent_query(route) == {
        "security_key": ["test_key"],
        "condition": ["pendingsettlement,complete"],
        "action_type": ["sale,refund"],
        "source": ["api"],
        "transaction_id": ["1,2"],
        "order_id": ["ord-1"],
        "start_date": ["20260101000000"],
        "end_date": ["20260201120000"],
        "result_limit": ["100"],
        "page_number": ["0"],
    }


@pytest.mark.parametrize("body", ["<nm_response/>", "<nm_response></nm_response>"])
async def test_empty_nm_response_yields_no_records(client, respx_mock, body):
    respx_mock.post(QUERY_URL).mock(return_value=httpx.Response(200, text=body))
    assert await collect(client.query.transactions()) == []


async def test_malformed_xml_raises_api_error(client, respx_mock):
    respx_mock.post(QUERY_URL).mock(
        return_value=httpx.Response(200, text="<nm_response><oops</nm_response>")
    )
    with pytest.raises(APIError, match="invalid XML"):
        await collect(client.query.transactions())


async def test_doctype_is_rejected(client, respx_mock):
    body = '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY x "y">]><nm_response></nm_response>'
    respx_mock.post(QUERY_URL).mock(return_value=httpx.Response(200, text=body))
    with pytest.raises(APIError, match="DOCTYPE"):
        await collect(client.query.transactions())


async def test_error_response_auth_text_raises_authentication_error(client, respx_mock):
    body = "<nm_response><error_response>Authentication Failed</error_response></nm_response>"
    respx_mock.post(QUERY_URL).mock(return_value=httpx.Response(200, text=body))
    with pytest.raises(AuthenticationError):
        await collect(client.query.transactions())


async def test_error_response_other_text_raises_invalid_request(client, respx_mock):
    body = "<nm_response><error_response>Invalid date range</error_response></nm_response>"
    respx_mock.post(QUERY_URL).mock(return_value=httpx.Response(200, text=body))
    with pytest.raises(InvalidRequestError, match="Invalid date range"):
        await collect(client.query.transactions())


async def test_pagination_is_lazy_and_walks_page_numbers(client, respx_mock):
    pages = {
        "0": _page(*range(100)),
        "1": _page(100, 101, 102),
    }

    def respond(request) -> httpx.Response:
        page_number = parse_qs(request.content.decode())["page_number"][0]
        return httpx.Response(200, text=pages[page_number])

    route = respx_mock.post(QUERY_URL).mock(side_effect=respond)
    iterator = client.query.transactions()
    assert route.call_count == 0  # nothing fetched until iteration starts
    first = await take_one(iterator)
    assert first.transaction_id == "0"
    assert route.call_count == 1  # page 1 not fetched until page 0 is crossed
    rest = await collect(iterator)
    assert len(rest) == 102  # 103 total
    assert route.call_count == 2
    assert sent_query(route, 0)["page_number"] == ["0"]
    assert sent_query(route, 1)["page_number"] == ["1"]
    assert sent_query(route, 1)["result_limit"] == ["100"]


async def test_short_first_page_stops_after_one_fetch(client, respx_mock):
    route = respx_mock.post(QUERY_URL).mock(return_value=httpx.Response(200, text=_page(1, 2, 3)))
    results = await collect(client.query.transactions(page_size=50))
    assert len(results) == 3
    assert route.call_count == 1
    assert sent_query(route)["result_limit"] == ["50"]


async def test_exactly_full_last_page_fetches_one_empty_page(client, respx_mock):
    pages = {"0": _page(*range(5)), "1": "<nm_response></nm_response>"}

    def respond(request) -> httpx.Response:
        page_number = parse_qs(request.content.decode())["page_number"][0]
        return httpx.Response(200, text=pages[page_number])

    route = respx_mock.post(QUERY_URL).mock(side_effect=respond)
    results = await collect(client.query.transactions(page_size=5))
    assert len(results) == 5
    assert route.call_count == 2


async def test_page_size_must_be_positive(client):
    with pytest.raises(InvalidRequestError, match="page_size"):
        await maybe_await(client.query.transactions(page_size=0))


async def test_customers_report(client, respx_mock):
    body = (
        "<nm_response><customer_vault>"
        '<customer id="cv-1">'
        "<customer_vault_id>cv-1</customer_vault_id>"
        "<first_name>Jane</first_name>"
        "<cc_number>4xxxxxxxxxxx1111</cc_number>"
        "</customer>"
        "</customer_vault></nm_response>"
    )
    route = respx_mock.post(QUERY_URL).mock(return_value=httpx.Response(200, text=body))
    customers = await collect(client.query.customers(customer_vault_id="cv-1"))
    assert sent_query(route)["report_type"] == ["customer_vault"]
    assert sent_query(route)["customer_vault_id"] == ["cv-1"]
    assert len(customers) == 1
    assert customers[0].customer_vault_id == "cv-1"
    assert customers[0].first_name == "Jane"


async def test_subscriptions_report_with_nested_plan(client, respx_mock):
    body = (
        "<nm_response><subscription>"
        "<subscription_id>sub-9</subscription_id>"
        "<customer_vault_id>cv-1</customer_vault_id>"
        "<next_charge_date>2026-07-01</next_charge_date>"
        "<plan>"
        "<plan_id>gold</plan_id><plan_name>Gold</plan_name><plan_amount>49.00</plan_amount>"
        "</plan>"
        "</subscription></nm_response>"
    )
    route = respx_mock.post(QUERY_URL).mock(return_value=httpx.Response(200, text=body))
    subscriptions = await collect(client.query.subscriptions(subscription_id="sub-9"))
    assert sent_query(route)["report_type"] == ["recurring"]
    assert subscriptions[0].subscription_id == "sub-9"
    assert subscriptions[0].plan is not None
    assert subscriptions[0].plan.plan_id == "gold"
    assert subscriptions[0].plan.plan_amount == "49.00"


async def test_plans_report(client, respx_mock):
    body = (
        "<nm_response>"
        "<plan><plan_id>gold</plan_id><plan_name>Gold</plan_name>"
        "<day_frequency>30</day_frequency></plan>"
        "<plan><plan_id>silver</plan_id><plan_name>Silver</plan_name></plan>"
        "</nm_response>"
    )
    route = respx_mock.post(QUERY_URL).mock(return_value=httpx.Response(200, text=body))
    plans = await collect(client.query.plans())
    assert sent_query(route)["report_type"] == ["recurring_plans"]
    assert [p.plan_id for p in plans] == ["gold", "silver"]


async def test_invoices_report(client, respx_mock):
    body = (
        "<nm_response><invoice>"
        "<invoice_id>inv-1</invoice_id><amount>150.00</amount><status>open</status>"
        "</invoice></nm_response>"
    )
    route = respx_mock.post(QUERY_URL).mock(return_value=httpx.Response(200, text=body))
    invoices = await collect(client.query.invoices(invoice_status=["open", "past_due"]))
    assert sent_query(route)["report_type"] == ["invoicing"]
    assert sent_query(route)["invoice_status"] == ["open,past_due"]
    assert invoices[0].invoice_id == "inv-1"
    assert invoices[0].status == "open"
