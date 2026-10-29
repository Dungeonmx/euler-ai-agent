from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from models.logger import logger
from repositories.training_data import TrainingDataRepository
from schemas.training_data import (
    TrainingDataCreate,
    TrainingDataList,
    TrainingDataRead,
    TrainingDataUpdate,
)
from storage.postgresql.session import get_session

router = APIRouter(prefix="/datos-entrenamiento", tags=["datos-entrenamiento"])


@router.post("", response_model=TrainingDataRead, status_code=status.HTTP_201_CREATED)
async def create_training_data(
    payload: TrainingDataCreate,
    session: AsyncSession = Depends(get_session),
):
    try:
        repo = TrainingDataRepository(session)
        created = await repo.create_training_data(payload.model_dump())
        await session.commit()
        return created
    except Exception as e:
        await session.rollback()
        logger.error(f"Error creando dato de entrenamiento: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=TrainingDataList)
async def list_training_data(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    try:
        repo = TrainingDataRepository(session)
        return await repo.list_paginated(page=page, per_page=per_page)
    except Exception as e:
        logger.error(f"Error listando datos de entrenamiento: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{training_data_id}", response_model=TrainingDataRead)
async def get_training_data(
    training_data_id: int,
    session: AsyncSession = Depends(get_session),
):
    try:
        repo = TrainingDataRepository(session)
        item = await repo.get_by_id(training_data_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Dato de entrenamiento no encontrado")
        return item
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo dato de entrenamiento: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{training_data_id}", response_model=TrainingDataRead)
async def update_training_data(
    training_data_id: int,
    payload: TrainingDataUpdate,
    session: AsyncSession = Depends(get_session),
):
    try:
        repo = TrainingDataRepository(session)
        updated = await repo.update_training_data(training_data_id, payload.model_dump())
        if updated is None:
            raise HTTPException(status_code=404, detail="Dato de entrenamiento no encontrado")
        await session.commit()
        return updated
    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Error actualizando dato de entrenamiento: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{training_data_id}")
async def delete_training_data(
    training_data_id: int,
    session: AsyncSession = Depends(get_session),
):
    try:
        repo = TrainingDataRepository(session)
        deleted = await repo.delete(training_data_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Dato de entrenamiento no encontrado")
        await session.commit()
        return {"detail": "Dato de entrenamiento eliminado"}
    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Error eliminando dato de entrenamiento: {e}")
        raise HTTPException(status_code=500, detail=str(e))
