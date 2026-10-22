"""Guardas aplicadas al mensaje del usuario antes de llamar al LLM.

El paquete no importa la capa de modelos ni de base de datos: son funciones
puras sobre texto para poder testearlas sin levantar el servidor.
"""

from .answers import canned_audio_filename, canned_text
from .code_detect import detect_code
from .gibberish import detect_gibberish
from .language import UnsupportedLanguage, detect_unsupported_language
from .normalize import normalize, stable_hash
from .service import (
    Verdict,
    check,
    decorate_user_message,
    find_previous_answer,
    guards_enabled,
    is_reusable,
    reuse_enabled,
)

__all__ = [
    "Verdict",
    "UnsupportedLanguage",
    "canned_audio_filename",
    "canned_text",
    "check",
    "decorate_user_message",
    "detect_code",
    "detect_gibberish",
    "detect_unsupported_language",
    "find_previous_answer",
    "guards_enabled",
    "is_reusable",
    "normalize",
    "reuse_enabled",
    "stable_hash",
]
