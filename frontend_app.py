from __future__ import annotations

import asyncio
import json
import os
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlsplit

import aiohttp
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from starlette.requests import Request
from starlette.responses import Response

from ltx_payload_builder import (
    ASPECT_RATIOS,
    FPS,
    SECONDS_MAX,
    SECONDS_MIN,
    SECONDS_STEP,
    build_payload,
    seconds_to_frames,
)
from workflow_support import (
    apply_input_filename_map,
    build_output_path,
    collect_output_entries,
    guess_media_type,
    write_input_images,
)

ROOT_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT_DIR / "frontend"
COMFY_NODES = os.environ.get("COMFY_NODES", "127.0.0.1:8188").split(",")
COMFY_INPUT_DIR = os.environ.get("COMFY_INPUT_DIR", "/comfyui/input")
LOCAL_COMFY_NODE = os.environ.get("LOCAL_COMFY_NODE", "127.0.0.1:8188").strip()
POD_SUBMIT_INPUT_FILES: dict[str, list[str]] = {}

app = FastAPI(title="LTX 2.3 Payload Builder")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR / "static"), name="static")


@app.middleware("http")
async def disable_frontend_caching(request: Request, call_next) -> Response:
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


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


class PodSubmitRequest(BaseModel):
    payload: dict[str, Any]
    timeout_seconds: int = Field(default=900, ge=5, le=3600)


def get_run_mode() -> str:
    run_mode = os.environ.get("RUN_MODE", "").strip().lower()
    if run_mode in {"worker", "local-api", "pod"}:
        return run_mode
    if os.environ.get("SERVE_API_LOCALLY", "").strip().lower() == "true":
        return "local-api"
    return "worker"


def get_submission_mode() -> str:
    return "pod" if get_run_mode() == "pod" else "endpoint"


