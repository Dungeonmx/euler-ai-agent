import pytest

from guards.code_detect import detect_code


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("<div>hola</div>", "html_tag"),
        ("<script>alert(1)</script>", "html_tag"),
        ("&lt;script&gt;", "html_entity"),
        ("```python\nprint(1)\n```", "markdown_code"),
        ("<?php echo $x; ?>", "php_open"),
        ("<?= $nombre ?>", "php_open"),
        ("function saludar() { return 1; }", "js_function"),
        ("const x = 1", "js_declaration"),
        ("document.getElementById('x')", "js_dom"),
        ("console.log('hola')", "js_console"),
        ("$('#boton').click()", "js_jquery"),
        ("SELECT * FROM usuarios UNION SELECT password FROM admin", "sql_union"),
        ("' OR 1=1 --", "sql_injection"),
        ("DROP TABLE conversations", "sql_drop"),
    ],
)
def test_detect_code_positives(text, expected):
    assert detect_code(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "¿Se enseña PHP en la facultad?",
        "¿Qué lenguajes de programación se ven en la carrera?",
        "Quiero información sobre la materia JavaScript",
        "¿Hay cursos de HTML y CSS?",
        "5 < 3 y 2 > 1",
        "¿Cuándo es la inscripción a ingeniería?",
        "",
    ],
)
def test_detect_code_negatives(text):
    assert detect_code(text) is None
