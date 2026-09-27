import asyncio
import json
import os
from pathlib import Path

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.utils.uuid import uuid7
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import SecretStr
from tools import get_recent_news

from .logger import logger
from .tts import generate_audio_filename, synthesize_text

SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT")
REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATED_AUDIO_DIR = REPO_ROOT / ".." / "audios" / "generated"

class Agent:

    def __init__(self) -> None:

        self.llm = ChatOpenAI(
            model = str(os.getenv("LLM_MODEL")),
            temperature = float(str(os.getenv("LLM_TEMPERATURE"))),
            base_url = str(os.getenv("LLM_BASE_URL")),
            api_key = SecretStr(str(os.getenv("LLM_API_KEY"))),
            default_headers = {"User-Agent": "python-httpx/0.28.1"},
        )

        self.tools = [get_recent_news]

        self.agent_executor = create_agent(
            self.llm,
            tools=self.tools,
            system_prompt=SYSTEM_PROMPT,
            checkpointer=InMemorySaver(),
        )

    async def event_generator(self, messages: list[SystemMessage]):
        full_text = ""

        config = {"configurable": {"thread_id": str(uuid7())}}

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
                    if hasattr(token, "content") and token.content:
                        full_text += token.content
                        yield f"event: text\ndata: {token.content}\n\n"

                elif chunk["type"] == "updates":
                    for source, update in chunk["data"].items():
                        if source == "model":
                            for msg in update.get("messages", []):
                                if hasattr(msg, "tool_calls") and msg.tool_calls:
                                    for tc in msg.tool_calls:
                                        logger.debug(f"Tool usada: {tc['name']} | Params: {json.dumps(tc['args'])}")
                                        yield f"event: tool_call\ndata: {json.dumps({'tool_name': tc['name'], 'input': tc['args']})}\n\n"
                        elif source == "tools":
                            for msg in update.get("messages", []):
                                if hasattr(msg, "content") and msg.content:
                                    logger.debug(f"Respuesta de tool {msg.content[:200]}")
                                    yield f"event: tool_output\ndata: {msg.content}\n\n"

            logger.debug(f"Respuesta generada: {full_text}")

            audio_filename = generate_audio_filename("wav")
            output_path = GENERATED_AUDIO_DIR / audio_filename
            try:
                synthesize_text(full_text, output_path)
            except Exception as e:
                logger.error(f"Error en TTS: {e}")
                yield f"event: error\ndata: {json.dumps({'detail': 'Error generating audio'})}\n\n"
                yield "event: done\ndata: \n\n"
                return

            audio_url = f"/audio/{audio_filename}"
            yield f"event: audio\ndata: {audio_url}\n\n"

            yield "event: done\ndata: \n\n"

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Error en agent: {e}")
            yield f"event: error\ndata: {json.dumps({'detail': str(e)})}\n\n"
            yield "event: done\ndata: \n\n"

    def invoke(self, messages: list[SystemMessage]):
        return self.agent_executor.invoke({"messages": messages})
