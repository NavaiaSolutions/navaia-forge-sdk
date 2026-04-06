"""
NavaiaForge Python SDK — programmatic access to the NavaiaForge platform.

Usage:
    from navaia_forge import NavaiaForgeClient

    client = NavaiaForgeClient(base_url="http://localhost:8000", api_key="your-key")
    workforces = client.workforces.list()
"""

from navaia_forge.client import NavaiaForgeClient, NavaiaForgeError

__version__ = "0.1.0"
__all__ = ["NavaiaForgeClient", "NavaiaForgeError"]
