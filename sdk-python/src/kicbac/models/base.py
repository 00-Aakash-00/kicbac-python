from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class KicbacModel(BaseModel):
    """Base for all SDK models: immutable, unknown gateway fields preserved."""

    model_config = ConfigDict(frozen=True, extra="allow")
