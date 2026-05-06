"""HTTP transport for the NavaiaForge SDK.

Wraps :class:`httpx.Client` and exposes typed convenience helpers used by every
resource module. The transport is responsible for:

* URL construction (``/api/v1`` prefix)
* Auth header injection (``X-API-Key``)
* Status-code -> typed-exception mapping
* Paginated list unwrapping (``{"items": [...], "total": N}``)
* Multipart file uploads

The transport is intentionally stateless beyond the wrapped client: every call
returns parsed JSON (or ``None`` on 204) and raises on non-2xx.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, BinaryIO

import httpx

from .errors import NavaiaForgeError, error_from_status


@dataclass(frozen=True)
class HttpConfig:
    """Immutable transport configuration."""

    base_url: str
    api_key: str
    timeout: float


class HttpClient:
    """Thin wrapper around ``httpx.Client`` that injects auth + maps errors."""

    def __init__(self, config: HttpConfig) -> None:
        self._config = config
        self._client = httpx.Client(timeout=config.timeout)

    # ── Lifecycle ──────────────────────────────────────────────

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> HttpClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ── URL / header helpers ───────────────────────────────────

    @property
    def base_url(self) -> str:
        return self._config.base_url

    @property
    def api_key(self) -> str:
        return self._config.api_key

    def _build_url(self, path: str) -> str:
        base = self._config.base_url.rstrip("/")
        return f"{base}/api/v1{path}"

    def _build_headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers: dict[str, str] = {"Accept": "application/json"}
        if self._config.api_key:
            headers["X-API-Key"] = self._config.api_key
        if extra:
            headers.update(extra)
        return headers

    # ── Core request ───────────────────────────────────────────

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: Any | None = None,
        params: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Execute a request, raise typed errors, return parsed JSON or ``None``."""
        url = self._build_url(path)
        merged_headers = self._build_headers(headers)
        # httpx does not let you set Content-Type when uploading multipart.
        if json_body is not None and files is None:
            merged_headers.setdefault("Content-Type", "application/json")

        # Filter out None query params and stringify the rest.
        query: dict[str, str] | None = None
        if params:
            query = {k: str(v) for k, v in params.items() if v is not None}

        try:
            response = self._client.request(
                method,
                url,
                json=json_body if files is None else None,
                params=query,
                headers=merged_headers,
                files=files,
            )
        except httpx.TimeoutException as exc:
            raise NavaiaForgeError(0, f"Request timed out: {exc}") from exc
        except httpx.RequestError as exc:
            raise NavaiaForgeError(0, f"Network error: {exc}") from exc

        if response.status_code == 204:
            return None

        if not response.is_success:
            try:
                payload = response.json()
                detail = payload.get("detail") or payload.get("error") or response.text
            except Exception:
                detail = response.text or response.reason_phrase
            raise error_from_status(response.status_code, str(detail))

        if not response.content:
            return None
        return response.json()

    # ── Convenience verbs ──────────────────────────────────────

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return self.request("GET", path, params=params)

    def post(self, path: str, body: Any | None = None) -> Any:
        return self.request("POST", path, json_body=body)

    def put(self, path: str, body: Any | None = None) -> Any:
        return self.request("PUT", path, json_body=body)

    def patch(self, path: str, body: Any | None = None) -> Any:
        return self.request("PATCH", path, json_body=body)

    def delete(self, path: str) -> Any:
        return self.request("DELETE", path)

    # ── Specialized helpers ────────────────────────────────────

    def get_list(self, path: str, params: dict[str, Any] | None = None) -> list[Any]:
        """GET that unwraps a ``{"items": [...]}`` envelope when present."""
        result = self.get(path, params=params)
        if isinstance(result, dict) and "items" in result:
            items = result["items"]
            return list(items) if isinstance(items, list) else []
        if isinstance(result, list):
            return result
        return []

    def upload(
        self,
        path: str,
        field_name: str,
        file: tuple[str, BinaryIO] | tuple[str, BinaryIO, str],
    ) -> Any:
        """POST a multipart/form-data file upload."""
        return self.request("POST", path, files={field_name: file})

    def download(self, path: str, params: dict[str, Any] | None = None) -> bytes:
        """GET a binary response body (e.g. document download)."""
        url = self._build_url(path)
        merged_headers = self._build_headers()
        query = {k: str(v) for k, v in (params or {}).items() if v is not None}
        try:
            response = self._client.get(url, params=query or None, headers=merged_headers)
        except httpx.TimeoutException as exc:
            raise NavaiaForgeError(0, f"Request timed out: {exc}") from exc
        except httpx.RequestError as exc:
            raise NavaiaForgeError(0, f"Network error: {exc}") from exc

        if not response.is_success:
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                detail = response.text or response.reason_phrase
            raise error_from_status(response.status_code, str(detail))
        return response.content
