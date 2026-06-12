from __future__ import annotations

from typing import Any

from kicbac.models.base import KicbacModel

__all__ = ["WebhookEvent"]


class WebhookEvent(KicbacModel):
    """A verified webhook event.

    Deduplicate deliveries with ``event_id`` (the gateway retries failed
    deliveries, so the same event may arrive more than once).
    """

    event_id: str
    event_type: str
    event_body: dict[str, Any]

    @property
    def merchant_id(self) -> str | None:
        merchant = self.event_body.get("merchant")
        if isinstance(merchant, dict):
            merchant_id = merchant.get("id")
            if isinstance(merchant_id, str):
                return merchant_id
        return None

    @property
    def is_test_mode(self) -> bool:
        features = self.event_body.get("features")
        if isinstance(features, dict):
            return bool(features.get("is_test_mode"))
        return False
