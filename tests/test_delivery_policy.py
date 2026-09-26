import base64
import json
from datetime import datetime, timezone

import httpx
import pytest

from course_image_gate.delivery_policy import (
    CourseImageGate,
    CourseImageRequest,
    PublicationState,
)
from course_image_gate.infrai_upload import InfraiUploadClient


def request_for(*, adult_content: bool) -> CourseImageRequest:
    return CourseImageRequest(
        course_id="biology-101",
        lesson_id="cell-structure",
        filename="cell-diagram.png",
        image_base64=base64.b64encode(b"image-bytes").decode("ascii"),
        learner_deadline=datetime(2026, 9, 30, 16, tzinfo=timezone.utc),
        review={"adult_content": adult_content, "graphic_violence": False},
    )


@pytest.mark.asyncio
async def test_review_controls_delivery_and_educator_report() -> None:
    uploads = 0

    def accept_upload(request: httpx.Request) -> httpx.Response:
        nonlocal uploads
        uploads += 1
        body = json.loads(request.content)
        assert request.method == "POST"
        assert request.url.path == "/v1/image/upload"
        assert request.headers["Authorization"] == "Bearer test-key"
        assert request.headers["Idempotency-Key"].startswith("biology-101:cell-structure:")
        assert request.headers["Content-Type"] == "application/json"
        assert body == {
            "file": base64.b64encode(b"image-bytes").decode("ascii"),
            "filename": "cell-diagram.png",
            "idempotency_key": request.headers["Idempotency-Key"],
        }
        return httpx.Response(200, json={"ok": True, "data": {"id": "img_123"}, "error": None, "metadata": {}})

    client = InfraiUploadClient("test-key", transport=httpx.MockTransport(accept_upload))
    gate = CourseImageGate(client)

    live = await gate.review(request_for(adult_content=False))
    blocked = await gate.review(request_for(adult_content=True))

    assert live.publication_state is PublicationState.LIVE
    assert live.learner_deadline == datetime(2026, 9, 30, 16, tzinfo=timezone.utc)
    assert blocked.publication_state is PublicationState.BLOCKED
    assert blocked.educator_report.live_images == 1
    assert blocked.educator_report.blocked_images == 1
    assert uploads == 1
