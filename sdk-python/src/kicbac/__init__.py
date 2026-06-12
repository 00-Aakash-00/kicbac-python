"""Official Python SDK for the Kicbac payments gateway.

Quickstart::

    import kicbac

    client = kicbac.Kicbac()  # reads KICBAC_SECURITY_KEY
    result = client.transactions.sale(amount="19.99", payment_token="tok_from_collect_js")
    if result.ok:
        print("approved:", result.transaction_id)
    else:
        print("declined:", result.response_code, result.message)
"""

from kicbac import errors, models, types, webhooks
from kicbac._client import AsyncKicbac, Kicbac
from kicbac._version import __version__
from kicbac.errors import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AuthenticationError,
    InvalidRequestError,
    KicbacError,
    ProcessorError,
    RateLimitError,
    SignatureVerificationError,
    WebhookPayloadError,
)
from kicbac.models import (
    InvoiceResult,
    PlanResult,
    QueryAction,
    QueryCustomer,
    QueryInvoice,
    QueryPlan,
    QueryProduct,
    QuerySubscription,
    QueryTransaction,
    SubscriptionResult,
    TransactionApproved,
    TransactionDeclined,
    TransactionResult,
    VaultResult,
    WebhookEvent,
)
from kicbac.types import BillingParams, Money, ShippingParams
from kicbac.webhooks import construct_event

__all__ = [
    "APIConnectionError",
    "APIError",
    "APITimeoutError",
    "AsyncKicbac",
    "AuthenticationError",
    "BillingParams",
    "InvalidRequestError",
    "InvoiceResult",
    "Kicbac",
    "KicbacError",
    "Money",
    "PlanResult",
    "ProcessorError",
    "QueryAction",
    "QueryCustomer",
    "QueryInvoice",
    "QueryPlan",
    "QueryProduct",
    "QuerySubscription",
    "QueryTransaction",
    "RateLimitError",
    "ShippingParams",
    "SignatureVerificationError",
    "SubscriptionResult",
    "TransactionApproved",
    "TransactionDeclined",
    "TransactionResult",
    "VaultResult",
    "WebhookEvent",
    "WebhookPayloadError",
    "__version__",
    "construct_event",
    "errors",
    "models",
    "types",
    "webhooks",
]
