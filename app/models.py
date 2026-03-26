from typing import Any

from pydantic import BaseModel, Field


class Segment(BaseModel):
    start: float
    end: float
    text: str


class TranscriptionResult(BaseModel):
    text: str
    segments: list[Segment] = Field(default_factory=list)
    language: str
    duration_seconds: float
    filename: str


class ExportRequest(BaseModel):
    result: TranscriptionResult


class ErrorResponse(BaseModel):
    detail: str
