"""Orquestación de las guardas previas al LLM.

``check()`` recibe el texto del último mensaje y el historial de la conversación
(sin incluir el mensaje actual) y devuelve un ``Verdict``: o se deja pasar al
agente, o se responde sin LLM.

Orden de evaluación:

1. pregunta repetida en esta conversación (lo más barato, y un hit garantiza
   que el mensaje ya pasó todas las demás guardas),
2. código / HTML / PHP / SQL,
3. texto incomprensible,
4. idioma distinto de español o inglés.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from .answers import canned_text, is_canned_text
from .code_detect import detect_code
from .gibberish import detect_gibberish
from .language import detect_unsupported_language
from .normalize import stable_hash

Action = Literal["allow", "answer"]

# Respuestas de falla conocidas del frontend (ver ChatWidget.jsx). Se usan solo
# como fallback para filas viejas sin metadata ``cacheable``.
_ERROR_SNIPPETS = (
    "no pude conectarme",
    "algo falló de mi lado",
    "estoy tardando demasiado",
    "error al conectar con el servidor",
    "error generating audio",
)


@dataclass(frozen=True)
class Verdict:
    action: Action
    source: str | None = None  # "cache" | "guard"
    reason: str | None = None  # "duplicate" | "language" | "code" | "gibberish"
    text: str | None = None
    audio_filename: str | None = None
    question_hash: str | None = None
    detail: str | None = None


def _env_flag(name: str, default: bool = True) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("true", "1", "yes", "on")


def guards_enabled() -> bool:
    return _env_flag("GUARD_ENABLED", True)


def reuse_enabled() -> bool:
    return _env_flag("GUARD_REUSE_ANSWER", True)


def is_reusable(message: dict) -> bool:
    """Indica si una respuesta guardada se puede devolver sin llamar al LLM."""
    if not isinstance(message, dict) or message.get("role") != "assistant":
        return False

    content = (message.get("content") or "").strip()
    if not content:
        return False

    # Las respuestas de guarda nunca se reutilizan como "respuesta anterior".
    if message.get("source") == "guard" or message.get("guard_reason"):
        return False

    if "cacheable" in message:
        return bool(message["cacheable"])

    lowered = content.casefold()
    if any(snippet in lowered for snippet in _ERROR_SNIPPETS):
        return False
    if is_canned_text(content):
        return False
    return True


def find_previous_answer(messages: list[dict], text: str) -> dict | None:
    """Busca la respuesta más reciente a la misma pregunta en el historial.

    ``messages`` debe venir *sin* el mensaje actual del usuario.
    """
    if not messages:
        return None

    target = stable_hash(text)
    if not target or not (text or "").strip():
        return None

    last = len(messages) - 1
    for index in range(last, -1, -1):
        message = messages[index]
        if not isinstance(message, dict) or message.get("role") != "user":
            continue

        current = message.get("hash") or stable_hash(message.get("content", ""))
        if current != target:
            continue

        answer = messages[index + 1] if index + 1 < len(messages) else None
        if not answer or answer.get("role") != "assistant":
            continue
        if not is_reusable(answer):
            continue
        return answer

    return None


def check(text: str | None, previous_messages: list[dict] | None = None) -> Verdict:
    """Evalúa el mensaje del usuario y decide si llega al LLM."""
    question_hash = stable_hash(text)

    if not guards_enabled():
        return Verdict(action="allow", question_hash=question_hash)

    if reuse_enabled():
        previous = find_previous_answer(previous_messages or [], text or "")
        if previous is not None:
            return Verdict(
                action="answer",
                source="cache",
                reason="duplicate",
                text=previous.get("content"),
                audio_filename=_audio_filename_from(previous),
                question_hash=question_hash,
            )

    code_reason = detect_code(text)
    if code_reason:
        return Verdict(
            action="answer",
            source="guard",
            reason="code",
            text=canned_text("code"),
            question_hash=question_hash,
            detail=code_reason,
        )

    gibberish_reason = detect_gibberish(text)
    if gibberish_reason:
        return Verdict(
            action="answer",
            source="guard",
            reason="gibberish",
            text=canned_text("gibberish"),
            question_hash=question_hash,
            detail=gibberish_reason,
        )

    unsupported = detect_unsupported_language(text)
    if unsupported is not None:
        return Verdict(
            action="answer",
            source="guard",
            reason="language",
            text=canned_text("language"),
            question_hash=question_hash,
            detail=unsupported.lang,
        )

    return Verdict(action="allow", question_hash=question_hash)


def _audio_filename_from(message: dict) -> str | None:
    """Extrae el nombre del archivo desde ``/audio/x.wav`` o ``x.wav``."""
    audio = message.get("audio")
    if not isinstance(audio, str) or not audio.strip():
        return None
    return audio.rsplit("/", 1)[-1].strip() or None


def decorate_user_message(message: dict) -> dict:
    """Agrega el hash de la pregunta al mensaje antes de persistirlo."""
    decorated = dict(message)
    if decorated.get("role") in ("user", "human"):
        decorated["hash"] = stable_hash(decorated.get("content", ""))
    return decorated
