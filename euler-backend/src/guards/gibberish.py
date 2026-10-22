"""Detección de texto incomprensible (basura, mojibake, base64, teclado mash).

La detección es deliberadamente conservadora: se necesitan al menos
``MIN_LETTERS`` letras para juzgar, y los mensajes con acentos, eñes, emojis o
URLs no se penalizan. Un falso rechazo es peor que dejar pasar algo dudoso.
"""

from __future__ import annotations

import os
import re
import unicodedata

MIN_LETTERS = 3

_URL = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+", re.UNICODE)
_TOKEN_SPLIT = re.compile(r"\s+")
_LETTER_RUN = re.compile(r"([^\W\d_])\1{5,}", re.UNICODE)
# Mojibake típico de UTF-8 leído como Latin-1/CP1252.
_MOJIBAKE = re.compile(r"Ã[\x80-\xBF]|Â[\x80-\xBF]|ï¿½|â€|\ufffd")
# Secuencias contiguas de teclado. No aparecen en palabras españolas ni inglesas.
_KEYBOARD_MASH = (
    "asdf",
    "sdfg",
    "dfgh",
    "fghj",
    "ghjk",
    "qwer",
    "wert",
    "erty",
    "rtyu",
    "tyui",
    "yuio",
    "uiop",
    "zxcv",
    "xcvb",
    "cvbn",
    "vbnm",
)
_VOWELS = frozenset("aeiou")


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def detect_gibberish(text: str | None) -> str | None:
    """Devuelve el motivo del rechazo, o ``None`` si el texto parece razonable."""
    if not text:
        return None

    body = _EMAIL.sub(" ", _URL.sub(" ", text)).strip()

    letters = [ch for ch in body if ch.isalpha()]
    if len(letters) < MIN_LETTERS:
        # Sin letras no hay idioma que analizar: se dejan pasar los emojis y los
        # mensajes cortos ("ok", "3"), pero una pared de símbolos se rechaza.
        if len(letters) == 0 and _is_symbol_wall(body):
            return "simbolos"
        return None

    if _MOJIBAKE.search(body):
        return "mojibake"

    lowered = body.casefold()
    if any(fragment in lowered for fragment in _KEYBOARD_MASH):
        return "teclado"

    # Ratio de símbolos: se excluyen espacios y signos propios del español.
    if len(body) >= 10:
        symbol_count = sum(
            1
            for ch in body
            if not ch.isalnum() and not ch.isspace() and ch not in "¿¡«»\"'.,;:-()!?"
        )
        if symbol_count / len(body) > _env_float("GUARD_SYMBOL_RATIO_MAX", 0.5):
            return "simbolos"

    if _LETTER_RUN.search(body):
        return "repeticion"

    max_consonants = _env_int("GUARD_MAX_CONSECUTIVE_CONSONANTS", 5)
    if _consonant_run_length(body) > max_consonants:
        return "consonantes"

    if len(letters) >= 10:
        vowels = sum(1 for ch in _strip_accents(lowered) if ch in _VOWELS)
        if vowels / len(letters) < _env_float("GUARD_VOWEL_RATIO_MIN", 0.15):
            return "sin_vocales"

    max_token = _env_int("GUARD_MAX_TOKEN_LEN", 25)
    if any(len(token) > max_token for token in _TOKEN_SPLIT.split(body)):
        return "token_largo"

    return None


def _consonant_run_length(text: str) -> int:
    """Longitud de la racha de consonantes más larga del texto."""
    longest = current = 0
    for ch in _strip_accents(text).casefold():
        if ch.isalpha() and ch not in _VOWELS:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def _is_symbol_wall(text: str) -> bool:
    """True para una seguidilla de signos, pero no para emojis sueltos.

    ``"#$%&/()=?"`` se rechaza; ``"🎉🎉🎉"`` no, porque los emojis son parte del
    lenguaje cotidiano del chat.
    """
    visible = [ch for ch in text if not ch.isspace()]
    if len(visible) < 5:
        return False
    emojis = [ch for ch in visible if unicodedata.category(ch) == "So"]
    return len(emojis) * 2 < len(visible)
