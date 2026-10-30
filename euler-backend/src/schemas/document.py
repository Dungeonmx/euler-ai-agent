from pydantic import BaseModel


class SupportedFormat(BaseModel):
    extension: str
    mime_type: str
    description: str


class SupportedFormatsResponse(BaseModel):
    formats: list[SupportedFormat]


class DocumentConversionResponse(BaseModel):
    filename: str
    extension: str
    markdown: str
    characters: int
