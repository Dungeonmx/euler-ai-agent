import pytest

from guards.gibberish import detect_gibberish


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("asdf asdf asdf", "teclado"),
        ("qwerty", "teclado"),
        ("Ã¡Ã©Ã­Ã³", "mojibake"),
        ("aG9sYSBtdW5kbyBjb21vIGVzdGFzIGFoby", "consonantes"),
        ("holamundo123456789012345678901234", "token_largo"),
        ("aaaaaaaaaaaa", "repeticion"),
        ("xkcdqzpt", "consonantes"),
        ("#$%&/()=?#$%&/()=?#$%&/()=?", "simbolos"),
    ],
)
def test_detect_gibberish_positives(text, expected):
    assert detect_gibberish(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "¿Cuándo es la inscripción a las carreras de ingeniería?",
        "Hola, ¿cómo estás?",
        "Necesito información sobre la diplomatura en inteligencia artificial",
        "ok",
        "si",
        "🎉🎉🎉",
        "Jajajaja",
        "https://www.ing.unlpam.edu.ar/noticias",
        "Escribime a difusion@ing.unlpam.edu.ar",
        "El examen es el 12/11 a las 8:30 hs.",
    ],
)
def test_detect_gibberish_negatives(text):
    assert detect_gibberish(text) is None
