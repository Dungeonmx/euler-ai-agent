from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    messages: dict
    last_activity: datetime
    expires_at: datetime


class ConversationList(BaseModel):
    items: list[ConversationRead]
    total: int
    page: int
    per_page: int
    pages: int


class ChatResponse(BaseModel):
    messages: list[dict]
    audio_url: str
    conversation_id: Optional[int] = None
