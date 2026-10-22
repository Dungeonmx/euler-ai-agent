from guards.normalize import stable_hash
from guards.service import (
    check,
    decorate_user_message,
    find_previous_answer,
    is_reusable,
)


def _history(*messages):
    return [decorate_user_message(m) for m in messages]


def test_allows_normal_spanish_question():
    verdict = check("¿Cuándo es la inscripción a ingeniería?")
    assert verdict.action == "allow"


def test_rejects_code():
    verdict = check("<script>alert('x')</script>")
    assert verdict.action == "answer"
    assert verdict.source == "guard"
    assert verdict.reason == "code"


def test_rejects_gibberish():
    verdict = check("asdf asdf asdf")
    assert verdict.reason == "gibberish"


def test_rejects_unsupported_language():
    verdict = check("Olá, quando é o exame de álgebra?")
    assert verdict.reason == "language"


def test_duplicate_returns_previous_answer():
    previous = _history(
        {"role": "user", "content": "¿Cuándo es el examen?"},
        {"role": "assistant", "content": "El examen es el 12/11.", "cacheable": True},
    )
    verdict = check("cuando es el examen", previous)
    assert verdict.action == "answer"
    assert verdict.source == "cache"
    assert verdict.text == "El examen es el 12/11."


def test_duplicate_ignores_non_cacheable_answer():
    previous = _history(
        {"role": "user", "content": "¿Cuándo es el examen?"},
        {"role": "assistant", "content": "Error al conectar", "cacheable": False},
    )
    assert check("¿Cuándo es el examen?", previous).action == "allow"


def test_duplicate_ignores_cached_guard_answer():
    previous = _history(
        {"role": "user", "content": "¿Cuándo es el examen?"},
        {"role": "assistant", "content": "No logré entender tu mensaje.", "source": "guard"},
    )
    assert check("¿Cuándo es el examen?", previous).action == "allow"


def test_duplicate_supports_legacy_rows_without_metadata():
    previous = [
        {"role": "user", "content": "¿Cuándo es el examen?"},
        {"role": "assistant", "content": "El examen es el 12/11.", "audio": "/audio/x.wav"},
    ]
    verdict = check("cuando es el examen", previous)
    assert verdict.reason == "duplicate"
    assert verdict.audio_filename == "x.wav"


def test_duplicate_skips_legacy_error_answers():
    previous = [
        {"role": "user", "content": "hola"},
        {"role": "assistant", "content": "No pude conectarme. Revisá tu conexión."},
    ]
    assert check("hola", previous).action == "allow"


def test_last_occurrence_wins():
    previous = _history(
        {"role": "user", "content": "hola"},
        {"role": "assistant", "content": "Primera", "cacheable": True},
        {"role": "user", "content": "hola"},
        {"role": "assistant", "content": "Segunda", "cacheable": True},
    )
    assert find_previous_answer(previous, "hola")["content"] == "Segunda"


def test_cached_answer_can_be_reused_again():
    # Una respuesta servida desde cache sigue siendo reutilizable (preguntar
    # tres veces la misma cosa no debe volver a llamar al LLM).
    previous = _history(
        {"role": "user", "content": "¿Cuándo es el examen?"},
        {"role": "assistant", "content": "El 12/11.", "source": "cache", "cacheable": True},
        {"role": "user", "content": "¿Cuándo es el examen?"},
        {"role": "assistant", "content": "El 12/11.", "source": "cache", "cacheable": True},
    )
    assert check("cuando es el examen", previous).reason == "duplicate"


def test_missing_answer_between_questions_is_not_a_hit():
    previous = _history(
        {"role": "user", "content": "hola"},
        {"role": "user", "content": "hola"},
    )
    assert check("hola", previous).action == "allow"


def test_is_reusable():
    assert is_reusable({"role": "assistant", "content": "ok", "cacheable": True})
    assert not is_reusable({"role": "assistant", "content": "", "cacheable": True})
    assert not is_reusable({"role": "assistant", "content": "ok", "cacheable": False})
    assert not is_reusable({"role": "user", "content": "ok"})


def test_hash_is_added_to_user_messages_only():
    user = decorate_user_message({"role": "user", "content": "Hola"})
    assistant = decorate_user_message({"role": "assistant", "content": "Hola"})
    assert user["hash"] == stable_hash("hola")
    assert "hash" not in assistant


def test_guards_can_be_disabled(monkeypatch):
    monkeypatch.setenv("GUARD_ENABLED", "false")
    assert check("<script>alert(1)</script>").action == "allow"