def normalize_node_host(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise RuntimeError("LOCAL_COMFY_NODE is not configured.")

    if "://" in normalized:
        parsed = urlsplit(normalized)
        if not parsed.netloc:
            raise RuntimeError(f"Invalid LOCAL_COMFY_NODE value: {value}")
        normalized = parsed.netloc

    return normalized.rstrip("/")


def get_pod_submit_node() -> str:
    return normalize_node_host(LOCAL_COMFY_NODE)


def prepare_pod_images(
    images: list[dict[str, str]] | None,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    if not images:
        return {}, []

    job_prefix = f"frontend-{uuid.uuid4().hex[:12]}"
    replacements: dict[str, str] = {}
    prepared_images: list[dict[str, str]] = []

    for image in images:
        image_name = image.get("name")
        image_data = image.get("image")
        if not image_name or not image_data:
            raise ValueError(
                "'images' must be a list of objects with 'name' and 'image' keys."
            )

        scoped_name = str(Path(job_prefix) / Path(image_name)).replace("\\", "/")
        replacements[image_name] = scoped_name
        prepared_images.append({"name": scoped_name, "image": image_data})

    return replacements, prepared_images


def cleanup_input_files(filepaths: list[str]) -> None:
    input_root = Path(COMFY_INPUT_DIR).resolve()

    for filepath in filepaths:
        path = Path(filepath)
        try:
            if path.exists():
                path.unlink()
        except OSError:
            continue

    for filepath in filepaths:
        parent = Path(filepath).parent
        while parent != input_root and parent.exists():
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent


async def wait_for_history(
    session: aiohttp.ClientSession,
    target_node: str,
    prompt_id: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    fail_count = 0

    while True:
        if asyncio.get_running_loop().time() > deadline:
            raise TimeoutError("Local ComfyUI render timed out.")

        try:
            async with session.get(f"http://{target_node}/history/{prompt_id}") as resp:
                history_data = await resp.json()
        except Exception:
            fail_count += 1
            if fail_count > 5:
                raise RuntimeError(f"Local ComfyUI node {target_node} is unavailable.")
            await asyncio.sleep(2)
            continue

        if prompt_id in history_data:
            return history_data[prompt_id]

        await asyncio.sleep(2)


def remember_pod_submit_files(prompt_id: str, filepaths: list[str]) -> None:
    POD_SUBMIT_INPUT_FILES[prompt_id] = list(filepaths)


def cleanup_tracked_pod_submit_files(prompt_id: str) -> None:
    filepaths = POD_SUBMIT_INPUT_FILES.pop(prompt_id, [])
    if filepaths:
        cleanup_input_files(filepaths)


async def fetch_history_once(
    session: aiohttp.ClientSession,
    target_node: str,
    prompt_id: str,
) -> dict[str, Any] | None:
    async with session.get(f"http://{target_node}/history/{prompt_id}") as response:
        history_data = await response.json()

    if prompt_id in history_data:
        return history_data[prompt_id]

    return None


def build_pod_output_payload(history_entry: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    entries = collect_output_entries(history_entry.get("outputs", {}))
    output: dict[str, list[dict[str, str]]] = {"images": [], "videos": []}

    for entry in entries:
        media_type = guess_media_type(entry["filename"], entry["media_kind"])
        query = urlencode(
            {
                "filename": entry["filename"],
                "subfolder": entry.get("subfolder", ""),
                "media_kind": entry["media_kind"],
            }
        )
        download_query = urlencode(
            {
                "filename": entry["filename"],
                "subfolder": entry.get("subfolder", ""),
                "media_kind": entry["media_kind"],
                "download": "1",
            }
        )
        payload = {
            "filename": entry["filename"],
            "subfolder": entry.get("subfolder", ""),
            "media_type": media_type,
            "url": f"/api/comfy-output?{query}",
            "download_url": f"/api/comfy-output?{download_query}",
        }
        collection = "images" if entry["media_kind"] == "image" else "videos"
        output[collection].append(payload)

    return {key: value for key, value in output.items() if value}


@app.get("/", response_class=FileResponse)
async def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/comfy-output")
async def get_comfy_output(
    filename: str,
    subfolder: str = "",
    media_kind: str = "video",
    download: bool = False,
) -> FileResponse:
    try:
        output_path = build_output_path(
            os.environ.get("COMFY_OUTPUT_DIR", "/comfyui/output"),
            {
                "filename": filename,
                "subfolder": subfolder,
                "media_kind": media_kind,
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Generated output file not found.")

    media_type = guess_media_type(filename, media_kind)
    return FileResponse(
        output_path,
        media_type=media_type,
        filename=filename if download else None,
    )


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
        "run_mode": get_run_mode(),
        "submission_mode": get_submission_mode(),
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


@app.post("/api/pod-submit")
async def submit_payload_in_pod(request: PodSubmitRequest) -> dict[str, object]:
    workflow_input = request.payload.get("input", {})
    workflow = workflow_input.get("workflow")
    images = workflow_input.get("images")
    if not isinstance(workflow, dict):
        raise HTTPException(
            status_code=400,
            detail="Payload must include input.workflow for pod submission.",
        )

    try:
        name_map, prepared_images = prepare_pod_images(images)
        prepared_workflow = apply_input_filename_map(workflow, name_map)
        written_input_files = write_input_images(COMFY_INPUT_DIR, prepared_images)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        target_node = get_pod_submit_node()
    except RuntimeError as exc:
        cleanup_input_files(written_input_files)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    timeout = aiohttp.ClientTimeout(total=request.timeout_seconds)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                f"http://{target_node}/prompt",
                json={"prompt": prepared_workflow},
            ) as response:
                raw_body = await response.text()
                try:
                    prompt_response = json.loads(raw_body)
                except json.JSONDecodeError:
                    prompt_response = {}
                prompt_id = prompt_response.get("prompt_id")
                if response.status >= 400 or not prompt_id:
                    detail = "Local ComfyUI rejected the workflow submit."
                    if isinstance(prompt_response, dict) and prompt_response:
                        detail = prompt_response.get("message") or json.dumps(
                            prompt_response
                        )
                    elif raw_body.strip():
                        detail = raw_body.strip()
                    raise HTTPException(
                        status_code=502,
                        detail=detail,
                    )
        remember_pod_submit_files(prompt_id, written_input_files)
        return {
            "ok": True,
            "status_code": 202,
            "content_type": "application/json",
            "response_json": {
                "prompt_id": prompt_id,
                "node_used": target_node,
                "status": "queued",
            },
            "response_text": None,
        }
    except TimeoutError as exc:
        cleanup_input_files(written_input_files)
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except aiohttp.ClientError as exc:
        cleanup_input_files(written_input_files)
        raise HTTPException(
            status_code=502,
            detail=f"Local ComfyUI request failed: {exc}",
        ) from exc
    except HTTPException:
        cleanup_input_files(written_input_files)
        raise
    except Exception:
        cleanup_input_files(written_input_files)
        raise


@app.get("/api/pod-submit/{prompt_id}")
async def get_pod_submit_status(
    prompt_id: str,
    node: str = "",
) -> dict[str, object]:
    node_value = node.strip()
    try:
        target_node = normalize_node_host(node_value) if node_value else get_pod_submit_node()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    timeout = aiohttp.ClientTimeout(total=10)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            history_entry = await fetch_history_once(session, target_node, prompt_id)
    except aiohttp.ClientError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Local ComfyUI status request failed: {exc}",
        ) from exc

    if history_entry is None:
        return {
            "ok": True,
            "status_code": 202,
            "content_type": "application/json",
            "response_json": {
                "prompt_id": prompt_id,
                "node_used": target_node,
                "status": "running",
            },
            "response_text": None,
        }

    cleanup_tracked_pod_submit_files(prompt_id)
    return {
        "ok": True,
        "status_code": 200,
        "content_type": "application/json",
        "response_json": {
            "prompt_id": prompt_id,
            "node_used": target_node,
            "status": "completed",
            "output": build_pod_output_payload(history_entry),
        },
        "response_text": None,
    }
