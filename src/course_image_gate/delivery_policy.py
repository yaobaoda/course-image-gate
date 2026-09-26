"""Course delivery decision and educator-facing counters."""

from __future__ import annotations

import base64
import binascii
import hashlib
from collections import defaultdict
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

from .infrai_upload import InfraiUploadClient


class PublicationState(StrEnum):
    LIVE = "live"
    BLOCKED = "blocked"


class ReviewSignals(BaseModel):
    adult_content: bool
    graphic_violence: bool


class CourseImageRequest(BaseModel):
    course_id: str = Field(min_length=1, max_length=100)
    lesson_id: str = Field(min_length=1, max_length=100)
    filename: str = Field(min_length=1, max_length=255)
    image_base64: str
    learner_deadline: datetime
    review: ReviewSignals

    @field_validator("image_base64")
    @classmethod
    def valid_image_bytes(cls, value: str) -> str:
        try:
            decoded = base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("image_base64 must contain valid base64") from exc
        if not decoded:
            raise ValueError("image_base64 must not be empty")
        return value


class EducatorReport(BaseModel):
    course_id: str
    live_images: int
    blocked_images: int


class CourseImageResult(BaseModel):
    course_id: str
    lesson_id: str
    publication_state: PublicationState
    learner_deadline: datetime
    educator_report: EducatorReport


class CourseImageGate:
    def __init__(self, upload_client: InfraiUploadClient) -> None:
        self._upload_client = upload_client
        self._counts: dict[str, dict[PublicationState, int]] = defaultdict(
            lambda: defaultdict(int)
        )

    async def review(self, request: CourseImageRequest) -> CourseImageResult:
        blocked = request.review.adult_content or request.review.graphic_violence
        state = PublicationState.BLOCKED if blocked else PublicationState.LIVE

        if state is PublicationState.LIVE:
            image = base64.b64decode(request.image_base64, validate=True)
            digest = hashlib.sha256(image).hexdigest()
            await self._upload_client.upload(
                image=image,
                filename=request.filename,
                idempotency_key=f"{request.course_id}:{request.lesson_id}:{digest}",
            )

        self._counts[request.course_id][state] += 1
        counts = self._counts[request.course_id]
        return CourseImageResult(
            course_id=request.course_id,
            lesson_id=request.lesson_id,
            publication_state=state,
            learner_deadline=request.learner_deadline,
            educator_report=EducatorReport(
                course_id=request.course_id,
                live_images=counts[PublicationState.LIVE],
                blocked_images=counts[PublicationState.BLOCKED],
            ),
        )
