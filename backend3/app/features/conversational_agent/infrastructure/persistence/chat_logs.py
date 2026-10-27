from uuid import UUID

from app.features.conversational_agent.domain.chat_log import (
    ChatLogEntry,
    ChatLogRepository,
)
from app.features.conversational_agent.infrastructure.persistence.supabase import (
    get_supabase_client,
)

TABLE = "chat_logs"


class SupabaseChatLogRepository(ChatLogRepository):
    def add(self, entry: ChatLogEntry) -> None:
        payload = entry.model_dump(mode="json", exclude={"created_at"})
        get_supabase_client().table(TABLE).insert(payload).execute()

    def list_by_conversation(
        self, conversation_id: UUID, limit: int | None = None
    ) -> list[ChatLogEntry]:
        query = (
            get_supabase_client()
            .table(TABLE)
            .select("*")
            .eq("conversation_id", str(conversation_id))
            .order("created_at", desc=True)
            .order("id", desc=True)
        )
        if limit is not None:
            query = query.limit(limit)
        rows = query.execute().data
        return [ChatLogEntry.model_validate(row) for row in reversed(rows)]
