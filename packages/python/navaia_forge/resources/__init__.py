"""Resource namespaces for the NavaiaForge SDK."""

from .agents import AgentsResource
from .auth import AuthResource
from .conversations import ConversationsResource
from .integrations import IntegrationsResource
from .knowledge import KnowledgeResource
from .marketplace import MarketplaceResource
from .observability import ObservabilityResource
from .sync import SyncResource
from .tasks import TasksResource
from .templates import TemplatesResource
from .workforces import WorkforcesResource

__all__ = [
    "AgentsResource",
    "AuthResource",
    "ConversationsResource",
    "IntegrationsResource",
    "KnowledgeResource",
    "MarketplaceResource",
    "ObservabilityResource",
    "SyncResource",
    "TasksResource",
    "TemplatesResource",
    "WorkforcesResource",
]
