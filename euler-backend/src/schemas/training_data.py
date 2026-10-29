from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TrainingDataCreate(BaseModel):
    titulo: str = Field(min_length=1, max_length=500)
    contenido: str = Field(min_length=1)

    @field_validator("titulo", "contenido")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("no puede estar vacio")
        return value


class TrainingDataUpdate(TrainingDataCreate):
    """PUT: reemplazo total, ambos campos requeridos."""


class TrainingDataRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    titulo: str
    contenido: str
    created_at: datetime


class TrainingDataList(BaseModel):
    items: list[TrainingDataRead]
    total: int
    page: int
    per_page: int
    pages: int
