from __future__ import annotations

import mimetypes
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from models.message import Message

load_dotenv()

import asyncio

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from models.agent import Agent
from models.chatRequest import ChatRequest
from models.logger import logger
from models.prompt import build_llm_messages
from models.sse import sse_event
from models.tts import generate_audio_filename, synthesize_text
from repositories.conversation import ConversationRepository
from schemas.conversation import ChatResponse, ConversationList, ConversationRead
from services.chat import (
    ConversationNotFound,
    assistant_message,
    persist_answer,
    prepare_turn,
    prewarm_canned_audio,
    resolve_answer,
    stream_answer,
)
from storage.postgresql.session import async_session

REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATED_AUDIO_DIR = REPO_ROOT / "audios" / "generated"

# Directorio con el build del widget que se sirve en /euler/js. Por defecto
# apunta al dist del frontend (carpeta hermana de euler-backend/). En produccion
# se puede sobreescribir con FRONTEND_DIST_DIR.
DEFAULT_FRONTEND_DIST_DIR = REPO_ROOT.parent / "euler-frontend" / "dist"
FRONTEND_DIST_DIR = Path(
    os.getenv("FRONTEND_DIST_DIR", str(DEFAULT_FRONTEND_DIST_DIR))
).expanduser().resolve()

WIDGET_REQUIRED_FILES = ("iniciar.js", "euler-chat.js")


def _check_frontend_dist() -> None:
    """Valida el directorio del widget antes de montarlo.

    StaticFiles exige que el directorio exista al inicializar, asi que si falta
    se crea vacio. Si no estan los archivos clave del snippet se avisa por log,
    para que el 404 de /euler/js no sea un fallo silencioso.
    """
    if not FRONTEND_DIST_DIR.is_dir():
        logger.warning(
            f"No existe el directorio del widget ({FRONTEND_DIST_DIR}); se crea vacio. "
            f"/euler/js devolvera 404."
        )
        FRONTEND_DIST_DIR.mkdir(parents=True, exist_ok=True)

    faltantes = [f for f in WIDGET_REQUIRED_FILES if not (FRONTEND_DIST_DIR / f).is_file()]
    if faltantes:
        logger.warning(
            f"Widget incompleto en {FRONTEND_DIST_DIR}: faltan {faltantes}. "
            f"/euler/js devolvera 404. Construi el frontend (bun/npm run build) "
            f"o defini FRONTEND_DIST_DIR."
        )


_check_frontend_dist()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Pre-generar los audios de rechazo deja el primer rechazo en milisegundos.
    # Se lanza como tarea para no bloquear el arranque si el TTS está caído.
    asyncio.create_task(prewarm_canned_audio())
    yield


app = FastAPI(title="Euler AI Agent API", version="1.0.0", lifespan=lifespan)

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


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    repo, session = await get_conversation_repo()

    # Si el turno llega al agente, la sesión pasa a `commit_after_agent`. Cualquier
    # salida anterior (rechazo, caché, error) tiene que cerrarla acá.
    session_handed_off = False

    try:
        try:
            turn = await prepare_turn(request, repo, session)
        except ConversationNotFound:
            raise HTTPException(status_code=404, detail="Conversation not found")

        conversation_id = turn.conversation_id

        if turn.is_answer:
            message = await resolve_answer(turn.verdict)
            await persist_answer(repo, session, conversation_id, message)
            logger.info(
                f"Respuesta sin LLM ({turn.verdict.reason}) | conv={conversation_id}"
            )
            return StreamingResponse(
                stream_answer(conversation_id, message),
                media_type="text/event-stream",
            )

        messages = build_llm_messages(turn.history)

        event_queue: asyncio.Queue = asyncio.Queue()
        agent_done = asyncio.Event()
        full_text = ""
        audio_filename = None
        had_llm_error = False

        async def agent_worker():
            """Ejecuta el agente en segundo plano, emite eventos al queue y recolecta datos."""
            nonlocal full_text, audio_filename, had_llm_error
            try:
                await event_queue.put(sse_event("conversation_id", conversation_id))
                async for event_type, event_data, event_raw in agent.event_generator(messages, conversation_id):
                    await event_queue.put(event_raw)
                    if event_type == "text":
                        full_text += event_data
                    elif event_type == "final_text":
                        # El mensaje final del LLM tiene los espacios correctos.
                        full_text = event_data
                    elif event_type == "audio":
                        # event_data es "/audio/x.wav"; guardamos solo el nombre
                        # para no duplicar el prefijo al persistir.
                        audio_filename = str(event_data).strip().rsplit("/", 1)[-1]
                    elif event_type == "error":
                        # Falla del LLM o de conexión: la respuesta no se reutiliza.
                        had_llm_error = True
            except asyncio.CancelledError:
                logger.info("Agent worker cancelled")
            except Exception as e:
                logger.error(f"Error en agent worker: {e}")
                had_llm_error = True
            finally:
                agent_done.set()

        async def commit_after_agent():
            """Commit despues de que el agente termina (independiente del streaming)."""
            await agent_done.wait()
            try:
                if full_text:
                    message = assistant_message(
                        full_text,
                        audio_filename,
                        source="llm",
                        cacheable=not had_llm_error,
                    )
                    await repo.update_with_response(conversation_id, message)
                    await session.commit()
            except Exception as e:
                logger.error(f"Error committing response: {e}")
            finally:
                # Se cierra siempre, incluso si no hubo texto que guardar.
                await session.close()

        # Lanzar tareas en background
        asyncio.create_task(agent_worker())
        asyncio.create_task(commit_after_agent())
        session_handed_off = True

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
    finally:
        if not session_handed_off:
            await session.close()


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    repo, session = await get_conversation_repo()
    try:
        try:
            turn = await prepare_turn(request, repo, session)
        except ConversationNotFound:
            raise HTTPException(status_code=404, detail="Conversation not found")

        conversation_id = turn.conversation_id

        if turn.is_answer:
            message = await resolve_answer(turn.verdict)
            await persist_answer(repo, session, conversation_id, message)
            logger.info(
                f"Respuesta sin LLM ({turn.verdict.reason}) | conv={conversation_id}"
            )
            all_messages = list(request.messages) + [
                Message(role="assistant", content=message["content"])
            ]
            return ChatResponse(
                messages=[m.model_dump() for m in all_messages],
                audio_url=message.get("audio", ""),
                conversation_id=conversation_id,
            )

        messages = build_llm_messages(turn.history)

        try:
            # invoke es sincrono y puede tardar; no bloquear el event loop.
            result = await asyncio.to_thread(agent.invoke, messages, conversation_id)
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

        message = assistant_message(
            assistant_response,
            audio_filename,
            source="llm",
            cacheable=True,
        )
        try:
            await persist_answer(repo, session, conversation_id, message)
        except Exception as e:
            logger.error(f"Error al commit de la respuesta: {e}")
            await session.rollback()
            raise HTTPException(status_code=500, detail="Error al guardar la respuesta en la base de datos")

        async def run_tts():
            try:
                await asyncio.to_thread(synthesize_text, assistant_response, output_path)
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
    # Path(...).name descarta cualquier intento de salir del directorio.
    safe_name = Path(filename).name
    file_path = GENERATED_AUDIO_DIR / safe_name
    if not safe_name or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Audio file not found")
    media_type = mimetypes.guess_type(safe_name)[0] or "audio/wav"
    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=safe_name,
    )
