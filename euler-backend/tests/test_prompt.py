import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from models.prompt import build_llm_messages


def _roles(messages):
    return [message.type for message in messages]


def _content(messages):
    return [message.content for message in messages]


def test_single_turn_with_system_role():
    messages = build_llm_messages(
        [{"role": "user", "content": "hola"}],
        system_prompt="SOS EULER",
        mode="system",
        max_turns=0,
    )
    assert _roles(messages) == ["system", "human"]
    assert messages[0].content == "SOS EULER"


def test_first_user_mode_has_no_system_role():
    # Gemma no soporta "system": el prompt va dentro del primer mensaje.
    messages = build_llm_messages(
        [
            {"role": "user", "content": "hola"},
            {"role": "assistant", "content": "respuesta"},
            {"role": "user", "content": "otra"},
        ],
        system_prompt="SOS EULER",
        mode="first_user",
        max_turns=0,
    )
    assert _roles(messages) == ["human", "ai", "human"]
    assert messages[0].content.startswith("SOS EULER")
    assert messages[0].content.endswith("hola")
    assert messages[2].content == "otra"


def test_history_alternates_without_duplicates():
    # El caso que rompía en vLLM: historial reenviado por el cliente y
    # además duplicado en el estado anterior.
    messages = build_llm_messages(
        [
            {"role": "user", "content": "hola"},
            {"role": "assistant", "content": "respuesta 1"},
            {"role": "user", "content": "otra pregunta"},
        ],
        system_prompt="SOS EULER",
        mode="system",
        max_turns=0,
    )
    assert _roles(messages) == ["system", "human", "ai", "human"]
    assert _content(messages).count("hola") == 1


def test_consecutive_user_messages_are_merged():
    # Un turno que falló deja dos preguntas seguidas en la base.
    messages = build_llm_messages(
        [
            {"role": "user", "content": "primera"},
            {"role": "user", "content": "segunda"},
        ],
        system_prompt="",
        max_turns=0,
    )
    assert _roles(messages) == ["human"]
    assert messages[0].content == "primera\n\nsegunda"


def test_consecutive_assistant_messages_keep_the_last():
    messages = build_llm_messages(
        [
            {"role": "user", "content": "hola"},
            {"role": "assistant", "content": "vieja"},
            {"role": "assistant", "content": "nueva"},
            {"role": "user", "content": "otra"},
        ],
        system_prompt="",
        max_turns=0,
    )
    assert _roles(messages) == ["human", "ai", "human"]
    assert messages[1].content == "nueva"


def test_leading_assistant_is_dropped():
    messages = build_llm_messages(
        [
            {"role": "assistant", "content": "huérfana"},
            {"role": "user", "content": "hola"},
        ],
        system_prompt="",
        max_turns=0,
    )
    assert _roles(messages) == ["human"]


def test_ignores_metadata_and_unknown_roles():
    messages = build_llm_messages(
        [
            {"role": "user", "content": "hola", "hash": "abc", "source": "guard"},
            {"role": "tool", "content": "resultado de tool"},
            {"role": "assistant", "content": "", "source": "guard"},
            {"role": "assistant", "content": "respuesta", "cacheable": True},
            {"role": "user", "content": "otra"},
        ],
        system_prompt="",
        max_turns=0,
    )
    assert _roles(messages) == ["human", "ai", "human"]


def test_window_keeps_last_turns_and_alternation():
    history = []
    for index in range(5):
        history.append({"role": "user", "content": f"pregunta {index}"})
        history.append({"role": "assistant", "content": f"respuesta {index}"})
    history.append({"role": "user", "content": "actual"})

    messages = build_llm_messages(history, system_prompt="", max_turns=2)
    assert _roles(messages) == ["human", "ai", "human"]
    assert messages[0].content == "pregunta 4"
    assert messages[-1].content == "actual"


def test_zero_turns_means_no_limit():
    history = []
    for index in range(30):
        history.append({"role": "user", "content": f"pregunta {index}"})
        history.append({"role": "assistant", "content": f"respuesta {index}"})
    messages = build_llm_messages(history, system_prompt="", max_turns=0)
    assert len(messages) == 60


def test_empty_system_prompt_adds_no_system_message():
    messages = build_llm_messages(
        [{"role": "user", "content": "hola"}], system_prompt="   ", mode="system"
    )
    assert _roles(messages) == ["human"]


def test_empty_history_returns_empty_list():
    assert build_llm_messages([], system_prompt="SOS EULER") == []


def test_reads_config_from_environment(monkeypatch):
    monkeypatch.setenv("LLM_SYSTEM_MODE", "first_user")
    monkeypatch.setenv("LLM_HISTORY_MAX_TURNS", "1")
    monkeypatch.setenv("SYSTEM_PROMPT", "SOS EULER")

    history = [
        {"role": "user", "content": "vieja"},
        {"role": "assistant", "content": "respuesta"},
        {"role": "user", "content": "actual"},
    ]
    messages = build_llm_messages(history)
    assert _roles(messages) == ["human"]
    assert messages[0].content == "SOS EULER\n\nactual"


def test_messages_are_langchain_types():
    messages = build_llm_messages(
        [
            {"role": "user", "content": "hola"},
            {"role": "assistant", "content": "respuesta"},
            {"role": "user", "content": "otra"},
        ],
        system_prompt="SOS EULER",
        mode="system",
    )
    assert isinstance(messages[0], SystemMessage)
    assert isinstance(messages[1], HumanMessage)
    assert isinstance(messages[2], AIMessage)


def test_agent_receives_valid_alternating_payload():
    # Integración con el framework real: create_agent ya no agrega un system
    # prompt propio, así que el payload es exactamente el que armamos.
    from langchain.agents import create_agent
    from langchain_core.callbacks import BaseCallbackHandler
    from langchain_core.language_models.fake_chat_models import FakeListChatModel

    class Recorder(BaseCallbackHandler):
        def __init__(self):
            self.roles = []

        def on_chat_model_start(self, serialized, messages, **kwargs):
            self.roles.append([message.type for message in messages[0]])

    llm = FakeListChatModel(responses=["respuesta 1", "respuesta 2"])
    agent = create_agent(llm, tools=[])
    recorder = Recorder()
    config = {"callbacks": [recorder]}

    agent.invoke(
        {"messages": build_llm_messages(
            [{"role": "user", "content": "hola"}],
            system_prompt="SOS EULER",
            mode="first_user",
        )},
        config=config,
    )
    agent.invoke(
        {"messages": build_llm_messages(
            [
                {"role": "user", "content": "hola"},
                {"role": "assistant", "content": "respuesta 1"},
                {"role": "user", "content": "otra"},
            ],
            system_prompt="SOS EULER",
            mode="first_user",
        )},
        config=config,
    )

    assert recorder.roles == [["human"], ["human", "ai", "human"]]
