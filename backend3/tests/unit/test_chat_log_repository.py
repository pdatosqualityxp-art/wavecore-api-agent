from uuid import UUID

from app.features.conversational_agent.domain.chat_log import ChatLogEntry
from app.features.conversational_agent.infrastructure.persistence import chat_logs


class FakeSupabaseTable:
    def __init__(self) -> None:
        self.payload: dict[str, object] | None = None

    def insert(self, payload: dict[str, object]) -> "FakeSupabaseTable":
        self.payload = payload
        return self

    def execute(self) -> None:
        return None


class FakeSupabaseClient:
    def __init__(self) -> None:
        self.table_name: str | None = None
        self.table_adapter = FakeSupabaseTable()

    def table(self, name: str) -> FakeSupabaseTable:
        self.table_name = name
        return self.table_adapter


def test_repository_inserts_audit_payload_into_chat_logs(monkeypatch) -> None:
    client = FakeSupabaseClient()
    monkeypatch.setattr(chat_logs, "get_supabase_client", lambda: client)
    conversation_id = UUID("96735614-e4dd-4da5-8e91-899893483250")
    entry = ChatLogEntry(
        conversation_id=conversation_id,
        prompt="¿Cuánto vendimos?",
        reply="Vendimos 100.",
        model_used="gemini-test",
        prompt_tokens=12,
        response_tokens=5,
        total_tokens=17,
        client_ip="192.0.2.10",
    )

    chat_logs.SupabaseChatLogRepository().add(entry)

    assert client.table_name == "chat_logs"
    assert client.table_adapter.payload == {
        "api": "3 agent av",
        "user": "anonymous",
        "model_used": "gemini-test",
        "prompt": "¿Cuánto vendimos?",
        "reply": "Vendimos 100.",
        "prompt_tokens": 12,
        "response_tokens": 5,
        "total_tokens": 17,
        "client_ip": "192.0.2.10",
        "conversation_id": str(conversation_id),
    }
