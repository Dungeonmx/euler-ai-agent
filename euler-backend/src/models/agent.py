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
from models.tools import get_carreras, get_recent_news

from .logger import logger
from .tts import generate_audio_filename, synthesize_text

SYSTEM_PROMPT_BASE = os.getenv("SYSTEM_PROMPT")

# El texto del LLM se muestra en el widget. El frontend lo escapa y lo sanea
# antes de pintarlo, pero mejor que el modelo no devuelva HTML: se lo pide
# explicitamente. Es la primera linea de defensa, no la unica.
SYSTEM_PROMPT_SUFFIX = (
    " Output plain text only: never output HTML tags, scripts, code blocks or any "
    "other markup. If the user asks for HTML or code, describe it in words instead."
)

SYSTEM_PROMPT = (
    f"{SYSTEM_PROMPT_BASE}{SYSTEM_PROMPT_SUFFIX}" if SYSTEM_PROMPT_BASE else SYSTEM_PROMPT_BASE
)

REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATED_AUDIO_DIR = REPO_ROOT / ".." / "audios" / "generated"


def _sse_event(event: str, data: object = "") -> str:
    """Serializa un evento SSE preservando los saltos de linea.

    En SSE, cada linea de un mismo evento va prefijada con ``data: `` y el
    cliente las vuelve a unir con ``\\n``. Sin esto, un token que contiene un
    salto de linea corta el evento y el resto del texto se pierde.
    """
    lines = str(data).split("\n")
    payload = "\n".join(f"data: {line}" for line in lines)
    return f"event: {event}\n{payload}\n\n"


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

        self.tools = [get_recent_news, get_carreras]

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
                        raw = _sse_event("text", token.content)
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
                                        raw = _sse_event(
                                            "tool_call",
                                            json.dumps({"tool_name": tc["name"], "input": tc["args"]}),
                                        )
                                        yield ("tool_call", tc, raw)
                        elif source == "tools":
                            for msg in update.get("messages", []):
                                if hasattr(msg, "content") and msg.content:
                                    logger.debug(f"Respuesta de tool {msg.content[:200]}")
                                    raw = _sse_event("tool_output", msg.content)
                                    yield ("tool_output", msg.content, raw)

            # Usar el texto final del LLM para TTS (tiene espacios correctos)
            # Si por alguna razón full_text_final está vacío, caer al stream
            tts_text = full_text_final if full_text_final else full_text_stream
            logger.debug(f"full_text_stream (tokens SSE): {full_text_stream!r}")
            logger.debug(f"full_text_final (mensaje LLM): {full_text_final!r}")
            logger.debug(f"Texto usado para TTS: {tts_text!r}")

            # Reemplaza en el cliente el texto acumulado por tokens. Los chunks
            # del stream pueden perder espacios; el mensaje final no.
            if tts_text:
                yield ("final_text", tts_text, _sse_event("final_text", tts_text))

            response_format = os.getenv("TTS_RESPONSE_FORMAT", "wav")
            audio_filename = generate_audio_filename(response_format)
            output_path = GENERATED_AUDIO_DIR / audio_filename
            try:
                # requests.post es sincrono: si se llamara directo bloquearia el
                # event loop y el evento final_text no llegaria hasta terminar TTS.
                await asyncio.to_thread(synthesize_text, tts_text, output_path)
            except Exception as e:
                logger.error(f"Error en TTS: {e}")
                raw = _sse_event("error", json.dumps({"detail": "Error generating audio"}))
                yield ("error", {"detail": "Error generating audio"}, raw)
                yield ("done", "", _sse_event("done"))
                return

            audio_url = f"/audio/{audio_filename}"
            yield ("audio", audio_url, _sse_event("audio", audio_url))

            yield ("done", "", _sse_event("done"))

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Error en agent: {e}")
            raw = _sse_event("error", json.dumps({"detail": str(e)}))
            yield ("error", {"detail": str(e)}, raw)
            yield ("done", "", _sse_event("done"))

    def invoke(self, messages: list[SystemMessage], conversation_id: int = None):
        config = {"configurable": {"thread_id": str(conversation_id) if conversation_id else str(uuid7())}}
        return self.agent_executor.invoke({"messages": messages}, config=config)
