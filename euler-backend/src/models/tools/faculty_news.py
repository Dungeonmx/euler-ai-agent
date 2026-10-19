"""Tool de novedades de la Facultad de Ingeniería (UNLPam).

Lee la tabla ``contenido`` de la base pública de la facultad (MariaDB) usando la
conexión compartida de ``storage.chatbot_public``. Todas las operaciones son de
lectura (``SELECT``); nunca se modifica la base de datos.
"""

from __future__ import annotations

from langchain.tools import tool
from pydantic import Field
from sqlalchemy import select

from models.logger import logger
from storage.chatbot_public import Contenido, get_chatbot_public_session


def fetch_faculty_news(n: int = 5) -> list[Contenido]:
    """Obtiene las novedades más recientes de la tabla ``contenido``."""
    with get_chatbot_public_session() as session:
        result = session.execute(
            select(Contenido)
            .order_by(Contenido.fecha_publicacion.desc())
            .limit(n)
        )
        return list(result.scalars().all())


@tool
def get_recent_news(
    cantidad: int = Field(default=5, description="Número de novedades a obtener, entre 1 y 10"),
) -> str:
    """Obtén las últimas novedades de la Facultad de Ingeniería de la UNLPam.
    Esta herramienta consulta la base de datos de la facultad y devuelve las últimas
    noticias y comunicados publicados, ordenadas por fecha de publicación. Úsala cuando
    el usuario pregunte sobre novedades, noticias, eventos, cursos, convocatorias,
    llamados, ofertas laborales, becas, o cualquier información reciente de la facultad.
    El argumento 'cantidad' determina cuántas novedades devolver (máximo 10)."""
    cantidad = max(1, min(cantidad, 10))
    news = fetch_faculty_news(n=cantidad)

    logger.debug(
        f"Tool get_recent_news | Params: cantidad={cantidad} | Respuesta: {len(news)} novedades obtenidas"
    )

    if not news:
        return "No se pudieron obtener novedades en este momento. Por favor, intentá más tarde."

    partes = []
    for i, item in enumerate(news, 1):
        lineas = [f"Novedad {i}: {item.titulo}"]
        if item.categoria:
            lineas.append(f"Categoría: {item.categoria}")
        if item.fecha_publicacion:
            lineas.append(f"Fecha: {item.fecha_publicacion.strftime('%Y-%m-%d %H:%M')}")
        if item.resumen:
            lineas.append(f"Resumen: {item.resumen}")
        if item.url:
            lineas.append(f"URL: {item.url}")
        partes.append("\n".join(lineas))

    return "\n\n".join(partes)
