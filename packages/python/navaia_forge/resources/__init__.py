"""Resource namespaces for the NavaiaForge SDK."""

from .agents import AgentsResource
from .conversations import ConversationsResource
from .integrations import IntegrationsResource
from .knowledge import KnowledgeResource
from .observability import ObservabilityResource
from .tasks import TasksResource
from .templates import TemplatesResource
from .workforces import WorkforcesResource

__all__ = [
    "AgentsResource",
    "ConversationsResource",
    "IntegrationsResource",
    "KnowledgeResource",
    "ObservabilityResource",
    "TasksResource",
    "TemplatesResource",
    "WorkforcesResource",
]
