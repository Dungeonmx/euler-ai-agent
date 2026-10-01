import json
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from storage.postgresql.base import Base

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    messages: Mapped[dict] = mapped_column(JSON)
    last_activity: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, last_activity={self.last_activity})>"

    @staticmethod
    def compute_expires_at(last_activity: datetime, ttl_seconds: int = 3600) -> datetime:
        from datetime import timedelta
        return last_activity + timedelta(seconds=ttl_seconds)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "messages": self.messages,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }
