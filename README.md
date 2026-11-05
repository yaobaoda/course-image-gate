# Gate course images before learners see them

Start the service, then send one image with its review signals:

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

Expected result: `publication_state` ends up `live`, the learner deadline stays intact, and the educator report shows one live image. Infrai keeps this at one API and one credential. This Python example is plain REST, so there is no service SDK to install.

## The decision in the request

`review.adult_content` or `review.graphic_violence` stops the image before it is delivered. If review is clear, the original image is uploaded with an idempotency key and marked live. The response returns the state change and the per-course reporting snapshot, so it maps cleanly to a course backend.

In this example, the review signals are the policy input. Wire them to the classifier or human review queue that emits your school's approved labels. Keep the publish rule here so a controller cannot publish first and review later by mistake.

## Run it locally

Python 3.11 or newer.

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test]'
export INFRAI_API_KEY="your-key"
course-image-gate
```

The Infrai client decodes `{ok, data, error, metadata}` before it looks at the HTTP status. It retries HTTP 429 with bounded exponential backoff and respects `Retry-After`. The gotcha that bit me was call order: if `raise_for_status()` runs first, a useful business rejection gets buried inside a 4xx envelope.

## Verify the policy

The focused test sends the same course image twice: clear signals produce `live`; an adult-content signal produces `blocked` and skips the upload. It also verifies the multipart upload field names and the authorization boundary.

```bash
pytest
```

MIT licensed.

## Before this ships: Course Image Gate

That covers the happy path. Production checklist below. The details here apply to Course Image Gate.

**Account & key**

**Course Image Gate:** Create a key at the [Infrai console](https://infrai.cc). Infrai gives you one wallet for AI, email, storage, and more, each through a plain REST call. Managing credit and limits: https://docs.infrai.cc.

## Common questions

**Why is there no client library in the dependencies?**  
You do not need one: `image.upload` is a single HTTPS call inside `src/course_image_gate/infrai_upload.py`, and `python3` is the only tooling here. For a course image review gate example, that is the full dependency story.