"""Query API (query.php) reports as lazy iterators of pydantic models.

Pages are fetched with ``result_limit``/``page_number`` only as the iterator
is consumed; iteration stops after the first non-full page.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator, Mapping, Sequence
from datetime import date, datetime

import httpx

from kicbac._core import build_query_request
from kicbac._encode import encode_csv, encode_datetime, put
from kicbac._pagination import paginate, paginate_async
from kicbac._xml import parse_query_records
from kicbac.errors import InvalidRequestError
from kicbac.models.query import (
    QueryCustomer,
    QueryInvoice,
    QueryPlan,
    QuerySubscription,
    QueryTransaction,
)
from kicbac.resources._base import AsyncResource, SyncResource

__all__ = ["AsyncQuery", "Query"]

_DEFAULT_PAGE_SIZE = 100


def _check_page_size(page_size: int) -> None:
    if page_size < 1:
        raise InvalidRequestError("page_size must be at least 1")


def _date_range(
    params: dict[str, str],
    start_date: datetime | date | str | None,
    end_date: datetime | date | str | None,
) -> None:
    if start_date is not None:
        params["start_date"] = encode_datetime(start_date, field="start_date")
    if end_date is not None:
        params["end_date"] = encode_datetime(end_date, field="end_date")


def _transactions_filters(
    *,
    condition: str | Sequence[str] | None,
    transaction_type: str | None,
    action_type: str | Sequence[str] | None,
    source: str | Sequence[str] | None,
    transaction_id: str | Sequence[str] | None,
    subscription_id: str | None,
    order_id: str | None,
    first_name: str | None,
    last_name: str | None,
    email: str | None,
    start_date: datetime | date | str | None,
    end_date: datetime | date | str | None,
    extra_params: Mapping[str, str] | None,
) -> dict[str, str]:
    params: dict[str, str] = {}
    if condition is not None:
        params["condition"] = encode_csv(condition, field="condition")
    put(params, "transaction_type", transaction_type)
    if action_type is not None:
        params["action_type"] = encode_csv(action_type, field="action_type")
    if source is not None:
        params["source"] = encode_csv(source, field="source")
    if transaction_id is not None:
        params["transaction_id"] = encode_csv(transaction_id, field="transaction_id")
    put(params, "subscription_id", subscription_id)
    put(params, "order_id", order_id)
    put(params, "first_name", first_name)
    put(params, "last_name", last_name)
    put(params, "email", email)
    _date_range(params, start_date, end_date)
    if extra_params is not None:
        params.update(extra_params)
    return params


def _customers_filters(
    *,
    customer_vault_id: str | None,
    date_search: str | Sequence[str] | None,
    start_date: datetime | date | str | None,
    end_date: datetime | date | str | None,
    extra_params: Mapping[str, str] | None,
) -> dict[str, str]:
    params: dict[str, str] = {"report_type": "customer_vault"}
    put(params, "customer_vault_id", customer_vault_id)
    if date_search is not None:
        params["date_search"] = encode_csv(date_search, field="date_search")
    _date_range(params, start_date, end_date)
    if extra_params is not None:
        params.update(extra_params)
    return params


def _subscriptions_filters(
    *,
    subscription_id: str | Sequence[str] | None,
    start_date: datetime | date | str | None,
    end_date: datetime | date | str | None,
    extra_params: Mapping[str, str] | None,
) -> dict[str, str]:
    params: dict[str, str] = {"report_type": "recurring"}
    if subscription_id is not None:
        params["subscription_id"] = encode_csv(subscription_id, field="subscription_id")
    _date_range(params, start_date, end_date)
    if extra_params is not None:
        params.update(extra_params)
    return params


def _plans_filters(*, extra_params: Mapping[str, str] | None) -> dict[str, str]:
    params: dict[str, str] = {"report_type": "recurring_plans"}
    if extra_params is not None:
        params.update(extra_params)
    return params


def _invoices_filters(
    *,
    invoice_id: str | None,
    invoice_status: str | Sequence[str] | None,
    start_date: datetime | date | str | None,
    end_date: datetime | date | str | None,
    extra_params: Mapping[str, str] | None,
) -> dict[str, str]:
    params: dict[str, str] = {"report_type": "invoicing"}
    put(params, "invoice_id", invoice_id)
    if invoice_status is not None:
        params["invoice_status"] = encode_csv(invoice_status, field="invoice_status")
    _date_range(params, start_date, end_date)
    if extra_params is not None:
        params.update(extra_params)
    return params


class Query(SyncResource):
    """Sync Query API reports."""

    def _fetch_records(
        self,
        filters: Mapping[str, str],
        *,
        tag: str,
        page_size: int,
        page_number: int,
        timeout: float | httpx.Timeout | None,
    ) -> list[dict[str, object]]:
        params = {**filters, "result_limit": str(page_size), "page_number": str(page_number)}
        spec = build_query_request(self._security_key, params)
        body = self._transport.request(spec, timeout=timeout)
        return parse_query_records(body, tag)

    def transactions(
        self,
        *,
        condition: str | Sequence[str] | None = None,
        transaction_type: str | None = None,
        action_type: str | Sequence[str] | None = None,
        source: str | Sequence[str] | None = None,
        transaction_id: str | Sequence[str] | None = None,
        subscription_id: str | None = None,
        order_id: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
        start_date: datetime | date | str | None = None,
        end_date: datetime | date | str | None = None,
        page_size: int = _DEFAULT_PAGE_SIZE,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> Iterator[QueryTransaction]:
        """Iterate transactions matching the filters (Query API variables)."""
        _check_page_size(page_size)
        filters = _transactions_filters(
            condition=condition,
            transaction_type=transaction_type,
            action_type=action_type,
            source=source,
            transaction_id=transaction_id,
            subscription_id=subscription_id,
            order_id=order_id,
            first_name=first_name,
            last_name=last_name,
            email=email,
            start_date=start_date,
            end_date=end_date,
            extra_params=extra_params,
        )

        def fetch(page_number: int) -> list[QueryTransaction]:
            records = self._fetch_records(
                filters,
                tag="transaction",
                page_size=page_size,
                page_number=page_number,
                timeout=timeout,
            )
            return [QueryTransaction.model_validate(record) for record in records]

        return paginate(fetch, page_size)

    def customers(
        self,
        *,
        customer_vault_id: str | None = None,
        date_search: str | Sequence[str] | None = None,
        start_date: datetime | date | str | None = None,
        end_date: datetime | date | str | None = None,
        page_size: int = _DEFAULT_PAGE_SIZE,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> Iterator[QueryCustomer]:
        """Iterate Customer Vault records (``report_type=customer_vault``)."""
        _check_page_size(page_size)
        filters = _customers_filters(
            customer_vault_id=customer_vault_id,
            date_search=date_search,
            start_date=start_date,
            end_date=end_date,
            extra_params=extra_params,
        )

        def fetch(page_number: int) -> list[QueryCustomer]:
            records = self._fetch_records(
                filters,
                tag="customer",
                page_size=page_size,
                page_number=page_number,
                timeout=timeout,
            )
            return [QueryCustomer.model_validate(record) for record in records]

        return paginate(fetch, page_size)

    def subscriptions(
        self,
        *,
        subscription_id: str | Sequence[str] | None = None,
        start_date: datetime | date | str | None = None,
        end_date: datetime | date | str | None = None,
        page_size: int = _DEFAULT_PAGE_SIZE,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> Iterator[QuerySubscription]:
        """Iterate subscriptions (``report_type=recurring``)."""
        _check_page_size(page_size)
        filters = _subscriptions_filters(
            subscription_id=subscription_id,
            start_date=start_date,
            end_date=end_date,
            extra_params=extra_params,
        )

        def fetch(page_number: int) -> list[QuerySubscription]:
            records = self._fetch_records(
                filters,
                tag="subscription",
                page_size=page_size,
                page_number=page_number,
                timeout=timeout,
            )
            return [QuerySubscription.model_validate(record) for record in records]

        return paginate(fetch, page_size)

    def plans(
        self,
        *,
        page_size: int = _DEFAULT_PAGE_SIZE,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> Iterator[QueryPlan]:
        """Iterate recurring plans (``report_type=recurring_plans``)."""
        _check_page_size(page_size)
        filters = _plans_filters(extra_params=extra_params)

        def fetch(page_number: int) -> list[QueryPlan]:
            records = self._fetch_records(
                filters,
                tag="plan",
                page_size=page_size,
                page_number=page_number,
                timeout=timeout,
            )
            return [QueryPlan.model_validate(record) for record in records]

        return paginate(fetch, page_size)

    def invoices(
        self,
        *,
        invoice_id: str | None = None,
        invoice_status: str | Sequence[str] | None = None,
        start_date: datetime | date | str | None = None,
        end_date: datetime | date | str | None = None,
        page_size: int = _DEFAULT_PAGE_SIZE,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> Iterator[QueryInvoice]:
        """Iterate invoices (``report_type=invoicing``)."""
        _check_page_size(page_size)
        filters = _invoices_filters(
            invoice_id=invoice_id,
            invoice_status=invoice_status,
            start_date=start_date,
            end_date=end_date,
            extra_params=extra_params,
        )

        def fetch(page_number: int) -> list[QueryInvoice]:
            records = self._fetch_records(
                filters,
                tag="invoice",
                page_size=page_size,
                page_number=page_number,
                timeout=timeout,
            )
            return [QueryInvoice.model_validate(record) for record in records]

        return paginate(fetch, page_size)


class AsyncQuery(AsyncResource):
    """Async Query API reports."""

    async def _fetch_records(
        self,
        filters: Mapping[str, str],
        *,
        tag: str,
        page_size: int,
        page_number: int,
        timeout: float | httpx.Timeout | None,
    ) -> list[dict[str, object]]:
        params = {**filters, "result_limit": str(page_size), "page_number": str(page_number)}
        spec = build_query_request(self._security_key, params)
        body = await self._transport.request(spec, timeout=timeout)
        return parse_query_records(body, tag)

    def transactions(
        self,
        *,
        condition: str | Sequence[str] | None = None,
        transaction_type: str | None = None,
        action_type: str | Sequence[str] | None = None,
        source: str | Sequence[str] | None = None,
        transaction_id: str | Sequence[str] | None = None,
        subscription_id: str | None = None,
        order_id: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
        start_date: datetime | date | str | None = None,
        end_date: datetime | date | str | None = None,
        page_size: int = _DEFAULT_PAGE_SIZE,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> AsyncIterator[QueryTransaction]:
        """Iterate transactions matching the filters (Query API variables)."""
        _check_page_size(page_size)
        filters = _transactions_filters(
            condition=condition,
            transaction_type=transaction_type,
            action_type=action_type,
            source=source,
            transaction_id=transaction_id,
            subscription_id=subscription_id,
            order_id=order_id,
            first_name=first_name,
            last_name=last_name,
            email=email,
            start_date=start_date,
            end_date=end_date,
            extra_params=extra_params,
        )

        async def fetch(page_number: int) -> list[QueryTransaction]:
            records = await self._fetch_records(
                filters,
                tag="transaction",
                page_size=page_size,
                page_number=page_number,
                timeout=timeout,
            )
            return [QueryTransaction.model_validate(record) for record in records]

        return paginate_async(fetch, page_size)

    def customers(
        self,
        *,
        customer_vault_id: str | None = None,
        date_search: str | Sequence[str] | None = None,
        start_date: datetime | date | str | None = None,
        end_date: datetime | date | str | None = None,
        page_size: int = _DEFAULT_PAGE_SIZE,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> AsyncIterator[QueryCustomer]:
        """Iterate Customer Vault records (``report_type=customer_vault``)."""
        _check_page_size(page_size)
        filters = _customers_filters(
            customer_vault_id=customer_vault_id,
            date_search=date_search,
            start_date=start_date,
            end_date=end_date,
            extra_params=extra_params,
        )

        async def fetch(page_number: int) -> list[QueryCustomer]:
            records = await self._fetch_records(
                filters,
                tag="customer",
                page_size=page_size,
                page_number=page_number,
                timeout=timeout,
            )
            return [QueryCustomer.model_validate(record) for record in records]

        return paginate_async(fetch, page_size)

    def subscriptions(
        self,
        *,
        subscription_id: str | Sequence[str] | None = None,
        start_date: datetime | date | str | None = None,
        end_date: datetime | date | str | None = None,
        page_size: int = _DEFAULT_PAGE_SIZE,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> AsyncIterator[QuerySubscription]:
        """Iterate subscriptions (``report_type=recurring``)."""
        _check_page_size(page_size)
        filters = _subscriptions_filters(
            subscription_id=subscription_id,
            start_date=start_date,
            end_date=end_date,
            extra_params=extra_params,
        )

        async def fetch(page_number: int) -> list[QuerySubscription]:
            records = await self._fetch_records(
                filters,
                tag="subscription",
                page_size=page_size,
                page_number=page_number,
                timeout=timeout,
            )
            return [QuerySubscription.model_validate(record) for record in records]

        return paginate_async(fetch, page_size)

    def plans(
        self,
        *,
        page_size: int = _DEFAULT_PAGE_SIZE,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> AsyncIterator[QueryPlan]:
        """Iterate recurring plans (``report_type=recurring_plans``)."""
        _check_page_size(page_size)
        filters = _plans_filters(extra_params=extra_params)

        async def fetch(page_number: int) -> list[QueryPlan]:
            records = await self._fetch_records(
                filters,
                tag="plan",
                page_size=page_size,
                page_number=page_number,
                timeout=timeout,
            )
            return [QueryPlan.model_validate(record) for record in records]

        return paginate_async(fetch, page_size)

    def invoices(
        self,
        *,
        invoice_id: str | None = None,
        invoice_status: str | Sequence[str] | None = None,
        start_date: datetime | date | str | None = None,
        end_date: datetime | date | str | None = None,
        page_size: int = _DEFAULT_PAGE_SIZE,
        extra_params: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> AsyncIterator[QueryInvoice]:
        """Iterate invoices (``report_type=invoicing``)."""
        _check_page_size(page_size)
        filters = _invoices_filters(
            invoice_id=invoice_id,
            invoice_status=invoice_status,
            start_date=start_date,
            end_date=end_date,
            extra_params=extra_params,
        )

        async def fetch(page_number: int) -> list[QueryInvoice]:
            records = await self._fetch_records(
                filters,
                tag="invoice",
                page_size=page_size,
                page_number=page_number,
                timeout=timeout,
            )
            return [QueryInvoice.model_validate(record) for record in records]

        return paginate_async(fetch, page_size)
