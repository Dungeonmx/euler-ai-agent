from __future__ import annotations

import asyncio
import os
import json
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.utils.uuid import uuid7
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import BaseModel, SecretStr
from tools import get_recent_news
from tts import generate_audio_filename, synthesize_text

load_dotenv()

SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT")
REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATED_AUDIO_DIR = REPO_ROOT / "audios" / "generated"

app = FastAPI(title="Euler AI Agent API", version="1.0.0")

llm = ChatOpenAI(
    model = str(os.getenv("LLM_MODEL")),
    temperature = float(str(os.getenv("LLM_TEMPERATURE"))),
    base_url = str(os.getenv("LLM_BASE_URL")),
    api_key = SecretStr(str(os.getenv("LLM_API_KEY"))),
    default_headers = {"User-Agent": "python-httpx/0.28.1"},
)

tools = [get_recent_news]

agent_executor = create_agent(
    llm,
    tools=tools,
    system_prompt=SYSTEM_PROMPT,
    checkpointer=InMemorySaver(),
)


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    messages = [SystemMessage(content=SYSTEM_PROMPT)]

    for msg in request.messages:
        if msg.role == "user":
            messages.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            messages.append(AIMessage(content=msg.content))

    async def event_generator():
        full_text = ""

        config = {"configurable": {"thread_id": str(uuid7())}}

        try:
            async for chunk in agent_executor.astream(
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
                                        yield f"event: tool_call\ndata: {json.dumps({'tool_name': tc['name'], 'input': tc['args']})}\n\n"
                        elif source == "tools":
                            for msg in update.get("messages", []):
                                if hasattr(msg, "content") and msg.content:
                                    yield f"event: tool_output\ndata: {msg.content}\n\n"

            audio_filename = generate_audio_filename("wav")
            output_path = GENERATED_AUDIO_DIR / audio_filename
            synthesize_text(full_text, output_path)

            audio_url = f"/audio/{audio_filename}"
            yield f"event: audio\ndata: {audio_url}\n\n"

            yield "event: done\ndata: \n\n"

        except asyncio.CancelledError:
            raise

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/chat")
async def chat(request: ChatRequest):
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

    messages = [SystemMessage(content=SYSTEM_PROMPT)]
    for msg in request.messages:
        if msg.role in ("user", "human"):
            messages.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            messages.append(AIMessage(content=msg.content))

    result = agent_executor.invoke({"messages": messages})

    output_messages = result["messages"]
    assistant_response = output_messages[-1].content

    print(f"[RESPONSE] {assistant_response}", flush=True)

    all_messages = list(request.messages) + [
        Message(role="assistant", content=assistant_response)
    ]

    response_format = os.environ.get("TTS_RESPONSE_FORMAT", "wav")
    audio_filename = generate_audio_filename(response_format)
    output_path = GENERATED_AUDIO_DIR / audio_filename

    import asyncio

    async def run_tts():
        synthesize_text(assistant_response, output_path)

    asyncio.create_task(run_tts())

    return {
        "messages": [m.model_dump() for m in all_messages],
        "audio_url": f"/audio/{audio_filename}",
    }


@app.get("/audio/{filename}")
async def get_audio(filename: str):
    file_path = GENERATED_AUDIO_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")
    return FileResponse(
        path=str(file_path),
        media_type="audio/wav",
        filename=filename,
    )
