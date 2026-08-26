from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from langchain_openai import ChatOpenAI

from tts import synthesize_text

load_dotenv()

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


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]


class ChatResponse(BaseModel):
    messages: list[Message]
    audio_url: str


@app.on_event("startup")
async def startup_event():
    GENERATED_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    from tts import get_tts_runtime
    get_tts_runtime()


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    langchain_messages = [(msg.role, msg.content) for msg in request.messages]

    result = llm.invoke(input=langchain_messages)
    assistant_response = result.content

    all_messages = list(request.messages) + [
        Message(role="assistant", content=assistant_response)
    ]

    tts_result = synthesize_text(assistant_response)
    audio_filename = tts_result["filename"]

    return ChatResponse(
        messages=all_messages,
        audio_url=f"/audio/{audio_filename}",
    )


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
