import pytest

from guards.language import detect_unsupported_language


@pytest.mark.parametrize(
    "text",
    [
        "Hola, ¿cuándo es el examen de álgebra?",
        "Necesito información sobre la carrera de ingeniería en sistemas",
        "Hello, when is the entrance exam for engineering?",
        "I would like to know more about the scholarship program",
        "¿Dónde está la facultad de ingeniería?",
    ],
)
def test_allowed_languages(text):
    assert detect_unsupported_language(text) is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Olá, quando é o exame de álgebra?", "pt"),
        ("Wie komme ich zur Fakultät für Ingenieurwissenschaften?", "de"),
    ],
)
def test_unsupported_languages(text, expected):
    result = detect_unsupported_language(text)
    assert result is not None
    assert result.lang == expected


@pytest.mark.parametrize(
    "text",
    [
        "hola",
        "ok",
        "si",
        "3er piso",
        "",
        "https://www.ing.unlpam.edu.ar",
    ],
)
def test_short_or_ambiguous_text_passes(text):
    # Fail-open: sin señal suficiente no se rechaza.
    assert detect_unsupported_language(text) is None


def test_can_be_disabled(monkeypatch):
    monkeypatch.setenv("GUARD_ALLOWED_LANGUAGES", "es")
    assert detect_unsupported_language("Hello, when is the entrance exam?") is not None
