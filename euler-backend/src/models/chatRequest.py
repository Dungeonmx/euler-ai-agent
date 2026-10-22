from typing import Optional

from pydantic import BaseModel, Field

from .message import Message


class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1)
    conversation_id: Optional[int] = None
