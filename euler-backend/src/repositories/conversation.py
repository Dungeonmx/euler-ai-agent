import json
from datetime import datetime, timezone
from typing import Optional, Sequence

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from models.conversation import Conversation
from repositories.base import BaseRepository
from schemas.conversation import ConversationRead, ConversationList


class ConversationRepository(BaseRepository[Conversation]):
    def __init__(self, session: AsyncSession, ttl_seconds: int = 3600):
        super().__init__(Conversation, session)
        self.ttl_seconds = ttl_seconds

    async def create_conversation(self, messages: list[dict]) -> Conversation:
        now = datetime.now(timezone.utc)
        expires_at = Conversation.compute_expires_at(now, self.ttl_seconds)
        return await self.create({
            "messages": {"messages": messages},
            "last_activity": now,
            "expires_at": expires_at,
        })

    async def append_user_message(self, conversation_id: int, user_message: dict) -> Optional[Conversation]:
        conversation = await self.get(conversation_id)
        if not conversation:
            return None
        # Reemplazar el dict completo para que SQLAlchemy detecte el cambio
        conversation.messages = {
            "messages": conversation.messages["messages"] + [user_message],
        }
        conversation.last_activity = datetime.now(timezone.utc)
        conversation.expires_at = Conversation.compute_expires_at(
            conversation.last_activity, self.ttl_seconds
        )
        await self.session.flush()
        return conversation

    async def update_with_response(self, conversation_id: int, assistant_message: dict) -> Optional[Conversation]:
        conversation = await self.get(conversation_id)
        if not conversation:
            return None
        # Reemplazar el dict completo para que SQLAlchemy detecte el cambio
        conversation.messages = {
            "messages": conversation.messages["messages"] + [assistant_message],
        }
        conversation.last_activity = datetime.now(timezone.utc)
        conversation.expires_at = Conversation.compute_expires_at(
            conversation.last_activity, self.ttl_seconds
        )
        await self.session.flush()
        return conversation

    async def get_by_id(self, conversation_id: int) -> Optional[ConversationRead]:
        conversation = await self.get(conversation_id)
        if not conversation:
            return None
        return ConversationRead.model_validate(conversation)

    async def list_active(self, page: int = 1, per_page: int = 20) -> ConversationList:
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(Conversation)
            .where(Conversation.expires_at > now)
            .order_by(Conversation.id.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        items = result.scalars().all()

        count_result = await self.session.execute(
            select(func.count(Conversation.id))
            .where(Conversation.expires_at > now)
        )
        total = count_result.scalar_one()

        return ConversationList(
            items=[ConversationRead.model_validate(c) for c in items],
            total=total,
            page=page,
            per_page=per_page,
            pages=(total + per_page - 1) // per_page if total > 0 else 0,
        )

    async def list_all(self, page: int = 1, per_page: int = 20) -> ConversationList:
        result = await self.get_multi(skip=(page - 1) * per_page, limit=per_page)
        count_result = await self.count()
        total = count_result

        return ConversationList(
            items=[ConversationRead.model_validate(c) for c in result],
            total=total,
            page=page,
            per_page=per_page,
            pages=(total + per_page - 1) // per_page if total > 0 else 0,
        )

    async def delete_all(self) -> int:
        result = await self.session.execute(delete(Conversation))
        await self.session.flush()
        return result.rowcount
