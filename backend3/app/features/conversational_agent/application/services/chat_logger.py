import logging
from uuid import UUID

from app.features.conversational_agent.domain.chat_log import (
    ANONYMOUS_USER,
    ChatLogEntry,
    ChatLogRepository,
)

logger = logging.getLogger(__name__)


class ChatLogger:
    """Auditoría y memoria conversacional; sus fallos nunca afectan a la respuesta."""

    def __init__(self, repository: ChatLogRepository) -> None:
        self._repository = repository

    def log_interaction(
        self,
        *,
        conversation_id: UUID,
        prompt: str,
        reply: str | None,
        model_used: str | None = None,
        prompt_tokens: int | None = None,
        response_tokens: int | None = None,
        total_tokens: int | None = None,
        user: str | None = ANONYMOUS_USER,
        client_ip: str | None = None,
    ) -> bool:
        entry = ChatLogEntry(
            user=user,
            model_used=model_used,
            prompt=prompt,
            reply=reply,
            prompt_tokens=prompt_tokens,
            response_tokens=response_tokens,
            total_tokens=total_tokens,
            client_ip=client_ip,
            conversation_id=conversation_id,
        )
        try:
            self._repository.add(entry)
        except Exception:
            logger.warning("No se pudo guardar el registro en chat_logs", exc_info=True)
            return False
        return True

    def get_history(self, conversation_id: UUID, limit: int | None = None) -> list[ChatLogEntry]:
        try:
            entries = self._repository.list_by_conversation(conversation_id, limit)
        except Exception:
            logger.warning("No se pudo cargar el historial de chat_logs", exc_info=True)
            return []
        return [entry for entry in entries if entry.reply]
