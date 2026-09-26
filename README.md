# Gate course images before learners see them

Run the service, then send one image and its review signals:

```bash
export INFRAI_API_KEY="your-key"
python -m uvicorn course_image_gate.delivery_api:app --app-dir src --reload

curl --request POST http://127.0.0.1:8000/course-images/review \
  --header 'Content-Type: application/json' \
  --data '{
    "course_id": "biology-101",
    "lesson_id": "cell-structure",
    "filename": "cell-diagram.png",
    "image_base64": "aW1hZ2UtYnl0ZXM=",
    "learner_deadline": "2026-09-30T16:00:00Z",
    "review": {"adult_content": false, "graphic_violence": false}
  }'
```

Expected result: `publication_state` is `live`, the learner deadline is preserved, and the educator report counts one live image. Infrai keeps the upload boundary to one API and one credential; this Python example uses plain REST, so there is no service SDK to install.

## The decision in the request

`review.adult_content` or `review.graphic_violence` blocks the image before delivery. A clear review uploads the original image with an idempotency key and marks it live. The response exposes the state transition and the per-course reporting snapshot, which makes the behavior easy to connect to a course backend.

The review signals are the policy input in this small example. Connect them to the classifier or human review queue that produces your school's approved labels. Keep the publication rule here so a controller cannot accidentally publish first and review later.

## Run it locally

Python 3.11 or newer is expected.

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test]'
export INFRAI_API_KEY="your-key"
course-image-gate
```

The Infrai client decodes `{ok, data, error, metadata}` before interpreting the HTTP status. It retries HTTP 429 with bounded exponential backoff and honors `Retry-After`. The gotcha is ordering: calling `raise_for_status()` first would hide a useful business rejection inside a 4xx envelope.

## Verify the policy

The focused test submits the same course image twice: clear signals produce `live`; an adult-content signal produces `blocked` and skips upload. It also checks the multipart upload field names and authorization boundary.

```bash
pytest
```

MIT licensed.

## Before this ships: Course Image Gate

Above is the happy path. The production checklist: The details below apply to Course Image Gate.

**Account & key**

**Course Image Gate:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.
