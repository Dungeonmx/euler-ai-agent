import pytest

from guards.normalize import normalize, stable_hash


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("¿Cuándo es el examen?", "cuando es el examen"),
        ("  HOLA   mundo ", "hola mundo"),
        ("Inscripción 2026!!!", "inscripcion 2026"),
        ("Ingeniería en Sistemas", "ingenieria en sistemas"),
        ("", ""),
        (None, ""),
    ],
)
def test_normalize(raw, expected):
    assert normalize(raw) == expected


def test_stable_hash_ignores_case_accents_and_punctuation():
    assert stable_hash("¿Cuándo es el examen?") == stable_hash("cuando es el examen")
    assert stable_hash("¿Cuándo es el examen?") != stable_hash("cuando es la inscripcion")


def test_stable_hash_length():
    assert len(stable_hash("hola")) == 32
