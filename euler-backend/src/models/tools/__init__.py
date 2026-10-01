"""
models/tools — Colección de LangChain tools disponibles para el agente Euler.

Cada módulo dentro de este paquete define una tool independiente.
Para agregar una nueva tool, creá un archivo .py en este directorio
y exportala desde este __init__.py.
"""

from .faculty_news import get_recent_news

__all__ = [
    "get_recent_news",
]
