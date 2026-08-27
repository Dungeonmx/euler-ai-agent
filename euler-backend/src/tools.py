from __future__ import annotations

import re
from typing import Optional

import requests
from bs4 import BeautifulSoup
from langchain.tools import tool
from pydantic import BaseModel, Field


BASE_URL = "https://www.ing.unlpam.edu.ar"


class FacultyNews(BaseModel):
    id: int = Field(description="Identificador único de la novedad en la facultad")
    title: str = Field(description="Título de la novedad o noticia")
    summary: str = Field(description="Resumen o copete de la novedad")
    url: str = Field(description="URL completa para acceder a la novedad en el sitio de la facultad")
    image_url: Optional[str] = Field(default=None, description="URL de la imagen asociada a la novedad")


def _clean_text(text: str) -> str:
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _extract_news_id(url: str) -> int:
    match = re.search(r'/verNovedad/(\d+)/', url)
    if match:
        return int(match.group(1))
    return 0


def fetch_faculty_news(n: int = 5) -> list[FacultyNews]:
    try:
        response = requests.get(
            BASE_URL,
            timeout=15,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                               'AppleWebKit/537.36 (KHTML, like Gecko) '
                               'Chrome/120.0.0.0 Safari/537.36'
            }
        )
        response.raise_for_status()
    except requests.RequestException as e:
        return [FacultyNews(
            id=0,
            title="Error al obtener novedades",
            summary=f"No se pudo acceder al sitio de la facultad: {str(e)}. Intenta nuevamente más tarde.",
            url=BASE_URL,
            image_url=None
        )]

    soup = BeautifulSoup(response.text, 'html.parser')
    novedades_section = soup.select_one('.home-listado-novedades')
    if not novedades_section:
        return [FacultyNews(
            id=0,
            title="No se encontraron novedades",
            summary="No se pudo encontrar la sección de novedades en el sitio de la facultad.",
            url=BASE_URL,
            image_url=None
        )]

    cards = novedades_section.select('.card-novedad-home')
    results = []

    for card in cards[:n]:
        title_tag = card.select_one('.tituloNovedad')
        summary_tag = card.select_one('.copeteNovedad')
        img_tag = card.select_one('.imgNovedades')

        title = _clean_text(title_tag.get_text()) if title_tag else "Sin título"
        summary = _clean_text(summary_tag.get_text()) if summary_tag else ""
        href = card.get('href', '')
        full_url = BASE_URL + href if href else ''
        image_url = img_tag.get('src') if img_tag else None
        news_id = _extract_news_id(full_url)

        results.append(FacultyNews(
            id=news_id,
            title=title,
            summary=summary,
            url=full_url,
            image_url=image_url
        ))

    if not results:
        return [FacultyNews(
            id=0,
            title="No se encontraron novedades",
            summary="No se encontraron novedades disponibles en el sitio de la facultad.",
            url=BASE_URL,
            image_url=None
        )]

    return results


@tool
def get_recent_news(cantidad: int = Field(default=5, description="Número de novedades a obtener, entre 1 y 10")) -> str:
    """Obtén las últimas novedades de la Facultad de Ingeniería de la UNLPam.
    Esta herramienta busca en el sitio oficial de la facultad (https://www.ing.unlpam.edu.ar)
    las últimas noticias y comunicados publicados. Úsala cuando el usuario pregunte sobre
    novedades, noticias, eventos, cursos, convocatorias, llamados, ofertas laborales,
    becas, o cualquier información reciente de la facultad. El argumento 'cantidad'
    determina cuántas novedades devolver (máximo 10)."""
    news = fetch_faculty_news(n=cantidad)

    print("obteniendo novedades...")
    print(news)

    if not news or (len(news) == 1 and news[0].id == 0):
        return news[0].summary if news else "No se pudieron obtener novedades en este momento."

    partes = []
    for i, item in enumerate(news, 1):
        partes.append(
            f"Novedad {i}: {item.title}\n"
            f"Resumen: {item.summary}\n"
        )

    return "\n\n".join(partes)
