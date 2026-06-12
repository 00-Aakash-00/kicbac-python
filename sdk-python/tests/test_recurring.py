"""Plans + subscriptions (recurring=...) request building."""

from __future__ import annotations

from datetime import date
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


class TestPlans:
    async def test_create_with_day_frequency(self, client, respx_mock):
        route = respx_mock.post(TRANSACT_URL).mock(
            return_value=httpx.Response(200, text=ok_body(plan_id="gold"))
        )
        result = await maybe_await(
            client.plans.create("gold", name="Gold", amount="49.00", payments=0, day_frequency=30)
        )
        assert sent_fields(route) == {
            "security_key": ["test_key"],
            "recurring": ["add_plan"],
            "plan_id": ["gold"],
            "plan_name": ["Gold"],
            "plan_amount": ["49.00"],
            "plan_payments": ["0"],
            "day_frequency": ["30"],
        }
        assert result.ok is True
        assert result.plan_id == "gold"

    async def test_create_with_monthly_schedule(self, client, respx_mock):
        route = respx_mock.post(TRANSACT_URL).mock(return_value=httpx.Response(200, text=ok_body()))
        await maybe_await(
            client.plans.create(
                "gold", name="Gold", amount="49.00", month_frequency=1, day_of_month=15
            )
        )
        fields = sent_fields(route)
        assert fields["month_frequency"] == ["1"]
        assert fields["day_of_month"] == ["15"]
        assert "day_frequency" not in fields

    @pytest.mark.parametrize(
        ("kwargs", "match"),
        [
            ({"day_frequency": 30, "month_frequency": 1, "day_of_month": 1}, "cannot be combined"),
            ({"day_frequency": 30, "day_of_month": 1}, "cannot be combined"),
            ({"month_frequency": 1}, "set together"),
            ({"day_of_month": 15}, "set together"),
            ({}, "schedule is required"),
            ({"month_frequency": 25, "day_of_month": 1}, "1 through 24"),
            ({"month_frequency": 1, "day_of_month": 32}, "1 through 31"),
            ({"day_frequency": 0}, "positive"),
        ],
    )
    async def test_create_schedule_validation(self, client, respx_mock, kwargs, match):
        route = respx_mock.post(TRANSACT_URL)
        with pytest.raises(InvalidRequestError, match=match):
            await maybe_await(client.plans.create("gold", name="Gold", amount="49.00", **kwargs))
        assert route.call_count == 0

    async def test_update_uses_current_plan_id(self, client, respx_mock):
        route = respx_mock.post(TRANSACT_URL).mock(return_value=httpx.Response(200, text=ok_body()))
        await maybe_await(client.plans.update("gold", amount="59.00"))
        assert sent_fields(route) == {
            "security_key": ["test_key"],
            "recurring": ["edit_plan"],
            "current_plan_id": ["gold"],
            "plan_amount": ["59.00"],
        }

    def test_plans_have_no_delete(self, client):
        assert not hasattr(client.plans, "delete")


class TestSubscriptions:
    async def test_create_with_vault_customer(self, client, respx_mock):
        route = respx_mock.post(TRANSACT_URL).mock(
            return_value=httpx.Response(200, text=ok_body(subscription_id="sub-9"))
        )
        result = await maybe_await(
            client.subscriptions.create(
                "gold", customer_vault_id="cv-1", start_date=date(2026, 7, 1)
            )
        )
        assert sent_fields(route) == {
            "security_key": ["test_key"],
            "recurring": ["add_subscription"],
            "plan_id": ["gold"],
            "customer_vault_id": ["cv-1"],
            "start_date": ["20260701"],
        }
        assert result.subscription_id == "sub-9"

    async def test_create_with_payment_token_and_string_date(self, client, respx_mock):
        route = respx_mock.post(TRANSACT_URL).mock(return_value=httpx.Response(200, text=ok_body()))
        await maybe_await(
            client.subscriptions.create("gold", payment_token="tok", start_date="20260701")
        )
        fields = sent_fields(route)
        assert fields["payment_token"] == ["tok"]
        assert fields["start_date"] == ["20260701"]

    async def test_create_requires_exactly_one_payment_source(self, client, respx_mock):
        route = respx_mock.post(TRANSACT_URL)
        with pytest.raises(InvalidRequestError, match="no payment source"):
            await maybe_await(client.subscriptions.create("gold"))
        with pytest.raises(InvalidRequestError, match="not both"):
            await maybe_await(
                client.subscriptions.create("gold", customer_vault_id="cv", payment_token="tok")
            )
        assert route.call_count == 0

    async def test_create_rejects_bad_start_date(self, client, respx_mock):
        with pytest.raises(InvalidRequestError, match="start_date"):
            await maybe_await(
                client.subscriptions.create("gold", customer_vault_id="cv", start_date="07/01/2026")
            )

    @pytest.mark.parametrize(("paused", "encoded"), [(True, "true"), (False, "false")])
    async def test_update_paused_maps_to_paused_subscription(
        self, client, respx_mock, paused, encoded
    ):
        route = respx_mock.post(TRANSACT_URL).mock(return_value=httpx.Response(200, text=ok_body()))
        await maybe_await(client.subscriptions.update("sub-9", paused=paused))
        assert sent_fields(route) == {
            "security_key": ["test_key"],
            "recurring": ["update_subscription"],
            "subscription_id": ["sub-9"],
            "paused_subscription": [encoded],
        }

    async def test_update_amount_and_schedule(self, client, respx_mock):
        route = respx_mock.post(TRANSACT_URL).mock(return_value=httpx.Response(200, text=ok_body()))
        await maybe_await(
            client.subscriptions.update("sub-9", amount="12.00", payments=6, day_frequency=14)
        )
        fields = sent_fields(route)
        assert fields["plan_amount"] == ["12.00"]
        assert fields["plan_payments"] == ["6"]
        assert fields["day_frequency"] == ["14"]

    async def test_delete(self, client, respx_mock):
        route = respx_mock.post(TRANSACT_URL).mock(return_value=httpx.Response(200, text=ok_body()))
        await maybe_await(client.subscriptions.delete("sub-9"))
        assert sent_fields(route) == {
            "security_key": ["test_key"],
            "recurring": ["delete_subscription"],
            "subscription_id": ["sub-9"],
        }
