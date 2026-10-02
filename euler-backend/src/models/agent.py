import asyncio
import json
import os
from pathlib import Path

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.utils.uuid import uuid7
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import SecretStr
from models.tools import get_recent_news

from .logger import logger
from .tts import generate_audio_filename, synthesize_text

SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT")
REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATED_AUDIO_DIR = REPO_ROOT / ".." / "audios" / "generated"

class Agent:

    def __init__(self) -> None:

        thinking_enabled = os.getenv("LLM_THINKING_ENABLED", "false").lower() in ("true", "1", "yes")

        self.llm = ChatOpenAI(
            model = str(os.getenv("LLM_MODEL")),
            temperature = float(str(os.getenv("LLM_TEMPERATURE"))),
            base_url = str(os.getenv("LLM_BASE_URL")),
            api_key = SecretStr(str(os.getenv("LLM_API_KEY"))),
            default_headers = {"User-Agent": "python-httpx/0.28.1"},
            model_kwargs={
                "extra_body": {
                    "chat_template_kwargs": {"enable_thinking": thinking_enabled}
                }
            }
        )

        self.tools = [get_recent_news]

        self.agent_executor = create_agent(
            self.llm,
            tools=self.tools,
            system_prompt=SYSTEM_PROMPT,
            checkpointer=InMemorySaver(),
        )

    async def event_generator(self, messages: list[SystemMessage], conversation_id: int = None):
        # full_text_stream: concatenación de tokens SSE (puede tener palabras pegadas)
        # full_text_final: texto completo del mensaje final del LLM (correcto para TTS)
        full_text_stream = ""
        full_text_final = ""

        config = {"configurable": {"thread_id": str(conversation_id) if conversation_id else str(uuid7())}}

        try:
            for msg in messages:
                if isinstance(msg, HumanMessage):
                    logger.debug(f"Consulta del usuario: {msg.content}")

            async for chunk in self.agent_executor.astream(
                {"messages": messages},
                config=config,
                stream_mode=["messages", "updates"],
                version="v2",
            ):
                if chunk["type"] == "messages":
                    token, metadata = chunk["data"]
                    # Solo emitir tokens de texto del asistente (AIMessage sin tool_calls)
                    # Ignorar ToolMessage (output de herramientas) y chunks de tool_calls
                    if (
                        isinstance(token, AIMessage)
                        and token.content
                        and not getattr(token, "tool_calls", None)
                        and not getattr(token, "tool_call_chunks", None)
                    ):
                        full_text_stream += token.content
                        raw = f"event: text\ndata: {token.content}\n\n"
                        yield ("text", token.content, raw)


                elif chunk["type"] == "updates":
                    for source, update in chunk["data"].items():
                        if source == "model":
                            for msg in update.get("messages", []):
                                # Solo capturar AIMessage finales (no ToolMessage ni AIMessage con tool_calls)
                                if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
                                    full_text_final = msg.content
                                if hasattr(msg, "tool_calls") and msg.tool_calls:
                                    for tc in msg.tool_calls:
                                        logger.debug(f"Tool usada: {tc['name']} | Params: {json.dumps(tc['args'])}")
                                        raw = f"event: tool_call\ndata: {json.dumps({'tool_name': tc['name'], 'input': tc['args']})}\n\n"
                                        yield ("tool_call", tc, raw)
                        elif source == "tools":
                            for msg in update.get("messages", []):
                                if hasattr(msg, "content") and msg.content:
                                    logger.debug(f"Respuesta de tool {msg.content[:200]}")
                                    raw = f"event: tool_output\ndata: {msg.content}\n\n"
                                    yield ("tool_output", msg.content, raw)

            # Usar el texto final del LLM para TTS (tiene espacios correctos)
            # Si por alguna razón full_text_final está vacío, caer al stream
            tts_text = full_text_final if full_text_final else full_text_stream
            logger.debug(f"full_text_stream (tokens SSE): {full_text_stream!r}")
            logger.debug(f"full_text_final (mensaje LLM): {full_text_final!r}")
            logger.debug(f"Texto usado para TTS: {tts_text!r}")

            audio_filename = generate_audio_filename("wav")
            output_path = GENERATED_AUDIO_DIR / audio_filename
            try:
                synthesize_text(tts_text, output_path)
            except Exception as e:
                logger.error(f"Error en TTS: {e}")
                raw = f"event: error\ndata: {json.dumps({'detail': 'Error generating audio'})}\n\n"
                yield ("error", {"detail": "Error generating audio"}, raw)
                yield ("done", "", "event: done\ndata: \n\n")
                return

            audio_url = f"/audio/{audio_filename}"
            yield ("audio", audio_url, f"event: audio\ndata: {audio_url}\n\n")

            yield ("done", "", "event: done\ndata: \n\n")

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Error en agent: {e}")
            raw = f"event: error\ndata: {json.dumps({'detail': str(e)})}\n\n"
            yield ("error", {"detail": str(e)}, raw)
            yield ("done", "", "event: done\ndata: \n\n")

    def invoke(self, messages: list[SystemMessage], conversation_id: int = None):
        config = {"configurable": {"thread_id": str(conversation_id) if conversation_id else str(uuid7())}}
        return self.agent_executor.invoke({"messages": messages}, config=config)
