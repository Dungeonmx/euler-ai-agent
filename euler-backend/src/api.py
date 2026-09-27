from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from models.message import Message

load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from models.agent import Agent
from models.chatRequest import ChatRequest
from models.logger import logger
from models.tts import generate_audio_filename, synthesize_text

SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT")
REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATED_AUDIO_DIR = REPO_ROOT / "audios" / "generated"

app = FastAPI(title="Euler AI Agent API", version="1.0.0")
agent = Agent()

@app.middleware("http")
async def log_requests(request: Request, call_next):
    client_host = request.client.host if request.client else "unknown"
    logger.info(f"{request.method} {request.url.path} from {client_host}")
    response = await call_next(request)
    logger.info(f"{request.method} {request.url.path} -> {response.status_code}")
    return response

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    messages = _process_request(request)
    return StreamingResponse(agent.event_generator(messages), media_type="text/event-stream")

@app.post("/chat")
async def chat(request: ChatRequest):

    messages = _process_request(request)

    try:
        result = agent.invoke(messages)
    except Exception as e:
        logger.error(f"Error en agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    output_messages = result["messages"]
    assistant_response = output_messages[-1].content
    logger.debug(f"Respuesta generada: {assistant_response}")

    print(f"[RESPONSE] {assistant_response}", flush=True)

    all_messages = list(request.messages) + [
        Message(role="assistant", content=assistant_response)
    ]

    response_format = os.environ.get("TTS_RESPONSE_FORMAT", "wav")
    audio_filename = generate_audio_filename(response_format)
    output_path = GENERATED_AUDIO_DIR / audio_filename

    import asyncio

    async def run_tts():
        try:
            synthesize_text(assistant_response, output_path)
        except Exception as e:
            logger.error(f"Error en TTS: {e}")

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

def _process_request(request: ChatRequest):
    messages = [SystemMessage(content=SYSTEM_PROMPT)]
    for msg in request.messages:
        if msg.role in ("user", "human"):
            messages.append(HumanMessage(content=msg.content))
            logger.debug(f"Consulta del usuario: {msg.content}")
        elif msg.role == "assistant":
            messages.append(AIMessage(content=msg.content))

    return messages
