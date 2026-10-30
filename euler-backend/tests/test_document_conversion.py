import pytest
from fastapi.testclient import TestClient

import router.documents as documents_router
from api import app
from services import document_conversion
from services.document_conversion import (
    SUPPORTED_EXTENSIONS,
    ConversionError,
    UnsupportedFormatError,
    convert_document,
    is_supported,
    normalize_extension,
)


def test_supported_extensions():
    assert SUPPORTED_EXTENSIONS == (".pdf", ".docx", ".pptx", ".xlsx")


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("Reglamento.PDF", ".pdf"),
        ("clase.docx", ".docx"),
        ("presentacion.pptx", ".pptx"),
        ("notas.xlsx", ".xlsx"),
        ("sin_extension", ""),
        (None, ""),
        ("archivo.txt", ".txt"),
    ],
)
def test_normalize_extension(filename, expected):
    assert normalize_extension(filename) == expected


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("a.pdf", True),
        ("a.DOCX", True),
        ("a.pptx", True),
        ("a.xlsx", True),
        ("a.doc", False),
        ("a.zip", False),
        (None, False),
    ],
)
def test_is_supported(filename, expected):
    assert is_supported(filename) is expected


def test_convert_document_rejects_unsupported_extension():
    with pytest.raises(UnsupportedFormatError):
        convert_document(b"contenido", "archivo.txt")


def test_convert_document_wraps_converter_errors(monkeypatch):
    class FakeConverter:
        def convert_stream(self, *args, **kwargs):
            from markitdown import UnsupportedFormatException

            raise UnsupportedFormatException("nope")

    monkeypatch.setattr(document_conversion, "get_converter", lambda: FakeConverter())

    with pytest.raises(ConversionError):
        convert_document(b"contenido", "archivo.pdf")


def test_convert_document_returns_markdown(monkeypatch):
    class FakeResult:
        markdown = "# Titulo\n\nTexto"

    class FakeConverter:
        def convert_stream(self, stream, stream_info):
            assert stream_info.extension == ".pdf"
            assert stream.read() == b"contenido"
            return FakeResult()

    monkeypatch.setattr(document_conversion, "get_converter", lambda: FakeConverter())

    assert convert_document(b"contenido", "archivo.pdf") == "# Titulo\n\nTexto"


def test_convert_document_rejects_corrupt_pdf():
    with pytest.raises(ConversionError):
        convert_document(b"esto no es un pdf", "archivo.pdf")


def test_convert_document_rejects_zip_disguised_as_pdf():
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("hola.txt", "contenido")

    with pytest.raises(ConversionError):
        convert_document(buffer.getvalue(), "archivo.pdf")


def test_formats_endpoint():
    client = TestClient(app)

    response = client.get("/documentos-conversor/formatos")

    assert response.status_code == 200
    formats = response.json()["formats"]
    assert [f["extension"] for f in formats] == [".pdf", ".docx", ".pptx", ".xlsx"]
    assert all(f["mime_type"] and f["description"] for f in formats)


def _client():
    return TestClient(app)


def test_convert_endpoint_returns_json(monkeypatch):
    def fake_convert(data, filename=None, **kwargs):
        assert data == b"contenido"
        return "# Hola\n\nMundo"

    monkeypatch.setattr(documents_router, "convert_document", fake_convert)

    response = _client().post(
        "/documentos-conversor/convertir",
        files={"file": ("doc.pdf", b"contenido", "application/pdf")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "filename": "doc.pdf",
        "extension": ".pdf",
        "markdown": "# Hola\n\nMundo",
        "characters": 13,
    }


def test_convert_endpoint_rejects_unsupported_extension():
    response = _client().post(
        "/documentos-conversor/convertir",
        files={"file": ("doc.txt", b"contenido", "text/plain")},
    )

    assert response.status_code == 415


def test_convert_endpoint_rejects_empty_file():
    response = _client().post(
        "/documentos-conversor/convertir",
        files={"file": ("doc.pdf", b"", "application/pdf")},
    )

    assert response.status_code == 400


def test_convert_endpoint_rejects_too_large_file(monkeypatch):
    monkeypatch.setattr(documents_router, "MAX_UPLOAD_BYTES", 4)

    response = _client().post(
        "/documentos-conversor/convertir",
        files={"file": ("doc.pdf", b"demasiado", "application/pdf")},
    )

    assert response.status_code == 413


def test_convert_endpoint_maps_conversion_error(monkeypatch):
    def fake_convert(*args, **kwargs):
        raise ConversionError("archivo dañado")

    monkeypatch.setattr(documents_router, "convert_document", fake_convert)

    response = _client().post(
        "/documentos-conversor/convertir",
        files={"file": ("doc.pdf", b"contenido", "application/pdf")},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "archivo dañado"
