"""Template resource."""

from __future__ import annotations

from ..types import Template, Workforce
from ._base import ResourceBase, parse_list, parse_model


class TemplatesResource(ResourceBase):
    """Operations for workforce templates."""

    def list(self) -> list[Template]:
        """List available workforce templates."""
        return parse_list(Template, self._http.get_list("/templates"))

    def get(self, template_id: str) -> Template:
        """Fetch a template by id."""
        return parse_model(Template, self._http.get(f"/templates/{template_id}"))

    def instantiate(self, template_id: str, name: str) -> Workforce:
        """Instantiate a template into a new workforce."""
        return parse_model(
            Workforce,
            self._http.post(
                f"/templates/{template_id}/instantiate",
                {"name": name},
            ),
        )
