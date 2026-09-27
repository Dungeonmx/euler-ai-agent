from pydantic import BaseModel

from .message import Message


class ChatRequest(BaseModel):
    messages: list[Message]
