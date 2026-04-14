from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import aiohttp
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from ltx_payload_builder import (
    ASPECT_RATIOS,
    FPS,
    SECONDS_MAX,
    SECONDS_MIN,
    SECONDS_STEP,
    build_payload,
    seconds_to_frames,
)

ROOT_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT_DIR / "frontend"

app = FastAPI(title="LTX 2.3 Payload Builder")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR / "static"), name="static")


class PayloadRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=1000)
    seconds: float = Field(default=5.0, ge=SECONDS_MIN, le=SECONDS_MAX)
    aspect_ratio: str = Field(default="16:9")
    image_name: str = Field(..., min_length=1)
    image_data_url: str = Field(..., min_length=1)
    optimize_prompt: bool = True


class SubmitRequest(BaseModel):
    endpoint_url: str = Field(..., min_length=1)
    auth_token: str = ""
    payload: dict[str, Any]
    timeout_seconds: int = Field(default=900, ge=5, le=3600)

    @field_validator("endpoint_url")
    @classmethod
    def validate_endpoint_url(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("Endpoint URL must start with http:// or https://")
        return normalized


@app.get("/", response_class=FileResponse)
async def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/config")
async def config() -> dict[str, object]:
    return {
        "fps": FPS,
        "seconds": {
            "min": SECONDS_MIN,
            "max": SECONDS_MAX,
            "step": SECONDS_STEP,
            "default": 5.0,
        },
        "aspect_ratios": ASPECT_RATIOS,
        "text_to_video_enabled": False,
    }


@app.post("/api/payload")
async def create_payload(request: PayloadRequest) -> dict[str, object]:
    try:
        payload = build_payload(
            prompt=request.prompt,
            seconds=request.seconds,
            aspect_ratio=request.aspect_ratio,
            image_name=request.image_name,
            image_data_url=request.image_data_url,
            optimize_prompt=request.optimize_prompt,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    dimensions = ASPECT_RATIOS[request.aspect_ratio]

    return {
        "payload": payload,
        "summary": {
            "frames": seconds_to_frames(request.seconds),
            "seconds": request.seconds,
            "fps": FPS,
            "width": dimensions["width"],
            "height": dimensions["height"],
            "aspect_ratio": request.aspect_ratio,
            "optimize_prompt": request.optimize_prompt,
        },
    }


@app.post("/api/submit")
async def submit_payload(request: SubmitRequest) -> dict[str, object]:
    headers = {"Content-Type": "application/json"}
    auth_token = request.auth_token.strip()
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    timeout = aiohttp.ClientTimeout(total=request.timeout_seconds)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                request.endpoint_url,
                json=request.payload,
                headers=headers,
            ) as response:
                raw_body = await response.text()
                content_type = response.headers.get("Content-Type", "")
                response_json: Any | None = None

                if "json" in content_type.lower():
                    try:
                        response_json = json.loads(raw_body)
                    except json.JSONDecodeError:
                        response_json = None

                return {
                    "ok": 200 <= response.status < 300,
                    "status_code": response.status,
                    "content_type": content_type or "application/octet-stream",
                    "endpoint_url": request.endpoint_url,
                    "response_json": response_json,
                    "response_text": None if response_json is not None else raw_body,
                }
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Submit request timed out.") from exc
    except aiohttp.ClientError as exc:
        raise HTTPException(status_code=502, detail=f"Submit request failed: {exc}") from exc
