from __future__ import annotations

import httpx
import pytest
from conftest import TRANSACT_URL, approved_body

from kicbac import AsyncKicbac, Kicbac
from kicbac.errors import AuthenticationError


class TestSecurityKeyResolution:
    def test_env_var_pickup(self, monkeypatch):
        monkeypatch.setenv("KICBAC_SECURITY_KEY", "env_key")
        with Kicbac() as client:
            assert client.transactions._security_key == "env_key"

    def test_explicit_key_wins_over_env(self, monkeypatch):
        monkeypatch.setenv("KICBAC_SECURITY_KEY", "env_key")
        with Kicbac(security_key="explicit") as client:
            assert client.transactions._security_key == "explicit"

    @pytest.mark.parametrize("client_class", [Kicbac, AsyncKicbac])
    def test_missing_key_raises_at_construction(self, monkeypatch, client_class):
        monkeypatch.delenv("KICBAC_SECURITY_KEY", raising=False)
        with pytest.raises(AuthenticationError, match="KICBAC_SECURITY_KEY"):
            client_class()

    def test_empty_key_raises(self, monkeypatch):
        monkeypatch.delenv("KICBAC_SECURITY_KEY", raising=False)
        with pytest.raises(AuthenticationError):
            Kicbac(security_key="")


class TestLifecycle:
    def test_sync_context_manager_closes_owned_client(self):
        with Kicbac(security_key="k") as client:
            http = client._http
            assert not http.is_closed
        assert http.is_closed

    async def test_async_context_manager_closes_owned_client(self):
        async with AsyncKicbac(security_key="k") as client:
            http = client._http
            assert not http.is_closed
        assert http.is_closed

    def test_byo_http_client_is_not_closed(self):
        http = httpx.Client()
        client = Kicbac(security_key="k", http_client=http)
        client.close()
        assert not http.is_closed
        http.close()

    async def test_byo_async_http_client_is_not_closed(self):
        http = httpx.AsyncClient()
        client = AsyncKicbac(security_key="k", http_client=http)
        await client.aclose()
        assert not http.is_closed
        await http.aclose()

    def test_byo_http_client_is_used_for_requests(self, respx_mock):
        respx_mock.post(TRANSACT_URL).mock(return_value=httpx.Response(200, text=approved_body()))
        http = httpx.Client(headers={"User-Agent": "byo-agent"})
        with Kicbac(security_key="k", http_client=http):
            pass
        client = Kicbac(security_key="k", http_client=http)
        client.transactions.sale(amount="1.00", payment_token="tok")
        request = respx_mock.calls.last.request
        assert request.headers["User-Agent"] == "byo-agent"
        http.close()


class TestRepr:
    def test_repr_redacts_key(self):
        client = Kicbac(security_key="sk_live_super_secret")
        try:
            assert "sk_live_super_secret" not in repr(client)
            assert "[REDACTED]" in repr(client)
        finally:
            client.close()

    async def test_async_repr_redacts_key(self):
        client = AsyncKicbac(security_key="sk_live_super_secret")
        try:
            assert "sk_live_super_secret" not in repr(client)
            assert "AsyncKicbac" in repr(client)
        finally:
            await client.aclose()


class TestBaseUrl:
    def test_custom_base_url_is_used(self, respx_mock):
        route = respx_mock.post("https://sandbox.example.com/api/transact.php").mock(
            return_value=httpx.Response(200, text=approved_body())
        )
        with Kicbac(security_key="k", base_url="https://sandbox.example.com/") as client:
            client.transactions.sale(amount="1.00", payment_token="tok")
        assert route.call_count == 1


def test_resource_namespaces_exist():
    with Kicbac(security_key="k") as client:
        for name in (
            "transactions",
            "customers",
            "plans",
            "subscriptions",
            "invoices",
            "query",
            "webhooks",
        ):
            assert hasattr(client, name)
    async_client = AsyncKicbac(security_key="k")
    for name in (
        "transactions",
        "customers",
        "plans",
        "subscriptions",
        "invoices",
        "query",
        "webhooks",
    ):
        assert hasattr(async_client, name)
