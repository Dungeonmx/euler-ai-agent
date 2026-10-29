from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.training_data import DatosEntrenamiento
from repositories.base import BaseRepository
from schemas.training_data import TrainingDataList, TrainingDataRead


class TrainingDataRepository(BaseRepository[DatosEntrenamiento]):
    def __init__(self, session: AsyncSession):
        super().__init__(DatosEntrenamiento, session)

    async def get_by_id(self, training_data_id: int) -> Optional[TrainingDataRead]:
        obj = await self.get(training_data_id)
        return TrainingDataRead.model_validate(obj) if obj else None

    async def list_paginated(self, page: int = 1, per_page: int = 20) -> TrainingDataList:
        result = await self.session.execute(
            select(DatosEntrenamiento)
            .order_by(
                DatosEntrenamiento.created_at.desc(),
                DatosEntrenamiento.id.desc(),
            )
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        items = result.scalars().all()
        total = await self.count()

        return TrainingDataList(
            items=[TrainingDataRead.model_validate(item) for item in items],
            total=total,
            page=page,
            per_page=per_page,
            pages=(total + per_page - 1) // per_page if total > 0 else 0,
        )

    async def create_training_data(self, data: dict) -> TrainingDataRead:
        obj = await self.create(data)
        return TrainingDataRead.model_validate(obj)

    async def update_training_data(
        self, training_data_id: int, data: dict
    ) -> Optional[TrainingDataRead]:
        obj = await self.get(training_data_id)
        if obj is None:
            return None
        for field, value in data.items():
            setattr(obj, field, value)
        await self.session.flush()
        return TrainingDataRead.model_validate(obj)
