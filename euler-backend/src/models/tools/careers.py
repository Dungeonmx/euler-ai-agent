"""Tool de consulta de carreras de la Facultad de Ingeniería (UNLPam).

Lee la tabla ``carreras`` de la base pública de la facultad (MariaDB) usando la
conexión compartida de ``storage.chatbot_public``. Todas las operaciones son de
lectura (``SELECT``); nunca se modifica la base de datos.
"""

from __future__ import annotations

from langchain.tools import tool
from pydantic import Field
from sqlalchemy import or_, select

from models.logger import logger
from storage.chatbot_public import Carrera, get_chatbot_public_session


def fetch_all_careers() -> list[Carrera]:
    """Devuelve todas las carreras ordenadas por su identificador."""
    with get_chatbot_public_session() as session:
        result = session.execute(select(Carrera).order_by(Carrera.carrera_id))
        return list(result.scalars().all())


def search_careers(term: str) -> list[Carrera]:
    """Busca carreras por nombre.

    Compara el término contra título, subtítulo, orientación y título otorgado.
    La colación ``utf8mb4_unicode_ci`` hace que la búsqueda ignore mayúsculas y
    tildes.
    """
    pattern = f"%{term.strip()}%"
    with get_chatbot_public_session() as session:
        result = session.execute(
            select(Carrera)
            .where(
                or_(
                    Carrera.titulo.like(pattern),
                    Carrera.subtitulo.like(pattern),
                    Carrera.orientacion.like(pattern),
                    Carrera.titulo_otorgado.like(pattern),
                )
            )
            .order_by(Carrera.carrera_id)
        )
        return list(result.scalars().all())


def _format_list(carreras: list[Carrera]) -> str:
    """Formatea un listado resumido de carreras."""
    if not carreras:
        return "No hay carreras registradas."

    lines = [f"Carreras de la Facultad de Ingeniería ({len(carreras)}):"]
    for carrera in carreras:
        line = f"- [{carrera.carrera_id}] {carrera.titulo}"
        if carrera.subtitulo:
            line += f" ({carrera.subtitulo})"

        detalle = []
        if carrera.tipo_programa:
            detalle.append(carrera.tipo_programa)
        if carrera.duracion:
            detalle.append(carrera.duracion)
        if carrera.plan_anio:
            detalle.append(f"plan {carrera.plan_anio}")
        if detalle:
            line += " — " + " · ".join(detalle)

        lines.append(line)

    return "\n".join(lines)


def _format_detail(carrera: Carrera) -> str:
    """Formatea la ficha completa de una carrera, omitiendo campos vacíos."""
    lines = [f"Carrera: {carrera.titulo}"]
    if carrera.subtitulo:
        lines.append(f"Subtítulo: {carrera.subtitulo}")
    if carrera.orientacion:
        lines.append(f"Orientación: {carrera.orientacion}")
    if carrera.titulo_otorgado:
        lines.append(f"Título que otorga: {carrera.titulo_otorgado}")
    if carrera.tipo_programa:
        lines.append(f"Tipo de programa: {carrera.tipo_programa}")
    if carrera.plan_anio:
        lines.append(f"Año del plan de estudios: {carrera.plan_anio}")
    if carrera.duracion:
        lines.append(f"Duración: {carrera.duracion}")
    if carrera.resolucion:
        lines.append(f"Resolución: {carrera.resolucion}")
    if carrera.descripcion:
        lines.append(f"Descripción: {carrera.descripcion.strip()}")
    if carrera.perfil:
        lines.append(f"Perfil profesional: {carrera.perfil.strip()}")
    if carrera.plan_pdf_url:
        lines.append(f"Plan de estudios (PDF): {carrera.plan_pdf_url}")
    return "\n".join(lines)


@tool
def get_carreras(
    carrera: str = Field(
        default="",
        description=(
            "Nombre o parte del nombre de la carrera sobre la que se quiere "
            "información. Dejar vacío para obtener el listado de todas las carreras."
        ),
    ),
) -> str:
    """Obtén información de las carreras de la Facultad de Ingeniería de la UNLPam.

    Esta herramienta consulta la base de datos de la facultad. Úsala cuando el
    usuario pregunte qué carreras se dictan, o sobre una carrera en particular:
    su duración, el título que otorga, el plan de estudios, el perfil profesional,
    la resolución o el link al plan de estudios.

    - Si ``carrera`` queda vacío, devuelve el listado completo de carreras
      (grado, pregrado, posgrado y diplomaturas).
    - Si ``carrera`` tiene un valor, busca por nombre (coincidencia parcial,
      ignorando mayúsculas y tildes). Con una única coincidencia devuelve la
      ficha completa; con varias, la lista para que precises cuál; y si no hay
      coincidencias, te muestra las carreras disponibles.
    """
    term = (carrera or "").strip()

    try:
        if not term:
            carreras = fetch_all_careers()
            logger.debug(f"Tool get_carreras | listado | {len(carreras)} carreras")
            return _format_list(carreras)

        matches = search_careers(term)
        logger.debug(
            f"Tool get_carreras | búsqueda={term!r} | {len(matches)} coincidencias"
        )

        if not matches:
            disponibles = fetch_all_careers()
            return (
                f"No encontré ninguna carrera que coincida con «{term}».\n\n"
                f"{_format_list(disponibles)}"
            )

        if len(matches) == 1:
            return _format_detail(matches[0])

        return (
            f"Encontré {len(matches)} carreras que coinciden con «{term}». "
            f"Pedímelas por su nombre exacto para ver la información completa:\n"
            f"{_format_list(matches)}"
        )

    except Exception as e:
        logger.error(f"Error en get_carreras: {e}")
        return (
            "No se pudo consultar la información de carreras en este momento. "
            "Por favor, intentá más tarde."
        )
