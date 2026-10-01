from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent

from tts import synthesize_text, generate_audio_filename
from tools import get_recent_news

load_dotenv()

SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT")
REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATED_AUDIO_DIR = REPO_ROOT / "audios" / "generated"

app = FastAPI(title="Euler AI Agent API", version="1.0.0")

# El widget se sirve desde otro origen que la API (por ejemplo, la pagina de
# la facultad en www.ing.unlpam.edu.ar). Sin esto el navegador bloquea el fetch
# antes de que llegue al servidor. En desarrollo no se nota, porque el proxy
# de vite.config.js hace que ambos vivan en el mismo origen.
#
# En produccion hay que restringir CORS_ORIGINS a los dominios reales, en vez
# de dejar el "*" por defecto de .env.example.
cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "*").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    # El widget no usa cookies ni credenciales, asi que puede quedar en False.
    # Ademas, allow_credentials=True esta prohibido combinarlo con
    # allow_origins=["*"].
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

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


class ChatResponse(BaseModel):
    messages: list[Message]
    audio_url: str


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, background_tasks: BackgroundTasks):
    from langchain_core.messages import HumanMessage, SystemMessage

    messages = [SystemMessage(content=SYSTEM_PROMPT)]
    for msg in request.messages:
        if msg.role in ("user", "human"):
            messages.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            from langchain_core.messages import AIMessage
            messages.append(AIMessage(content=msg.content))

    result = agent_executor.invoke({"messages": messages})

    output_messages = result["messages"]
    assistant_response = output_messages[-1].content

    all_messages = list(request.messages) + [
        Message(role="assistant", content=assistant_response)
    ]

    response_format = os.environ.get("TTS_RESPONSE_FORMAT", "wav")
    audio_filename = generate_audio_filename(response_format)
    output_path = GENERATED_AUDIO_DIR / audio_filename
    background_tasks.add_task(synthesize_text, assistant_response, output_path)

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
