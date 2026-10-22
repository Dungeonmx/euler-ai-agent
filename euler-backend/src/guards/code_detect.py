"""Detección de código, HTML, PHP y SQL en el mensaje del usuario.

Los patrones están anclados a *sintaxis*, nunca a palabras sueltas: así una
consulta legítima como «¿Se enseña PHP en la facultad?» pasa, pero
``<?php echo $x; ?>`` se rechaza.
"""

from __future__ import annotations

import re

# (motivo, patrón). El orden importa solo para el log: gana el primero que
# matchea.
_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("html_tag", re.compile(r"<\s*/?\s*[a-z][^>]{0,200}>", re.IGNORECASE)),
    ("html_entity", re.compile(r"&(?:lt|gt|amp|quot|nbsp|#\d+);", re.IGNORECASE)),
    ("html_script", re.compile(r"<\s*(?:script|iframe|style|svg|form)\b", re.IGNORECASE)),
    ("markdown_code", re.compile(r"```")),
    ("php_open", re.compile(r"<\?php|<\?=", re.IGNORECASE)),
    (
        "php_superglobal",
        re.compile(r"\$_(?:GET|POST|REQUEST|SERVER|COOKIE|SESSION|FILES)\b", re.IGNORECASE),
    ),
    ("js_function", re.compile(r"\bfunction\s*\w*\s*\(", re.IGNORECASE)),
    ("js_arrow", re.compile(r"\w\s*=>")),
    (
        "js_dom",
        re.compile(
            r"\b(?:document|window|localStorage|sessionStorage|navigator)\.",
            re.IGNORECASE,
        ),
    ),
    ("js_declaration", re.compile(r"\b(?:var|let|const)\s+[A-Za-z_$]", re.IGNORECASE)),
    ("js_console", re.compile(r"\bconsole\.\w+\s*\(", re.IGNORECASE)),
    ("js_eval", re.compile(r"\b(?:eval|alert|prompt)\s*\(", re.IGNORECASE)),
    ("js_jquery", re.compile(r"\$\(|jQuery\s*\(")),
    ("sql_union", re.compile(r"\bunion\s+select\b", re.IGNORECASE)),
    ("sql_injection", re.compile(r"'\s*(?:or|and)\s+['\d]", re.IGNORECASE)),
    ("sql_drop", re.compile(r"\bdrop\s+(?:table|database)\b", re.IGNORECASE)),
)


def detect_code(text: str | None) -> str | None:
    """Devuelve el motivo del rechazo, o ``None`` si el texto es lenguaje natural."""
    if not text:
        return None

    for reason, pattern in _PATTERNS:
        if pattern.search(text):
            return reason
    return None
