from __future__ import annotations

import json
import os
from typing import Optional

import pymysql
from langchain.tools import tool
from pydantic import BaseModel, Field

from models.logger import logger


class FacultyNews(BaseModel):
    id: int = Field(description="Identificador único de la novedad en la facultad")
    title: str = Field(description="Título de la novedad o noticia")
    summary: Optional[str] = Field(default=None, description="Resumen o copete de la novedad")
    content: Optional[str] = Field(default=None, description="Contenido completo de la novedad")
    category: Optional[str] = Field(default=None, description="Categoría de la novedad")
    published_at: Optional[str] = Field(default=None, description="Fecha de publicación")
    url: Optional[str] = Field(default=None, description="URL completa para acceder a la novedad")


def _get_db_connection() -> pymysql.Connection:
    """Crea y retorna una conexión a la base de datos MariaDB."""
    return pymysql.connect(
        host=os.environ.get("MARIADB_HOST", "localhost"),
        port=int(os.environ.get("MARIADB_PORT", "3306")),
        user=os.environ.get("MARIADB_USER", "root"),
        password=os.environ.get("MARIADB_PASSWORD", ""),
        database=os.environ.get("MARIADB_DB", "euler"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10,
    )


def fetch_faculty_news(n: int = 5) -> list[FacultyNews]:
    """Obtiene las novedades más recientes de la tabla `contenido` en MariaDB."""
    conn = None
    try:
        conn = _get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    tipo,
                    categoria,
                    titulo,
                    resumen,
                    contenido,
                    fecha_publicacion,
                    url
                FROM contenido
                ORDER BY fecha_publicacion DESC
                LIMIT %s
                """,
                (n,),
            )
            rows = cursor.fetchall()

        results: list[FacultyNews] = []
        for row in rows:
            fecha = row["fecha_publicacion"]
            fecha_str = fecha.strftime("%Y-%m-%d %H:%M") if fecha else None
            results.append(
                FacultyNews(
                    id=row["id"],
                    title=row["titulo"],
                    summary=row.get("resumen"),
                    content=row.get("contenido"),
                    category=row.get("categoria"),
                    published_at=fecha_str,
                    url=row.get("url"),
                )
            )
        return results

    except pymysql.MySQLError as e:
        logger.error(f"Error al consultar la base de datos de novedades: {e}")
        return []
    finally:
        if conn:
            conn.close()


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
        lineas = [f"Novedad {i}: {item.title}"]
        if item.category:
            lineas.append(f"Categoría: {item.category}")
        if item.published_at:
            lineas.append(f"Fecha: {item.published_at}")
        if item.summary:
            lineas.append(f"Resumen: {item.summary}")
        if item.url:
            lineas.append(f"URL: {item.url}")
        partes.append("\n".join(lineas))

    return "\n\n".join(partes)
