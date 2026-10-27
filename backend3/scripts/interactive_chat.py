"""Chat interactivo por consola con el agente WaveCore.

Ejecutar desde backend3/ con PYTHONPATH apuntando a backend3/:
    PowerShell: $env:PYTHONPATH = (Get-Location).Path; python scripts/interactive_chat.py
    Bash:       PYTHONPATH=. python scripts/interactive_chat.py
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from uuid import UUID, uuid4

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings  # noqa: E402
from app.features.conversational_agent.application.agent import (  # noqa: E402
    ConversationalAgent,
)
from app.features.conversational_agent.application.services.chat_logger import (  # noqa: E402
    ChatLogger,
)
from app.features.conversational_agent.domain.chat_log import AgentResult  # noqa: E402
from app.features.conversational_agent.infrastructure.llm.gemini import (  # noqa: E402
    TransientFallbackMiddleware,
    build_agent_model,
    build_fallback_model,
)
from app.features.conversational_agent.infrastructure.mcp.client import (  # noqa: E402
    McpClient,
)
from app.features.conversational_agent.infrastructure.mcp.langchain_tools import (  # noqa: E402
    load_mcp_tools,
)
from app.features.conversational_agent.infrastructure.persistence.chat_logs import (  # noqa: E402
    SupabaseChatLogRepository,
)

EXIT_COMMANDS = {"exit", "quit", "salir"}


def print_trace(result: AgentResult, max_result_chars: int) -> None:
    for call in result.tool_calls:
        output = call.result or ""
        if len(output) > max_result_chars:
            output = output[:max_result_chars] + f"... [{len(call.result or '')} caracteres]"
        print(f"\n[herramienta] {call.name}")
        print(f"  argumentos: {json.dumps(call.arguments, ensure_ascii=False)}")
        print(f"  resultado:  {output}")
    print(f"\nAgente: {result.reply}\n")


async def chat(conversation_id: UUID, max_result_chars: int, debug: bool) -> None:
    settings = get_settings()
    errlog = sys.stderr if debug else open(os.devnull, "w")
    async with McpClient(errlog=errlog) as mcp_client:
        tools = await load_mcp_tools(mcp_client)
        agent = ConversationalAgent(
            model=build_agent_model(),
            tools=tools,
            chat_logger=ChatLogger(SupabaseChatLogRepository()),
            middleware=[TransientFallbackMiddleware(build_fallback_model())],
            history_turns=settings.CHAT_HISTORY_TURNS,
            default_model_name=settings.GEMINI_AGENT_MODEL,
        )
        print(f"Conversación: {conversation_id}")
        print(f"Herramientas MCP: {', '.join(tool.name for tool in tools)}")
        print("Escribe tu pregunta ('exit' para salir).\n")

        while True:
            try:
                prompt = (await asyncio.to_thread(input, "Tú: ")).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not prompt:
                continue
            if prompt.lower() in EXIT_COMMANDS:
                break
            try:
                result = await agent.ask(prompt, conversation_id)
            except Exception as exc:
                print(f"\nError al consultar al agente: {exc}\n")
                continue
            print_trace(result, max_result_chars)


def main() -> None:
    parser = argparse.ArgumentParser(description="Chat interactivo con el agente WaveCore")
    parser.add_argument("--conversation-id", type=UUID, default=None)
    parser.add_argument("--max-result-chars", type=int, default=600)
    parser.add_argument("--debug", action="store_true", help="Muestra stderr del servidor MCP")
    args = parser.parse_args()

    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    try:
        asyncio.run(chat(args.conversation_id or uuid4(), args.max_result_chars, args.debug))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
