"""Optional framework integrations for the NavaiaForge SDK.

Each integration sub-package depends on its target framework as an optional
extra. Importing this package does **not** import any third-party framework
— sub-packages must be imported explicitly so the SDK stays usable when the
extras are not installed.

Available integrations:

- :mod:`navaia_forge.integrations.langgraph` — bring an existing
  ``langgraph.graph.CompiledGraph`` into Forge as a workforce, with
  observability and backend access wired in.
"""

__all__: list[str] = []
