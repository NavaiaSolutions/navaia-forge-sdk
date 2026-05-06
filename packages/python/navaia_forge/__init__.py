"""NavaiaForge Python SDK.

Public surface::

    from navaia_forge import NavaiaForgeClient
    from navaia_forge import Workforce, Agent, Task, Edge   # typed models
    from navaia_forge import NavaiaForgeError, NotFoundError  # exceptions
    from navaia_forge import NavaiaForgeWs                   # real-time WS client

Quickstart::

    client = NavaiaForgeClient(base_url="http://localhost:8000", api_key="nf_...")
    workforces = client.workforces.list()
    task = client.tasks.create(workforce_id=workforces[0].id, title="Review PR")
    final = client.tasks.wait_for_completion(task.id)
"""

from .client import NavaiaForgeClient
from .errors import (
    AuthenticationError,
    NavaiaForgeError,
    NotFoundError,
    PermissionError,
    RateLimitError,
    ServerError,
    TimeoutError,
    ValidationError,
)
from .http import HttpClient, HttpConfig
from .types import (
    Agent,
    AgentConfig,
    AgentCreate,
    AgentUpdate,
    AgentVariable,
    Conversation,
    Edge,
    Integration,
    KnowledgeBase,
    KnowledgeDocument,
    Message,
    MetricsSummary,
    PaginatedResponse,
    Task,
    TaskCreate,
    TaskLog,
    Template,
    TokenUsage,
    ToolCall,
    Workforce,
    WorkforceCreate,
    WorkforceFull,
    WorkforceUpdate,
    WsAgentStatusEvent,
    WsChatEvent,
    WsEvent,
    WsSystemEvent,
    WsTaskEvent,
)
from .websocket import NavaiaForgeWs

__version__ = "0.2.0"

__all__ = [
    "Agent",
    "AgentConfig",
    "AgentCreate",
    "AgentUpdate",
    "AgentVariable",
    "AuthenticationError",
    "Conversation",
    "Edge",
    "HttpClient",
    "HttpConfig",
    "Integration",
    "KnowledgeBase",
    "KnowledgeDocument",
    "Message",
    "MetricsSummary",
    "NavaiaForgeClient",
    "NavaiaForgeError",
    "NavaiaForgeWs",
    "NotFoundError",
    "PaginatedResponse",
    "PermissionError",
    "RateLimitError",
    "ServerError",
    "Task",
    "TaskCreate",
    "TaskLog",
    "Template",
    "TimeoutError",
    "TokenUsage",
    "ToolCall",
    "ValidationError",
    "Workforce",
    "WorkforceCreate",
    "WorkforceFull",
    "WorkforceUpdate",
    "WsAgentStatusEvent",
    "WsChatEvent",
    "WsEvent",
    "WsSystemEvent",
    "WsTaskEvent",
]
