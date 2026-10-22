"""Preparación de un turno de chat: persistencia, guardas y respuesta sin LLM.

Lo usan tanto ``/chat`` como ``/chat/stream`` para que las dos rutas apliquen
exactamente las mismas reglas antes de llegar al agente.
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass

from guards import (
    Verdict,
    canned_audio_filename,
    canned_text,
    check,
    decorate_user_message,
)
from models.chatRequest import ChatRequest
from models.logger import logger
from models.sse import sse_event
from models.tts import GENERATED_AUDIO_DIR, generate_audio_filename, synthesize_text
from repositories.conversation import ConversationRepository
from sqlalchemy.ext.asyncio import AsyncSession

CANNED_AUDIO_DIR = GENERATED_AUDIO_DIR / "canned"

_canned_locks: dict[str, asyncio.Lock] = {}


class ConversationNotFound(Exception):
    """El ``conversation_id`` enviado por el cliente no existe."""


@dataclass
class PreparedTurn:
    conversation_id: int
    verdict: Verdict
    # Historial completo (incluye el mensaje actual). Es la fuente de verdad
    # para armar el payload del LLM: no hay checkpointer.
    history: list[dict]

    @property
    def is_answer(self) -> bool:
        return self.verdict.action == "answer"


def _env_flag(name: str, default: bool = True) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("true", "1", "yes", "on")


def response_format() -> str:
    return os.environ.get("TTS_RESPONSE_FORMAT", "wav")


def audio_timeout() -> float:
    try:
        return float(os.environ.get("GUARD_AUDIO_TIMEOUT", "25"))
    except ValueError:
        return 25.0


async def _bounded(awaitable):
    """Espera la generación de audio como máximo ``GUARD_AUDIO_TIMEOUT`` segundos.

    Si se agota, se responde sin audio. El hilo de ``requests`` sigue hasta
    terminar y deja el archivo en disco; para los audios fijos eso significa
    que el siguiente rechazo ya lo encuentra.
    """
    try:
        return await asyncio.wait_for(awaitable, timeout=audio_timeout())
    except asyncio.TimeoutError:
        logger.warning("Timeout generando audio; se responde sin audio")
        return None


async def prewarm_canned_audio() -> None:
    """Genera en background los audios de rechazo para que el primero sea rápido.

    No bloquea el arranque: se lanza como tarea desde el lifespan. Si el TTS no
    está disponible se corta en el primer fallo, sin reintentar los demás.
    """
    for reason in ("language", "code", "gibberish"):
        try:
            if await _ensure_canned_audio(reason) is None:
                return
        except Exception as error:  # pragma: no cover - defensivo
            logger.error(f"No se pudo pre-generar el audio de rechazo {reason}: {error}")
            return


async def prepare_turn(
    request: ChatRequest,
    repo: ConversationRepository,
    session: AsyncSession,
) -> PreparedTurn:
    """Crea o actualiza la conversación y evalúa las guardas sobre el último mensaje.

    El mensaje del usuario se guarda antes de decidir, igual que antes; el
    lookup de preguntas repetidas excluye ese último elemento para no
    compararse consigo mismo.
    """
    if not request.messages:
        raise ValueError("El pedido no contiene mensajes")

    last_message = decorate_user_message(request.messages[-1].model_dump())
    logger.debug(f"Consulta del usuario: {last_message.get('content')}")

    if request.conversation_id:
        conversation = await repo.append_user_message(
            request.conversation_id, last_message
        )
        if not conversation:
            raise ConversationNotFound(request.conversation_id)
        await session.commit()
    else:
        history = [decorate_user_message(m.model_dump()) for m in request.messages]
        conversation = await repo.create_conversation(history)
        await session.commit()

    stored = (conversation.messages or {}).get("messages", [])
    # ``stored[:-1]`` es el historial previo: el último elemento es la consulta
    # que estamos evaluando.
    verdict = check(last_message.get("content"), stored[:-1])

    _log_verdict(conversation.id, verdict, last_message.get("content"))
    return PreparedTurn(conversation_id=conversation.id, verdict=verdict, history=stored)


def _log_verdict(conversation_id: int, verdict: Verdict, text: str | None) -> None:
    if verdict.reason == "duplicate":
        logger.info(
            f"Respuesta reutilizada | conv={conversation_id} | hash={verdict.question_hash}"
        )
    elif verdict.reason == "language":
        logger.warning(
            f"Rechazo por idioma | conv={conversation_id} | detectado={verdict.detail} | "
            f"texto={text!r}"
        )
    elif verdict.reason == "code":
        logger.warning(
            f"Rechazo por codigo | conv={conversation_id} | patron={verdict.detail} | "
            f"texto={text!r}"
        )
    elif verdict.reason == "gibberish":
        logger.warning(
            f"Rechazo por incomprensible | conv={conversation_id} | motivo={verdict.detail} | "
            f"texto={text!r}"
        )


async def resolve_answer(verdict: Verdict) -> dict:
    """Convierte el veredicto en el mensaje del asistente listo para persistir.

    Para preguntas repetidas reutiliza el audio original si sigue en disco; si
    fue purgado, regenera solo el audio. Nunca llama al LLM.

    La generación de audio está acotada por ``GUARD_AUDIO_TIMEOUT``: el widget
    corta a los 50 s, así que preferimos responder sin audio antes que dejar al
    usuario esperando. Los audios fijos se pre-generan al arrancar
    (``prewarm_canned_audio``), por lo que en la práctica no se espera nada.
    """
    text = verdict.text or ""

    if verdict.source == "cache":
        filename = None
        if _env_flag("GUARD_REUSE_AUDIO", True) and verdict.audio_filename:
            candidate = GENERATED_AUDIO_DIR / verdict.audio_filename
            if candidate.is_file():
                filename = verdict.audio_filename
        if filename is None:
            filename = await _bounded(_synthesize(text))

        return assistant_message(
            text,
            filename,
            source="cache",
            cacheable=True,
            reason="duplicate",
        )

    filename = await _bounded(_ensure_canned_audio(verdict.reason or "gibberish"))
    return assistant_message(
        text,
        filename,
        source="guard",
        cacheable=False,
        reason=verdict.reason,
    )


def assistant_message(
    content: str,
    audio_filename: str | None,
    *,
    source: str,
    cacheable: bool,
    reason: str | None = None,
) -> dict:
    """Construye el mensaje del asistente con su metadata de procedencia."""
    message: dict = {
        "role": "assistant",
        "content": content,
        "source": source,
        "cacheable": cacheable,
    }
    if audio_filename:
        message["audio"] = f"/audio/{audio_filename}"
    # ``guard_reason`` marca rechazos; una respuesta cacheada no es un rechazo y
    # debe poder reutilizarse otra vez.
    if reason and source == "guard":
        message["guard_reason"] = reason
    return message


async def persist_answer(
    repo: ConversationRepository,
    session: AsyncSession,
    conversation_id: int,
    message: dict,
) -> None:
    await repo.update_with_response(conversation_id, message)
    await session.commit()


def stream_answer(conversation_id: int, message: dict):
    """Generador SSE que emite una respuesta ya resuelta (cache o guarda).

    Mantiene el mismo contrato que el camino del agente: ``final_text`` para el
    texto, ``audio`` para reproducir y ``done`` para cerrar.
    """

    async def generator():
        yield sse_event("conversation_id", conversation_id)
        yield sse_event("final_text", message.get("content", ""))
        yield sse_event(
            "guard",
            json.dumps(
                {
                    "source": message.get("source"),
                    "reason": message.get("guard_reason") or "duplicate",
                }
            ),
        )
        audio = message.get("audio")
        if audio:
            yield sse_event("audio", audio)
        yield sse_event("done")

    return generator()


async def _synthesize(text: str) -> str | None:
    """Genera un audio nuevo para un texto y devuelve el nombre del archivo."""
    if not text.strip():
        return None

    filename = generate_audio_filename(response_format())
    output_path = GENERATED_AUDIO_DIR / filename
    try:
        GENERATED_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(synthesize_text, text, output_path)
    except Exception as error:  # el texto sigue siendo válido sin audio
        logger.error(f"Error en TTS: {error}")
        return None
    return filename


async def _ensure_canned_audio(reason: str) -> str | None:
    """Devuelve el audio fijo de un rechazo, generándolo la primera vez.

    Se genera de forma perezosa para no bloquear el arranque si el servicio de
    TTS todavía no está disponible.
    """
    if not _env_flag("GUARD_CANNED_AUDIO", True):
        return None

    filename = canned_audio_filename(reason, response_format())
    path = CANNED_AUDIO_DIR / filename
    if path.is_file():
        return filename

    lock = _canned_locks.setdefault(filename, asyncio.Lock())
    async with lock:
        if path.is_file():
            return filename
        try:
            CANNED_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(synthesize_text, canned_text(reason), path)
        except Exception as error:
            logger.error(f"Error generando audio de rechazo ({reason}): {error}")
            return None

    return filename
