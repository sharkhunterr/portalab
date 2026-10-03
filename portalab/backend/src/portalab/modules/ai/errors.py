"""AI problem codes (contracts): ``ai.unavailable``, ``ai.rate_limited``, ``ai.budget_exceeded``,
``ai.action_expired``, ``ai.tool_forbidden``."""

from portalab.core.errors import Conflict, Forbidden, NotFound, PortalError, Unavailable


class AiUnavailable(Unavailable):
    default_code = "ai.unavailable"
    default_title = "The assistant is unavailable"


class AiRateLimited(PortalError):
    status = 429
    default_code = "ai.rate_limited"
    default_title = "Too many messages"


class AiBudgetExceeded(PortalError):
    status = 429
    default_code = "ai.budget_exceeded"
    default_title = "Daily assistant budget reached"


class ActionExpired(Conflict):
    default_code = "ai.action_expired"
    default_title = "This action is no longer pending"


class ToolForbidden(Forbidden):
    default_code = "ai.tool_forbidden"
    default_title = "This tool is not available"


class ConversationNotFound(NotFound):
    default_code = "ai.conversation_not_found"
    default_title = "Conversation not found"


class ActionNotFound(NotFound):
    default_code = "ai.action_not_found"
    default_title = "Action not found"
