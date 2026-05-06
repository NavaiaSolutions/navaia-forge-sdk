"""Resource namespaces for the NavaiaForge SDK."""

from .agents import AgentsResource
from .auth import AuthResource
from .conversations import ConversationsResource
from .integrations import IntegrationsResource
from .knowledge import KnowledgeResource
from .observability import ObservabilityResource
from .setup import SetupResource
from .tasks import TasksResource
from .templates import TemplatesResource
from .tools import ToolsResource
from .workforces import WorkforcesResource

__all__ = [
    "AgentsResource",
    "AuthResource",
    "ConversationsResource",
    "IntegrationsResource",
    "KnowledgeResource",
    "ObservabilityResource",
    "SetupResource",
    "TasksResource",
    "TemplatesResource",
    "ToolsResource",
    "WorkforcesResource",
]
