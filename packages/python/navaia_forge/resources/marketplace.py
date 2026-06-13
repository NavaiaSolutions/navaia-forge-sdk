"""Marketplace resource.

The backend exposes the public marketplace catalog under ``/api/v1/marketplace``::

    client.marketplace.list()                 # browse published workforces
    client.marketplace.list(category="sales", search="crm", is_free=True)
    client.marketplace.get("wf_pub_1")        # listing detail
    wf = client.marketplace.install("wf_pub_1")  # copy into your backend

Browsing is read-only and surfaces every workforce you have access to — your
own published listings plus those published by others. ``install`` clones the
listing into your own backend (returning a fresh :class:`Workforce`) so you can
run it locally. Paid listings (``price_cents > 0``) reject install with HTTP
402 until billing is wired up.
"""

from __future__ import annotations

from typing import Any

from ..types import MarketplaceListing, Workforce
from ._base import ResourceBase, parse_list, parse_model


def _drop_none(payload: dict[str, Any]) -> dict[str, Any]:
    """Strip keys whose value is ``None`` so backend defaults apply."""
    return {key: value for key, value in payload.items() if value is not None}


class MarketplaceResource(ResourceBase):
    """Operations against ``/api/v1/marketplace``."""

    def list(
        self,
        *,
        category: str | None = None,
        search: str | None = None,
        is_free: bool | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[MarketplaceListing]:
        """Browse published marketplace listings.

        Filter by ``category``, free-text ``search``, or ``is_free`` (only
        zero-cost listings). Results are paginated via ``offset``/``limit``.
        """
        params = _drop_none(
            {
                "category": category,
                "search": search,
                "is_free": is_free,
                "offset": offset,
                "limit": limit,
            }
        )
        return parse_list(
            MarketplaceListing,
            self._http.get_list("/marketplace/listings", params=params),
        )

    def get(self, workforce_id: str) -> MarketplaceListing:
        """Fetch a single marketplace listing by workforce id."""
        return parse_model(
            MarketplaceListing,
            self._http.get(f"/marketplace/listings/{workforce_id}"),
        )

    def install(self, workforce_id: str) -> Workforce:
        """Install a marketplace listing into your own backend.

        Clones the published workforce (agents, edges, config) into your
        account and returns the new :class:`Workforce`. Raises on paid listings
        (HTTP 402) or when the hourly install rate limit is exceeded (HTTP 429).
        """
        return parse_model(
            Workforce,
            self._http.post(f"/marketplace/listings/{workforce_id}/install"),
        )
