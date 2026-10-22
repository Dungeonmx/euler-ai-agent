"""Normalización de texto para comparar preguntas.

Dos preguntas se consideran la misma si, después de normalizarlas, producen el
mismo hash. La normalización ignora mayúsculas, tildes, signos de puntuación y
espacios de más, así que ``"¿Cuándo es el examen?"`` y ``"cuando es el examen"``
colisionan a propósito.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

_WHITESPACE = re.compile(r"\s+")
# Todo lo que no sea letra, dígito o espacio se descarta (puntuación, emojis,
# símbolos). El guion bajo también se descarta: ``\w`` lo incluye.
_NON_WORD = re.compile(r"[^\w\s]|_", re.UNICODE)

HASH_LENGTH = 32


def normalize(text: str | None) -> str:
    """Devuelve una versión canónica del texto para comparar."""
    if not text:
        return ""

    # NFKD separa los diacríticos de su letra base; luego se descartan.
    decomposed = unicodedata.normalize("NFKD", text)
    without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))

    lowered = without_marks.casefold()
    cleaned = _NON_WORD.sub(" ", lowered)
    return _WHITESPACE.sub(" ", cleaned).strip()


def stable_hash(text: str | None) -> str:
    """Hash corto y estable de la pregunta normalizada."""
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()[:HASH_LENGTH]
