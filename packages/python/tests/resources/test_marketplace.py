"""Tests for MarketplaceResource (browse / get / install)."""

from __future__ import annotations

import pytest

from navaia_forge import (
    MarketplaceListing,
    NavaiaForgeError,
    NotFoundError,
    RateLimitError,
    Workforce,
)


@pytest.fixture
def listing_payload() -> dict:
    return {
        "id": "wf_pub_1",
        "name": "Sales Squad",
        "description": "Outbound sales automation",
        "tagline": "Close more deals",
        "category": "sales",
        "cover_url": "https://cdn.example/cover.png",
        "price_cents": 0,
        "currency": "usd",
        "install_count": 42,
        "published_at": "2026-06-01T00:00:00Z",
        "seller_id": "user_9",
        "seller_name": "Acme Co",
        "agent_count": 4,
    }


@pytest.mark.integration
def test_list_listings(httpx_mock, client, base_url, listing_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/marketplace/listings?offset=0&limit=50",
        method="GET",
        json={"items": [listing_payload], "total": 1},
    )
    listings = client.marketplace.list()
    assert isinstance(listings[0], MarketplaceListing)
    assert listings[0].name == "Sales Squad"
    assert listings[0].agent_count == 4


@pytest.mark.integration
def test_list_listings_with_filters(httpx_mock, client, base_url, listing_payload) -> None:
    httpx_mock.add_response(
        url=(
            f"{base_url}/api/v1/marketplace/listings"
            "?category=sales&search=deals&is_free=true&offset=0&limit=10"
        ),
        method="GET",
        json={"items": [listing_payload], "total": 1},
    )
    listings = client.marketplace.list(
        category="sales", search="deals", is_free=True, limit=10
    )
    assert listings[0].id == "wf_pub_1"


@pytest.mark.integration
def test_get_listing(httpx_mock, client, base_url, listing_payload) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/marketplace/listings/wf_pub_1",
        method="GET",
        json=listing_payload,
    )
    listing = client.marketplace.get("wf_pub_1")
    assert isinstance(listing, MarketplaceListing)
    assert listing.seller_name == "Acme Co"


@pytest.mark.integration
def test_get_listing_not_found(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/marketplace/listings/missing",
        method="GET",
        status_code=404,
        json={"detail": "Listing not found"},
    )
    with pytest.raises(NotFoundError):
        client.marketplace.get("missing")


@pytest.mark.integration
def test_install_returns_workforce(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/marketplace/listings/wf_pub_1/install",
        method="POST",
        status_code=201,
        json={
            "id": "wf_local_99",
            "name": "Sales Squad",
            "description": "Outbound sales automation",
            "runtime_mode": "claude_max",
            "config_json": {},
            "status": "active",
            "is_public": False,
        },
    )
    wf = client.marketplace.install("wf_pub_1")
    assert isinstance(wf, Workforce)
    assert wf.id == "wf_local_99"
    assert wf.is_public is False


@pytest.mark.integration
def test_install_paid_listing_rejected(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/marketplace/listings/wf_paid/install",
        method="POST",
        status_code=402,
        json={"detail": "Payment required"},
    )
    with pytest.raises(NavaiaForgeError) as exc:
        client.marketplace.install("wf_paid")
    assert exc.value.status_code == 402


@pytest.mark.integration
def test_install_rate_limited(httpx_mock, client, base_url) -> None:
    httpx_mock.add_response(
        url=f"{base_url}/api/v1/marketplace/listings/wf_pub_1/install",
        method="POST",
        status_code=429,
        json={"detail": "Too many installs"},
    )
    with pytest.raises(RateLimitError):
        client.marketplace.install("wf_pub_1")
