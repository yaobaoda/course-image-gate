"""Executable FastAPI boundary for course image review."""

import os

import uvicorn
from fastapi import FastAPI, HTTPException

from .delivery_policy import CourseImageGate, CourseImageRequest, CourseImageResult
from .infrai_upload import InfraiError, InfraiUploadClient


def build_gate() -> CourseImageGate:
    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise RuntimeError("Set INFRAI_API_KEY before starting the service")
    return CourseImageGate(InfraiUploadClient(api_key))


app = FastAPI(title="Course image gate")
_gate: CourseImageGate | None = None


def get_gate() -> CourseImageGate:
    global _gate
    if _gate is None:
        _gate = build_gate()
    return _gate


@app.post("/course-images/review", response_model=CourseImageResult)
async def review_course_image(request: CourseImageRequest) -> CourseImageResult:
    try:
        return await get_gate().review(request)
    except InfraiError as exc:
        status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=status, detail=exc.detail) from exc


def run() -> None:
    uvicorn.run("course_image_gate.delivery_api:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    run()
