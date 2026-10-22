"""Log de depuración del payload que recibe el modelo.

Se engancha como callback de LangChain (``on_chat_model_start``), que es el
único punto donde se ve el mensaje *real* que recibe el modelo: ya con el
formato final (rol ``system`` o prompt embebido en el primer ``user``) y con
los mensajes que agregue el agente por su cuenta (tool calls, resultados).

Se activa con ``LOG_LLM_PAYLOAD=true`` y se emite en nivel INFO para que se vea
sin necesidad de subir ``LOG_LEVEL``. En producción conviene dejarlo apagado:
escribe la conversación completa en disco en cada llamada al modelo.
"""

from __future__ import annotations

import json
import os
from typing import Any, Sequence

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage, convert_to_openai_messages

from .logger import logger

_PREFIX = "[LLM_PAYLOAD]"


def payload_logging_enabled() -> bool:
    return os.environ.get("LOG_LLM_PAYLOAD", "false").strip().lower() in (
        "true",
        "1",
        "yes",
        "on",
    )


class LLMPayloadLogger(BaseCallbackHandler):
    """Loguea el JSON completo enviado al LLM en cada llamada."""

    def __init__(
        self,
        conversation_id: int | str | None = None,
        model: str | None = None,
        tools: Sequence[str] | None = None,
    ) -> None:
        self.conversation_id = conversation_id
        self.model = model
        self.tools = list(tools) if tools else []

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[BaseMessage]],
        **kwargs: Any,
    ) -> None:
        if not payload_logging_enabled():
            return

        payload: dict[str, Any] = {
            "conversation_id": self.conversation_id,
            "model": self.model,
            "tools": self.tools,
        }

        try:
            payload["messages"] = self._serialize(messages)
        except Exception as error:  # pragma: no cover - defensivo
            # Un error acá no debe romper la llamada al modelo.
            logger.error(f"{_PREFIX} No se pudo serializar el payload: {error}")
            payload["messages"] = [
                [
                    {"role": getattr(msg, "type", "unknown"), "content": str(msg.content)}
                    for msg in batch
                ]
                for batch in messages
            ]

        try:
            dumped = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        except (TypeError, ValueError) as error:  # pragma: no cover - defensivo
            logger.error(f"{_PREFIX} No se pudo serializar el payload: {error}")
            return

        logger.info(f"{_PREFIX} conv={self.conversation_id}\n{dumped}")

    @staticmethod
    def _serialize(messages: list[list[BaseMessage]]) -> Any:
        serialized = [convert_to_openai_messages(batch) for batch in messages]
        # El agente no usa batching: en el caso normal devolvemos la lista plana
        # para que el log se lea como el JSON de la API de OpenAI.
        if len(serialized) == 1:
            return serialized[0]
        return serialized
