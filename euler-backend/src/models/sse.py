"""Serialización de eventos SSE compartida por los caminos del agente y de guardas."""

from __future__ import annotations


def sse_event(event: str, data: object = "") -> str:
    """Serializa un evento SSE preservando los saltos de línea.

    En SSE, cada línea de un mismo evento va prefijada con ``data: `` y el
    cliente las vuelve a unir con ``\\n``. Sin esto, un token que contiene un
    salto de línea corta el evento y el resto del texto se pierde.
    """
    lines = str(data).split("\n")
    payload = "\n".join(f"data: {line}" for line in lines)
    return f"event: {event}\n{payload}\n\n"
