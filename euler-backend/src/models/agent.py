import asyncio
import json
import os
from pathlib import Path

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, BaseMessage
from langchain_openai import ChatOpenAI
from pydantic import SecretStr
from models.tools import get_carreras, get_recent_news

from .llm_debug import LLMPayloadLogger
from .logger import logger
from .sse import sse_event as _sse_event
from .tts import generate_audio_filename, synthesize_text

REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATED_AUDIO_DIR = REPO_ROOT / ".." / "audios" / "generated"


class Agent:

    def __init__(self) -> None:

        thinking_enabled = os.getenv("LLM_THINKING_ENABLED", "false").lower() in ("true", "1", "yes")

        model_kwargs = {}
        if thinking_enabled:
            # ``chat_template_kwargs`` es específico de llama.cpp / Qwen. Con
            # vLLM y Gemma no se envía para no romper la plantilla del modelo.
            model_kwargs["extra_body"] = {
                "chat_template_kwargs": {"enable_thinking": True}
            }

        self.llm = ChatOpenAI(
            model = str(os.getenv("LLM_MODEL")),
            temperature = float(str(os.getenv("LLM_TEMPERATURE"))),
            base_url = str(os.getenv("LLM_BASE_URL")),
            api_key = SecretStr(str(os.getenv("LLM_API_KEY"))),
            default_headers = {"User-Agent": "python-httpx/0.28.1"},
            model_kwargs=model_kwargs,
        )

        self.tools = [get_recent_news, get_carreras]

        # Sin checkpointer ni system_prompt: el historial y el prompt los arma
        # ``models.prompt.build_llm_messages`` a partir de Postgres. Una sola
        # fuente de verdad evita duplicados y secuencias inválidas para vLLM.
        self.agent_executor = create_agent(self.llm, tools=self.tools)

    def _config(self, conversation_id: int | None) -> dict:
        """Config con el log del payload del LLM (no hay estado persistido)."""
        return {
            "callbacks": [
                LLMPayloadLogger(
                    conversation_id=conversation_id,
                    model=getattr(self.llm, "model_name", None)
                    or getattr(self.llm, "model", None),
                    tools=[tool.name for tool in self.tools],
                )
            ],
        }

    async def event_generator(self, messages: list[BaseMessage], conversation_id: int = None):
        # full_text_stream: concatenación de tokens SSE (puede tener palabras pegadas)
        # full_text_final: texto completo del mensaje final del LLM (correcto para TTS)
        full_text_stream = ""
        full_text_final = ""

        config = self._config(conversation_id)

        try:
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
                # El texto es válido: la respuesta se puede reutilizar aunque
                # falte el audio. Por eso el tipo interno es "audio_error" y no
                # "error" (que marca un fallo del LLM).
                yield ("audio_error", {"detail": "Error generating audio"}, raw)
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

    def invoke(self, messages: list[BaseMessage], conversation_id: int = None):
        config = self._config(conversation_id)
        return self.agent_executor.invoke({"messages": messages}, config=config)
