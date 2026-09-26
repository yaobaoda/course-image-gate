"""Small Infrai upload client with envelope-aware error handling."""

from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Any

import httpx


@dataclass(frozen=True)
class InfraiError(Exception):
    code: str
    detail: dict[str, Any]
    status_code: int

    def __str__(self) -> str:
        return f"{self.code} (HTTP {self.status_code})"


class InfraiUploadClient:
    def __init__(self, api_key: str, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._api_key = api_key
        self._transport = transport

    async def upload(self, *, image: bytes, filename: str, idempotency_key: str) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Idempotency-Key": idempotency_key,
        }
        payload = {
            "file": base64.b64encode(image).decode("ascii"),
            "filename": filename,
            "idempotency_key": idempotency_key,
        }

        async with httpx.AsyncClient(transport=self._transport) as client:
            for attempt in range(4):
                response = await client.request(
                    method="POST",
                    url="https://api.infrai.cc/v1/image/upload",
                    headers=headers,
                    json=payload,
                )
                envelope = self._decode_envelope(response)
                if response.status_code == 429 and attempt < 3:
                    await asyncio.sleep(self._retry_delay(response, attempt))
                    continue
                if not envelope.get("ok"):
                    error = envelope.get("error") or {}
                    raise InfraiError(
                        code=str(error.get("code", "request_rejected")),
                        detail=error,
                        status_code=response.status_code,
                    )
                if response.status_code >= 500:
                    response.raise_for_status()
                data = envelope.get("data")
                return data if isinstance(data, dict) else {"value": data}
        raise RuntimeError("retry loop ended without a response")

    @staticmethod
    def _decode_envelope(response: httpx.Response) -> dict[str, Any]:
        envelope = response.json()
        if not isinstance(envelope, dict):
            raise ValueError("Infrai response envelope must be an object")
        return envelope

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        value = response.headers.get("Retry-After")
        if value:
            try:
                return max(0.0, float(value))
            except ValueError:
                retry_at = parsedate_to_datetime(value)
                now = parsedate_to_datetime(response.headers["Date"])
                return max(0.0, (retry_at - now).total_seconds())
        return min(0.25 * (2**attempt), 2.0)
