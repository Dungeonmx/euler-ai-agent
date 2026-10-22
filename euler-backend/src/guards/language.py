"""Detección del idioma del mensaje (solo se aceptan español e inglés).

Usa ``langdetect`` con semilla fija para que el resultado sea determinista. La
política es *fail-open*: ante duda, el mensaje pasa al LLM. Un falso rechazo
molesta más que dejar pasar una pregunta rara.

Los mensajes muy cortos ("ok", "hola", "3er piso") no se evalúan: no hay señal
suficiente y ``langdetect`` devuelve cualquier cosa.
"""

from __future__ import annotations

import os
import re

from dataclasses import dataclass

try:  # pragma: no cover - depende de que la dependencia esté instalada
    from langdetect import DetectorFactory, LangDetectException, detect_langs

    # langdetect es no determinista por defecto.
    DetectorFactory.seed = 0
    _LANGDETECT_AVAILABLE = True
except ImportError:  # pragma: no cover
    _LANGDETECT_AVAILABLE = False


DEFAULT_ALLOWED = ("es", "en")

_URL = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_MENTION = re.compile(r"[@#]\w+")
_NON_LETTER = re.compile(r"[^\w\s]", re.UNICODE)
_WHITESPACE = re.compile(r"\s+")

# Marcadores que delatan español aunque langdetect dude (p. ej. con portugués).
_SPANISH_MARKERS = frozenset(
    {
        "el", "la", "los", "las", "de", "del", "que", "qué", "y", "en", "es",
        "un", "una", "por", "para", "con", "como", "cuando", "cuándo", "donde",
        "dónde", "carrera", "facultad", "ingeniería", "inscripción", "alumno",
        "materia", "cuánto", "cuántos", "hay", "soy", "quiero", "necesito",
    }
)


@dataclass(frozen=True)
class UnsupportedLanguage:
    lang: str
    probability: float


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


def allowed_languages() -> tuple[str, ...]:
    raw = os.environ.get("GUARD_ALLOWED_LANGUAGES", "es,en")
    langs = tuple(part.strip().lower() for part in raw.split(",") if part.strip())
    return langs or DEFAULT_ALLOWED


def _prepare(text: str) -> str:
    """Quita URLs, menciones y signos, que confunden al detector."""
    cleaned = _URL.sub(" ", text)
    cleaned = _MENTION.sub(" ", cleaned)
    cleaned = _NON_LETTER.sub(" ", cleaned)
    return _WHITESPACE.sub(" ", cleaned).strip()


def _looks_spanish(text: str) -> bool:
    lowered = text.casefold()
    if any(ch in lowered for ch in "ñ¿¡"):
        return True
    words = set(re.findall(r"[a-záéíóúüñ]+", lowered))
    return len(words & _SPANISH_MARKERS) >= 2


def detect_unsupported_language(text: str | None) -> UnsupportedLanguage | None:
    """Devuelve el idioma detectado si no está permitido, o ``None``."""
    if not text:
        return None

    cleaned = _prepare(text)
    min_chars = _env_int("GUARD_LANG_MIN_CHARS", 15)
    if len(cleaned) < min_chars or len(cleaned.split()) < 3:
        return None

    if not _LANGDETECT_AVAILABLE:
        return None

    try:
        results = detect_langs(cleaned)
    except LangDetectException:
        return None
    except Exception:  # pragma: no cover - langdetect puede fallar con entradas raras
        return None

    if not results:
        return None

    allowed = allowed_languages()
    accept_prob = _env_float("GUARD_LANG_MIN_PROB_ACCEPT", 0.65)
    reject_prob = _env_float("GUARD_LANG_MIN_PROB_REJECT", 0.85)

    if any(result.lang in allowed and result.prob >= accept_prob for result in results):
        return None

    top = results[0]
    if top.lang in allowed:
        # Idioma permitido pero con poca confianza: no rechazamos.
        return None

    if top.prob < reject_prob:
        return None

    if "es" in allowed and _looks_spanish(text):
        # langdetect confunde español con portugués/italiano en frases cortas.
        return None

    return UnsupportedLanguage(lang=top.lang, probability=top.prob)
