"""Models for Query API (query.php) records.

All fields mirror the gateway XML element names; values stay strings exactly
as returned (amounts like ``"11.00"``, dates like ``"20150312215205"``).
Unknown elements are preserved via ``extra="allow"``. Card numbers in query
results are already masked by the gateway (e.g. ``4xxxxxxxxxxx1111``).
"""

from __future__ import annotations

from pydantic import Field

from kicbac.models.base import KicbacModel

__all__ = [
    "QueryAction",
    "QueryCustomer",
    "QueryInvoice",
    "QueryPlan",
    "QueryProduct",
    "QuerySubscription",
    "QueryTransaction",
]


class QueryAction(KicbacModel):
    amount: str | None = None
    action_type: str | None = None
    date: str | None = None
    success: str | None = None
    ip_address: str | None = None
    source: str | None = None
    api_method: str | None = None
    username: str | None = None
    response_text: str | None = None
    batch_id: str | None = None
    processor_batch_id: str | None = None
    response_code: str | None = None
    processor_response_text: str | None = None
    processor_response_code: str | None = None


class QueryProduct(KicbacModel):
    sku: str | None = None
    quantity: str | None = None
    description: str | None = None
    amount: str | None = None


class QueryTransaction(KicbacModel):
    transaction_id: str | None = None
    partial_payment_id: str | None = None
    partial_payment_balance: str | None = None
    platform_id: str | None = None
    transaction_type: str | None = None
    condition: str | None = None
    order_id: str | None = None
    authorization_code: str | None = None
    ponumber: str | None = None
    order_description: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    address_1: str | None = None
    address_2: str | None = None
    company: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None
    email: str | None = None
    phone: str | None = None
    cc_number: str | None = None
    cc_hash: str | None = None
    cc_exp: str | None = None
    cc_type: str | None = None
    cc_bin: str | None = None
    check_account: str | None = None
    check_aba: str | None = None
    check_name: str | None = None
    avs_response: str | None = None
    csc_response: str | None = None
    processor_id: str | None = None
    tax: str | None = None
    currency: str | None = None
    surcharge: str | None = None
    tip: str | None = None
    customerid: str | None = None
    customer_vault_id: str | None = None
    entry_mode: str | None = None
    actions: list[QueryAction] = Field(default_factory=list)
    products: list[QueryProduct] = Field(default_factory=list)


class QueryCustomer(KicbacModel):
    customer_vault_id: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    company: str | None = None
    address_1: str | None = None
    address_2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None
    email: str | None = None
    phone: str | None = None
    cc_number: str | None = None
    cc_hash: str | None = None
    cc_exp: str | None = None
    cc_type: str | None = None
    check_account: str | None = None
    check_aba: str | None = None
    check_name: str | None = None
    created: str | None = None
    updated: str | None = None


class QueryPlan(KicbacModel):
    plan_id: str | None = None
    plan_name: str | None = None
    plan_amount: str | None = None
    plan_payments: str | None = None
    day_frequency: str | None = None
    month_frequency: str | None = None
    day_of_month: str | None = None


class QuerySubscription(KicbacModel):
    subscription_id: str | None = None
    customer_vault_id: str | None = None
    plan: QueryPlan | None = None
    next_charge_date: str | None = None
    completed_payments: str | None = None
    attempted_payments: str | None = None
    remaining_payments: str | None = None
    order_id: str | None = None
    order_description: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    cc_number: str | None = None
    cc_exp: str | None = None


class QueryInvoice(KicbacModel):
    invoice_id: str | None = None
    amount: str | None = None
    currency: str | None = None
    status: str | None = None
    email: str | None = None
    customer_id: str | None = None
    order_description: str | None = None
    orderid: str | None = None
    created: str | None = None
