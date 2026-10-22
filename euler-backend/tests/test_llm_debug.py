import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from models.llm_debug import LLMPayloadLogger


def _run(handler, messages):
    handler.on_chat_model_start({}, [messages])


def test_logs_full_payload(caplog, monkeypatch):
    monkeypatch.setenv("LOG_LLM_PAYLOAD", "true")
    handler = LLMPayloadLogger(conversation_id=42, model="modelo-test", tools=["get_carreras"])

    with caplog.at_level(logging.INFO, logger="euler"):
        _run(
            handler,
            [SystemMessage(content="sos euler"), HumanMessage(content="hola")],
        )

    assert "[LLM_PAYLOAD]" in caplog.text
    assert '"conversation_id": 42' in caplog.text
    assert '"model": "modelo-test"' in caplog.text
    assert '"tools": [' in caplog.text
    assert '"role": "system"' in caplog.text
    assert '"content": "hola"' in caplog.text


def test_logs_tool_calls_in_openai_format(caplog, monkeypatch):
    monkeypatch.setenv("LOG_LLM_PAYLOAD", "true")
    handler = LLMPayloadLogger(conversation_id=7)
    message = AIMessage(
        content="",
        tool_calls=[{"name": "get_carreras", "args": {"carrera": "sistemas"}, "id": "call_1"}],
    )

    with caplog.at_level(logging.INFO, logger="euler"):
        _run(handler, [HumanMessage(content="carreras"), message])

    assert '"type": "function"' in caplog.text
    assert '"name": "get_carreras"' in caplog.text
    assert "sistemas" in caplog.text


def test_disabled_by_default(caplog, monkeypatch):
    monkeypatch.delenv("LOG_LLM_PAYLOAD", raising=False)
    handler = LLMPayloadLogger(conversation_id=1)

    with caplog.at_level(logging.INFO, logger="euler"):
        _run(handler, [HumanMessage(content="hola")])

    assert "[LLM_PAYLOAD]" not in caplog.text
