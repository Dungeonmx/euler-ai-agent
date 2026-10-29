from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from storage.postgresql.base import Base


class DatosEntrenamiento(Base):
    """Documento de entrenamiento cargado por la facultad."""

    __tablename__ = "datos_entrenamiento"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    titulo: Mapped[str] = mapped_column(String(500))
    contenido: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    def __repr__(self) -> str:
        return f"<DatosEntrenamiento(id={self.id}, titulo={self.titulo!r})>"
