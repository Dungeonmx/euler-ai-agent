"""Respuestas fijas de rechazo.

Cada motivo tiene su versión en español y en inglés. Se envían siempre las dos,
porque no sabemos qué idioma entiende quien escribió en portugués, ruso o chino.
"""

from __future__ import annotations

import hashlib

CANNED_ANSWERS: dict[str, dict[str, str]] = {
    "language": {
        "es": (
            "Perdón, solo puedo responder consultas en español o inglés. "
            "¿Me repetís la pregunta en alguno de esos dos idiomas?"
        ),
        "en": (
            "Sorry, I can only answer questions in Spanish or English. "
            "Could you ask me again in one of those languages?"
        ),
    },
    "code": {
        "es": (
            "No puedo procesar código, etiquetas HTML ni instrucciones de "
            "programación. ¿Me contás tu consulta con tus propias palabras?"
        ),
        "en": (
            "I can't process code, HTML tags, or programming instructions. "
            "Could you tell me your question in your own words?"
        ),
    },
    "gibberish": {
        "es": "No logré entender tu mensaje. ¿Me lo escribís de nuevo con otras palabras?",
        "en": "I couldn't understand your message. Could you write it again in different words?",
    },
}

# Motivos internos de código/incomprensible que comparten la respuesta visible.
_REASON_TO_CANNED = {
    "language": "language",
    "code": "code",
    "gibberish": "gibberish",
}


def canned_text(reason: str) -> str:
    """Texto bilingüe para un motivo de rechazo."""
    key = _REASON_TO_CANNED.get(reason, "gibberish")
    pair = CANNED_ANSWERS[key]
    return f"{pair['es']}\n\n{pair['en']}"


def canned_reason(reason: str) -> str:
    """Normaliza el motivo interno (``html_tag``, ``teclado``...) a una categoría."""
    return _REASON_TO_CANNED.get(reason, "gibberish")


def canned_audio_filename(reason: str, response_format: str = "wav") -> str:
    """Nombre estable del audio pre-generado de un rechazo."""
    return f"canned_{canned_reason(reason)}.{response_format}"


def canned_text_hash(reason: str) -> str:
    """Hash del texto fijo, para reconocer rechazos guardados sin metadata."""
    return hashlib.sha256(canned_text(reason).encode("utf-8")).hexdigest()


def is_canned_text(text: str | None) -> bool:
    """True si el texto es una de nuestras respuestas fijas."""
    if not text:
        return False
    candidate = hashlib.sha256(text.strip().encode("utf-8")).hexdigest()
    return any(candidate == canned_text_hash(reason) for reason in CANNED_ANSWERS)
