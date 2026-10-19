"""Acceso a la base pública de la facultad (MariaDB, solo lectura).

Expone el motor, la fábrica de sesiones y los modelos ORM usados por las tools
(`get_recent_news`, `get_carreras`).
"""

from .base import Base
from .models import Carrera, Contenido
from .session import (
    CHATBOT_PUBLIC_URL,
    SessionLocal,
    engine,
    get_chatbot_public_session,
)

__all__ = [
    "Base",
    "Carrera",
    "Contenido",
    "CHATBOT_PUBLIC_URL",
    "SessionLocal",
    "engine",
    "get_chatbot_public_session",
]
