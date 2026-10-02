from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from models.message import Message

load_dotenv()

import asyncio
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from models.agent import Agent
from models.chatRequest import ChatRequest
from models.conversation import Conversation
from models.logger import logger
from models.tts import generate_audio_filename, synthesize_text
from repositories.conversation import ConversationRepository
from schemas.conversation import ChatResponse, ConversationList, ConversationRead
from storage.postgresql.session import async_session

SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT")
REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATED_AUDIO_DIR = REPO_ROOT / "audios" / "generated"
FRONTEND_DIST_DIR = REPO_ROOT / "euler-frontend" / "dist"
FRONTEND_DIST_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Euler AI Agent API", version="1.0.0")

app.mount("/euler/js", StaticFiles(directory=str(FRONTEND_DIST_DIR)), name="euler_js")

agent = Agent()

CONVERSATION_TTL = int(os.getenv("CONVERSATION_TTL_SECONDS", "3600"))
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

@app.middleware("http")
async def log_requests(request: Request, call_next):
    client_host = request.client.host if request.client else "unknown"
    logger.info(f"{request.method} {request.url.path} from {client_host}")
    response = await call_next(request)
    logger.info(f"{request.method} {request.url.path} -> {response.status_code}")
    return response


async def get_conversation_repo():
    session = async_session()
    try:
        repo = ConversationRepository(session, ttl_seconds=CONVERSATION_TTL)
        return repo, session
    except Exception:
        await session.close()
        raise


def _process_request(request: ChatRequest):
    messages = [SystemMessage(content=SYSTEM_PROMPT)]
    for msg in request.messages:
        if msg.role in ("user", "human"):
            messages.append(HumanMessage(content=msg.content))
            logger.debug(f"Consulta del usuario: {msg.content}")
        elif msg.role == "assistant":
            messages.append(AIMessage(content=msg.content))

    return messages


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    repo, session = await get_conversation_repo()
    try:
        conversation_id = request.conversation_id
        user_message = request.messages[-1].model_dump() if request.messages else None

        if conversation_id:
            conversation = await repo.append_user_message(conversation_id, user_message)
            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")
            await session.commit()
        else:
            conversation = await repo.create_conversation([m.model_dump() for m in request.messages])
            conversation_id = conversation.id
            await session.commit()

        messages = _process_request(request)

        event_queue: asyncio.Queue = asyncio.Queue()
        agent_done = asyncio.Event()
        full_text = ""
        audio_filename = None

        async def agent_worker():
            """Ejecuta el agente en segundo plano, emite eventos al queue y recolecta datos."""
            nonlocal full_text, audio_filename
            try:
                await event_queue.put(f"event: conversation_id\ndata: {conversation_id}\n\n")
                async for event_type, event_data, event_raw in agent.event_generator(messages, conversation_id):
                    await event_queue.put(event_raw)
                    if event_type == "text":
                        full_text += event_data
                    elif event_type == "audio":
                        audio_filename = event_data.strip()
            except asyncio.CancelledError:
                logger.info("Agent worker cancelled")
            except Exception as e:
                logger.error(f"Error en agent worker: {e}")
            finally:
                agent_done.set()

        async def commit_after_agent():
            """Commit despues de que el agente termina (independiente del streaming)."""
            await agent_done.wait()
            if full_text:
                try:
                    await repo.update_with_response(conversation_id, {
                        "role": "assistant",
                        "content": full_text,
                        "audio": f"/audio/{audio_filename}"
                    })
                    await session.commit()
                except Exception as e:
                    logger.error(f"Error committing response: {e}")
                finally:
                    await session.close()

        # Lanzar tareas en background
        asyncio.create_task(agent_worker())
        asyncio.create_task(commit_after_agent())

        async def event_stream():
            """Stream de eventos desde el queue hasta que el agente termina."""
            while not agent_done.is_set():
                try:
                    event = await asyncio.wait_for(event_queue.get(), timeout=0.5)
                    yield event
                except asyncio.TimeoutError:
                    continue
            # Drain eventos restantes
            while True:
                try:
                    event = event_queue.get_nowait()
                    yield event
                except asyncio.QueueEmpty:
                    break

        return StreamingResponse(event_stream(), media_type="text/event-stream")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en stream: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    repo, session = await get_conversation_repo()
    try:
        conversation_id = request.conversation_id
        user_message = request.messages[-1].model_dump() if request.messages else None

        if conversation_id:
            conversation = await repo.append_user_message(conversation_id, user_message)
            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")
            await session.commit()
        else:
            conversation = await repo.create_conversation([m.model_dump() for m in request.messages])
            conversation_id = conversation.id
            await session.commit()

        messages = _process_request(request)

        try:
            result = agent.invoke(messages, conversation_id)
        except Exception as e:
            logger.error(f"Error en agent: {e}")
            raise HTTPException(status_code=500, detail=str(e))

        output_messages = result["messages"]
        assistant_response = output_messages[-1].content
        logger.debug(f"Respuesta generada: {assistant_response}")

        print(f"[RESPONSE] {assistant_response}", flush=True)

        response_format = os.environ.get("TTS_RESPONSE_FORMAT", "wav")
        audio_filename = generate_audio_filename(response_format)
        output_path = GENERATED_AUDIO_DIR / audio_filename

        assistant_msg = {"role": "assistant", "content": assistant_response, "audio": f"/audio/{audio_filename}"}
        await repo.update_with_response(conversation_id, assistant_msg)
        try:
            await session.commit()
        except Exception as e:
            logger.error(f"Error al commit de la respuesta: {e}")
            await session.rollback()
            raise HTTPException(status_code=500, detail="Error al guardar la respuesta en la base de datos")

        async def run_tts():
            try:
                synthesize_text(assistant_response, output_path)
            except Exception as e:
                logger.error(f"Error en TTS: {e}")

        asyncio.create_task(run_tts())

        all_messages = list(request.messages) + [Message(role="assistant", content=assistant_response)]

        return ChatResponse(
            messages=[m.model_dump() for m in all_messages],
            audio_url=f"/audio/{audio_filename}",
            conversation_id=conversation_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await session.close()


@app.get("/conversations", response_model=ConversationList)
async def list_conversations(page: int = 1, per_page: int = 20):
    repo, session = await get_conversation_repo()
    try:
        conversations = await repo.list_active(page=page, per_page=per_page)
        return conversations
    except Exception as e:
        logger.error(f"Error listando conversaciones: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await session.close()


@app.get("/conversations/{conversation_id}", response_model=ConversationRead)
async def get_conversation(conversation_id: int):
    repo, session = await get_conversation_repo()
    try:
        conversation = await repo.get_by_id(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return conversation
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo conversacion: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await session.close()


@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: int):
    repo, session = await get_conversation_repo()
    try:
        deleted = await repo.delete(conversation_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Conversation not found")
        await session.commit()
        return {"detail": "Conversation deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error eliminando conversacion: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await session.close()


@app.delete("/conversations")
async def delete_all_conversations():
    repo, session = await get_conversation_repo()
    try:
        count = await repo.delete_all()
        await session.commit()
        return {"detail": f"Deleted {count} conversations"}
    except Exception as e:
        logger.error(f"Error eliminando todas las conversaciones: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await session.close()


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
