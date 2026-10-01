"""
tools.py — DEPRECADO

Este módulo se mantiene por compatibilidad.
Las tools han sido movidas a `models/tools/`.

Importá directamente desde `models.tools`:
    from models.tools import get_recent_news
"""

from models.tools import get_recent_news  # noqa: F401

__all__ = ["get_recent_news"]
