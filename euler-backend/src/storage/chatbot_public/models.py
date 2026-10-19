"""Mapeos ORM de la base pública de la facultad (MariaDB, solo lectura).

Solo se modelan las columnas necesarias para consultar los datos. Todas las
operaciones sobre estas tablas deben ser de lectura (``SELECT``).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Carrera(Base):
    """Carrera de la Facultad de Ingeniería (tabla ``carreras``)."""

    __tablename__ = "carreras"

    carrera_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    titulo: Mapped[str] = mapped_column(String(250))
    subtitulo: Mapped[Optional[str]] = mapped_column(String(250))
    orientacion: Mapped[Optional[str]] = mapped_column(String(250))
    titulo_otorgado: Mapped[Optional[str]] = mapped_column(String(500))
    tipo_programa: Mapped[Optional[str]] = mapped_column(String(200))
    descripcion: Mapped[Optional[str]] = mapped_column(Text)
    perfil: Mapped[Optional[str]] = mapped_column(Text)
    plan_anio: Mapped[Optional[int]] = mapped_column(Integer)
    duracion: Mapped[Optional[str]] = mapped_column(String(100))
    resolucion: Mapped[Optional[str]] = mapped_column(String(250))
    plan_pdf_url: Mapped[Optional[str]] = mapped_column(String(700))
    snapshot_at: Mapped[datetime] = mapped_column(DateTime)

    def __repr__(self) -> str:
        return f"<Carrera(id={self.carrera_id}, titulo={self.titulo!r})>"


class Contenido(Base):
    """Contenido publicado por la facultad (tabla ``contenido``)."""

    __tablename__ = "contenido"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tipo: Mapped[str] = mapped_column(String(50))
    categoria: Mapped[Optional[str]] = mapped_column(String(150))
    origen: Mapped[str] = mapped_column(String(100))
    origen_id: Mapped[int] = mapped_column(Integer)
    titulo: Mapped[str] = mapped_column(String(500))
    resumen: Mapped[Optional[str]] = mapped_column(Text)
    contenido: Mapped[Optional[str]] = mapped_column(Text)
    fecha_publicacion: Mapped[Optional[datetime]] = mapped_column(DateTime)
    destinatario: Mapped[Optional[str]] = mapped_column(String(50))
    url: Mapped[Optional[str]] = mapped_column(String(700))
    archivo_url: Mapped[Optional[str]] = mapped_column(String(700))
    snapshot_at: Mapped[datetime] = mapped_column(DateTime)

    def __repr__(self) -> str:
        return f"<Contenido(id={self.id}, titulo={self.titulo!r})>"
