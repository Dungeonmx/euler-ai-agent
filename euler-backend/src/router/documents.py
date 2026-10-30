import os

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from starlette.concurrency import run_in_threadpool

from models.logger import logger
from schemas.document import (
    DocumentConversionResponse,
    SupportedFormat,
    SupportedFormatsResponse,
)
from services.document_conversion import (
    SUPPORTED_EXTENSIONS,
    SUPPORTED_FORMATS,
    ConversionError,
    UnsupportedFormatError,
    convert_document,
    normalize_extension,
)

router = APIRouter(prefix="/documentos-conversor", tags=["documentos-conversor"])


def _read_max_mb() -> float:
    try:
        return float(os.getenv("DOCUMENT_MAX_MB", "20"))
    except ValueError:
        return 20.0


DOCUMENT_MAX_MB = _read_max_mb()
MAX_UPLOAD_BYTES = int(DOCUMENT_MAX_MB * 1024 * 1024)


@router.get("/formatos", response_model=SupportedFormatsResponse)
async def list_supported_formats() -> SupportedFormatsResponse:
    """Lista los formatos que acepta el endpoint de conversion."""
    return SupportedFormatsResponse(
        formats=[
            SupportedFormat(
                extension=fmt.extension,
                mime_type=fmt.mime_type,
                description=fmt.description,
            )
            for fmt in SUPPORTED_FORMATS
        ]
    )


@router.post("/convertir", response_model=DocumentConversionResponse)
async def convert_uploaded_document(
    file: UploadFile = File(..., description="Archivo PDF, DOCX, PPTX o XLSX"),
) -> DocumentConversionResponse:
    """Recibe un documento y devuelve su contenido como Markdown."""
    filename = file.filename or ""
    extension = normalize_extension(filename)

    try:
        if extension not in SUPPORTED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=(
                    f"Formato no soportado: {extension or 'desconocido'}. "
                    f"Formatos validos: {', '.join(SUPPORTED_EXTENSIONS)}"
                ),
            )

        # UploadFile.size lo completa el parser de Starlette: permite rechazar
        # un archivo enorme sin leerlo entero a memoria.
        if file.size is not None and file.size > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"El archivo supera el limite de {DOCUMENT_MAX_MB:g} MB.",
            )

        data = await file.read()

        if not data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo esta vacio.",
            )

        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"El archivo supera el limite de {DOCUMENT_MAX_MB:g} MB.",
            )
    finally:
        await file.close()

    try:
        markdown = await run_in_threadpool(convert_document, data, filename)
    except UnsupportedFormatError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)
        ) from exc
    except ConversionError as exc:
        logger.warning(f"No se pudo convertir {filename!r}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except Exception as exc:  # pragma: no cover - salvaguarda
        logger.error(f"Error inesperado convirtiendo {filename!r}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error inesperado al convertir el documento.",
        ) from exc

    return DocumentConversionResponse(
        filename=filename,
        extension=extension,
        markdown=markdown,
        characters=len(markdown),
    )
