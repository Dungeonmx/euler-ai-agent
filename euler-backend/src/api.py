from __future__ import annotations

import asyncio
import base64
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent

from tts import synthesize_text, generate_audio_filename, synthesize_pcm
from tools import get_recent_news

load_dotenv()

SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT")
REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATED_AUDIO_DIR = REPO_ROOT / "audios" / "generated"

app = FastAPI(title="Euler AI Agent API", version="1.0.0")

llm = ChatOpenAI(
    model=os.getenv("LLM_MODEL"),
    temperature=float(os.getenv("LLM_TEMPERATURE")),
    base_url=os.getenv("LLM_BASE_URL"),
    api_key=os.getenv("LLM_API_KEY"),
    default_headers={"User-Agent": "python-httpx/0.28.1"},
)

tools = [get_recent_news]

agent_executor = create_agent(
    llm,
    tools=tools,
    system_prompt=SYSTEM_PROMPT,
)


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]


SENTENCE_END_PATTERNS = re.compile(r'[.!?。！？\n…]+')


async def _sync_to_async_iter(sync_iter):
    loop = asyncio.get_event_loop()
    sentinel = object()
    while True:
        chunk = await loop.run_in_executor(None, next, sync_iter, sentinel)
        if chunk is sentinel:
            break
        yield chunk


def split_sentences(text: str) -> list[str]:
    sentences = SENTENCE_END_PATTERNS.split(text)
    endings = SENTENCE_END_PATTERNS.findall(text)
    result = []
    for i, sentence in enumerate(sentences):
        if sentence.strip():
            ending = endings[i] if i < len(endings) else ""
            result.append(sentence.strip() + ending)
    return result


def find_next_sentence(text: str, start: int) -> tuple[int, str]:
    """Find the next sentence boundary starting from position `start`.
    Returns (end_position, sentence_text) or (-1, '') if no boundary found."""
    remaining = text[start:]
    match = SENTENCE_END_PATTERNS.search(remaining)
    if match:
        sentence_text = remaining[:match.end()].strip()
        return start + match.end(), sentence_text
    return -1, ""


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

    messages = [SystemMessage(content=SYSTEM_PROMPT)]
    for msg in request.messages:
        if msg.role in ("user", "human"):
            messages.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            messages.append(AIMessage(content=msg.content))

    async def event_generator():
        full_text = ""
        sentence_start = 0
        audio_events = []
        audio_lock = asyncio.Lock()
        sentence_queue: asyncio.Queue = asyncio.Queue()

        async def tts_worker():
            while True:
                sentence = await sentence_queue.get()
                audio_data = synthesize_pcm(sentence)
                if audio_data:
                    async with audio_lock:
                        audio_events.append(
                            f"event: audio\ndata: {audio_data}\n\n"
                        )
                sentence_queue.task_done()

        tts_task = asyncio.create_task(tts_worker())

        try:
            stream_iter = agent_executor.stream(
                {"messages": messages},
                stream_mode="messages",
                version="v2",
            )
            async for chunk in _sync_to_async_iter(stream_iter):
                if chunk["type"] == "messages":
                    msg, metadata = chunk["data"]
                    if hasattr(msg, "content") and msg.content:
                        full_text += msg.content

                # Check for sentence boundaries in newly added text
                end_pos, sentence_text = find_next_sentence(full_text, sentence_start)
                if end_pos != -1 and sentence_text:
                    # Send text event for this sentence
                    yield f"event: text\ndata: {sentence_text}\n\n"

                    # Queue sentence for TTS (non-blocking)
                    await sentence_queue.put(sentence_text)
                    sentence_start = end_pos

                # Periodically flush audio events from TTS
                async with audio_lock:
                    for ae in audio_events:
                        yield ae
                    audio_events.clear()

            # Wait for all TTS tasks to complete
            await sentence_queue.join()
            tts_task.cancel()

            # Final flush of remaining audio events
            async with audio_lock:
                for ae in audio_events:
                    yield ae

            # Signal end
            yield "event: done\ndata: \n\n"

        except asyncio.CancelledError:
            tts_task.cancel()
            raise

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/chat")
async def chat(request: ChatRequest):
    from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

    messages = [SystemMessage(content=SYSTEM_PROMPT)]
    for msg in request.messages:
        if msg.role in ("user", "human"):
            messages.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            messages.append(AIMessage(content=msg.content))

    result = agent_executor.invoke({"messages": messages})

    output_messages = result["messages"]
    assistant_response = output_messages[-1].content

    all_messages = list(request.messages) + [
        Message(role="assistant", content=assistant_response)
    ]

    response_format = os.environ.get("TTS_RESPONSE_FORMAT", "pcm")
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
