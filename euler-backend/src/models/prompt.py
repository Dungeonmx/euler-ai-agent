"""Construcción del payload de mensajes que recibe el LLM.

A partir del historial guardado en Postgres (fuente de verdad) se arma una
secuencia válida para el motor de inferencia:

- solo roles ``user``/``assistant`` (el resto de la metadata se descarta),
- sin turnos consecutivos del mismo rol (vLLM rechaza historiales que no
  alternan, y un turno fallido deja dos preguntas seguidas),
- system prompt controlado por ``LLM_SYSTEM_MODE``: como mensaje ``system``
  (Qwen/llama.cpp) o dentro del primer mensaje del usuario (Gemma, que no
  soporta el rol ``system``).

No hay checkpointer: el historial lo aporta la base en cada request, así que la
conversación sobrevive a reinicios y las respuestas de guarda también entran en
el contexto.
"""

from __future__ import annotations

import os
from typing import Iterable, Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

SystemMode = Literal["system", "first_user"]

_USER_ROLES = frozenset({"user", "human"})
_ASSISTANT_ROLES = frozenset({"assistant", "ai"})


def build_llm_messages(
    history: Iterable[dict] | None,
    *,
    system_prompt: str | None = None,
    mode: str | None = None,
    max_turns: int | None = None,
) -> list[BaseMessage]:
    """Devuelve los mensajes listos para el agente.

    ``history`` es ``conversation.messages["messages"]``: incluye el mensaje
    actual del usuario como último elemento.
    """
    if system_prompt is None:
        system_prompt = os.getenv("SYSTEM_PROMPT") or ""
    if mode is None:
        mode = os.getenv("LLM_SYSTEM_MODE", "system")
    if max_turns is None:
        max_turns = _env_int("LLM_HISTORY_MAX_TURNS", 0)

    messages = _sanitize(history or [])
    messages = _apply_window(messages, max_turns)

    if not messages:
        # Sin historial no hay nada que preguntar; el endpoint ya valida que
        # haya al menos un mensaje, así que este caso es defensivo.
        return []

    system_prompt = system_prompt.strip()
    if not system_prompt:
        return messages

    if str(mode).strip().lower() == "first_user":
        first = messages[0]
        messages[0] = HumanMessage(
            content=f"{system_prompt}\n\n{first.content}",
            additional_kwargs=first.additional_kwargs,
        )
        return messages

    return [SystemMessage(content=system_prompt), *messages]


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _sanitize(history: Iterable[dict]) -> list[BaseMessage]:
    """Normaliza roles y garantiza la alternancia user/assistant."""
    messages: list[BaseMessage] = []

    for item in history:
        if not isinstance(item, dict):
            continue

        role = str(item.get("role", "")).strip().lower()
        content = item.get("content")
        if not isinstance(content, str) or not content.strip():
            continue

        if role in _USER_ROLES:
            _append_user(messages, content)
        elif role in _ASSISTANT_ROLES:
            _append_assistant(messages, content)

    # Un historial no puede empezar con una respuesta del asistente.
    while messages and isinstance(messages[0], AIMessage):
        messages.pop(0)

    return messages


def _append_user(messages: list[BaseMessage], content: str) -> None:
    if messages and isinstance(messages[-1], HumanMessage):
        # Dos preguntas seguidas: pasó un turno que falló sin guardar respuesta.
        messages[-1] = HumanMessage(content=f"{messages[-1].content}\n\n{content}")
        return
    messages.append(HumanMessage(content=content))


def _append_assistant(messages: list[BaseMessage], content: str) -> None:
    if messages and isinstance(messages[-1], AIMessage):
        # Solo interesa la última respuesta; las anteriores no aportan y
        # romperían la alternancia.
        messages[-1] = AIMessage(content=content)
        return
    if not messages:
        # Respuesta huérfana al principio del historial: se descarta.
        return
    messages.append(AIMessage(content=content))


def _apply_window(messages: list[BaseMessage], max_turns: int) -> list[BaseMessage]:
    """Conserva los últimos ``max_turns`` turnos de usuario. ``0`` = sin límite."""
    if max_turns <= 0 or not messages:
        return messages

    user_indexes = [
        index for index, message in enumerate(messages) if isinstance(message, HumanMessage)
    ]
    if len(user_indexes) <= max_turns:
        return messages

    # Cortar en el inicio del turno N-ésimo desde el final mantiene la
    # alternancia y deja siempre la pregunta actual.
    return messages[user_indexes[-max_turns]:]
