from typing import Literal, Optional

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


JobStatusLiteral = Literal["queued", "processing", "done", "failed"]


class JobCreateResponse(BaseModel):
    job_id: str
    status: JobStatusLiteral


class JobSummaryResponse(BaseModel):
    job_id: str
    status: JobStatusLiteral
    progress: float = 0.0
    current_step: str = "queued"
    filename: str
    error: Optional[str] = None
    duration_seconds: float = 0.0


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatusLiteral
    progress: float = 0.0
    current_step: str = "queued"
    filename: str
    error: Optional[str] = None
    duration_seconds: float = 0.0
    result: Optional[TranscriptionResult] = None
