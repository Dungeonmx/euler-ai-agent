"""Conversion de documentos a Markdown con MarkItDown.

Solo se aceptan los formatos de la whitelist. El contenido se pasa siempre como
un stream en memoria (`BytesIO`), nunca como ruta o URL: MarkItDown hace I/O con
los privilegios del proceso y no queremos que un usuario pueda leer archivos
locales ni hacer requests desde el servidor.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from markitdown import (
    FileConversionException,
    MarkItDown,
    StreamInfo,
    UnsupportedFormatException,
)
from markitdown.converters import (
    DocxConverter,
    PdfConverter,
    PptxConverter,
    XlsxConverter,
)


class UnsupportedFormatError(ValueError):
    """La extension del archivo no esta entre las soportadas."""


class ConversionError(RuntimeError):
    """MarkItDown no pudo convertir el archivo."""


@dataclass(frozen=True)
class SupportedFormat:
    extension: str
    mime_type: str
    description: str


SUPPORTED_FORMATS: tuple[SupportedFormat, ...] = (
    SupportedFormat(
        extension=".pdf",
        mime_type="application/pdf",
        description="Documento PDF",
    ),
    SupportedFormat(
        extension=".docx",
        mime_type=(
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ),
        description="Documento Word",
    ),
    SupportedFormat(
        extension=".pptx",
        mime_type=(
            "application/vnd.openxmlformats-officedocument."
            "presentationml.presentation"
        ),
        description="Presentacion PowerPoint",
    ),
    SupportedFormat(
        extension=".xlsx",
        mime_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        description="Planilla Excel",
    ),
)

SUPPORTED_EXTENSIONS: tuple[str, ...] = tuple(
    fmt.extension for fmt in SUPPORTED_FORMATS
)


@lru_cache(maxsize=1)
def get_converter() -> MarkItDown:
    """Instancia unica de MarkItDown con solo los cuatro convertidores.

    Construirla carga el modelo de magika, asi que se hace una sola vez y de
    forma perezosa (no en el import, para no demorar el arranque de la API).

    Se registran solo PDF, DOCX, PPTX y XLSX. Con los convertidores built-in
    completos, un ZIP renombrado a .pdf terminaria descomprimido y un .pdf con
    texto plano se devolveria como texto; aca eso falla con 422.
    """
    converter = MarkItDown(enable_builtins=False)
    for instance in (
        DocxConverter(),
        XlsxConverter(),
        PptxConverter(),
        PdfConverter(),
    ):
        converter.register_converter(instance)
    return converter


def normalize_extension(filename: str | None) -> str:
    """Devuelve la extension en minusculas con punto, o cadena vacia."""
    if not filename:
        return ""
    return Path(filename).suffix.lower()


def is_supported(filename: str | None) -> bool:
    return normalize_extension(filename) in SUPPORTED_EXTENSIONS


def convert_document(
    data: bytes,
    filename: str | None = None,
    *,
    extension: str | None = None,
) -> str:
    """Convierte el contenido de un documento a Markdown.

    `extension` tiene prioridad sobre la que se deduce de `filename`.
    """
    ext = (extension or normalize_extension(filename)).lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFormatError(
            f"Formato no soportado: {ext or 'desconocido'}. "
            f"Formatos validos: {', '.join(SUPPORTED_EXTENSIONS)}"
        )

    stream_info = StreamInfo(
        extension=ext,
        filename=Path(filename).name if filename else None,
    )

    try:
        result = get_converter().convert_stream(
            io.BytesIO(data),
            stream_info=stream_info,
        )
    except UnsupportedFormatException as exc:
        raise ConversionError(
            "El archivo no parece ser un documento valido del formato indicado."
        ) from exc
    except FileConversionException as exc:
        raise ConversionError(
            "No se pudo convertir el archivo. Verifica que no este dañado."
        ) from exc

    return result.markdown
