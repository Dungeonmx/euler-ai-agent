import asyncio
from types import SimpleNamespace

import pytest

from guards.normalize import stable_hash
from models.chatRequest import ChatRequest
from models.message import Message
from services import chat as chat_service


class FakeSession:
    def __init__(self):
        self.commits = 0
        self.closed = False
        self.rolled_back = False

    async def commit(self):
        self.commits += 1

    async def close(self):
        self.closed = True

    async def rollback(self):
        self.rolled_back = True


class FakeRepo:
    def __init__(self, history=None, conversation_id=7):
        self.history = list(history or [])
        self.conversation_id = conversation_id
        self.created_with = None
        self.appended = None

    async def create_conversation(self, messages):
        self.created_with = messages
        self.history = list(messages)
        return SimpleNamespace(id=self.conversation_id, messages={"messages": self.history})

    async def append_user_message(self, conversation_id, user_message):
        if conversation_id != self.conversation_id:
            return None
        self.appended = user_message
        self.history.append(user_message)
        return SimpleNamespace(id=conversation_id, messages={"messages": self.history})

    async def update_with_response(self, conversation_id, message):
        self.history.append(message)
        return SimpleNamespace(id=conversation_id, messages={"messages": self.history})


def _request(text, messages=None, conversation_id=None):
    return ChatRequest(
        messages=messages or [Message(role="user", content=text)],
        conversation_id=conversation_id,
    )


def test_prepare_turn_allows_normal_question():
    repo, session = FakeRepo(), FakeSession()
    turn = asyncio.run(
        chat_service.prepare_turn(_request("¿Cuándo es la inscripción?"), repo, session)
    )
    assert turn.verdict.action == "allow"
    assert turn.conversation_id == 7
    assert repo.created_with[0]["hash"] == stable_hash("¿Cuándo es la inscripción?")
    assert session.commits == 1


def test_prepare_turn_finds_duplicate_in_existing_conversation():
    history = [
        {"role": "user", "content": "¿Cuándo es el examen?", "hash": stable_hash("¿Cuándo es el examen?")},
        {"role": "assistant", "content": "El 12/11.", "cacheable": True, "audio": "/audio/x.wav"},
    ]
    repo, session = FakeRepo(history=history), FakeSession()
    turn = asyncio.run(
        chat_service.prepare_turn(_request("cuando es el examen", conversation_id=7), repo, session)
    )
    assert turn.is_answer
    assert turn.verdict.source == "cache"
    assert turn.verdict.text == "El 12/11."


def test_prepare_turn_rejects_code_without_calling_llm():
    repo, session = FakeRepo(), FakeSession()
    turn = asyncio.run(chat_service.prepare_turn(_request("<b>hola</b>"), repo, session))
    assert turn.is_answer
    assert turn.verdict.source == "guard"
    assert turn.verdict.reason == "code"


def test_prepare_turn_raises_when_conversation_is_missing():
    repo, session = FakeRepo(conversation_id=7), FakeSession()
    with pytest.raises(chat_service.ConversationNotFound):
        asyncio.run(
            chat_service.prepare_turn(
                _request("hola", conversation_id=999), repo, session
            )
        )


def test_resolve_answer_marks_guard_as_not_cacheable(monkeypatch):
    monkeypatch.setattr(chat_service, "synthesize_text", lambda *a, **k: None)
    verdict = chat_service.check("<b>x</b>")
    message = asyncio.run(chat_service.resolve_answer(verdict))
    assert message["role"] == "assistant"
    assert message["source"] == "guard"
    assert message["cacheable"] is False
    assert message["guard_reason"] == "code"
    assert message["audio"] == "/audio/canned_code.wav"


def test_resolve_answer_regenerates_audio_when_file_is_missing(monkeypatch):
    calls = []

    def fake_tts(text, path):
        calls.append(text)

    monkeypatch.setattr(chat_service, "synthesize_text", fake_tts)
    verdict = chat_service.Verdict(
        action="answer",
        source="cache",
        reason="duplicate",
        text="El examen es el 12/11.",
        audio_filename="archivo_purgado.wav",
    )
    message = asyncio.run(chat_service.resolve_answer(verdict))
    assert message["cacheable"] is True
    assert message["source"] == "cache"
    assert "guard_reason" not in message
    assert calls == ["El examen es el 12/11."]
    assert message["audio"].endswith(".wav")


def test_stream_answer_emits_expected_events():
    message = {
        "role": "assistant",
        "content": "No logré entender tu mensaje.",
        "source": "guard",
        "cacheable": False,
        "guard_reason": "gibberish",
        "audio": "/audio/canned_gibberish.wav",
    }

    async def collect():
        return [chunk async for chunk in chat_service.stream_answer(3, message)]

    chunks = asyncio.run(collect())
    events = "".join(chunks)
    assert "event: conversation_id" in events
    assert "event: final_text" in events
    assert "event: guard" in events
    assert "event: audio" in events
    assert "event: done" in events


def test_resolve_answer_gives_up_when_audio_is_slow(monkeypatch):
    import time

    monkeypatch.setenv("GUARD_AUDIO_TIMEOUT", "0.05")
    monkeypatch.setenv("GUARD_CANNED_AUDIO", "false")

    def slow_tts(text, path):
        time.sleep(1)

    monkeypatch.setattr(chat_service, "synthesize_text", slow_tts)
    verdict = chat_service.Verdict(
        action="answer",
        source="cache",
        reason="duplicate",
        text="El examen es el 12/11.",
        audio_filename="archivo_purgado.wav",
    )
    message = asyncio.run(chat_service.resolve_answer(verdict))
    assert message["content"] == "El examen es el 12/11."
    assert "audio" not in message

