"""Shared helpers for resource modules."""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

from ..http import HttpClient

T = TypeVar("T", bound=BaseModel)


class ResourceBase:
    """Tiny mixin that gives every resource a typed HTTP client handle."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http


def parse_model(model: type[T], payload: Any) -> T:
    """Validate ``payload`` against ``model``."""
    return model.model_validate(payload)


def parse_list(model: type[T], payload: Any) -> list[T]:
    """Validate a list payload (or paginated envelope) against ``model``."""
    if isinstance(payload, dict) and "items" in payload:
        payload = payload["items"]
    if not isinstance(payload, list):
        return []
    return [model.model_validate(item) for item in payload]
