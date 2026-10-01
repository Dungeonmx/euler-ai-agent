from typing import Optional

from pydantic import BaseModel

from .message import Message


class ChatRequest(BaseModel):
    messages: list[Message]
    conversation_id: Optional[int] = None
