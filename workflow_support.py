from __future__ import annotations

import base64
import binascii
import copy
import hashlib
import json
import mimetypes
from pathlib import Path
from typing import Any

OUTPUT_KEYS = {
    "images": "image",
    "videos": "video",
    "gifs": "video",
}


def is_workflow_job(job_input: dict[str, Any]) -> bool:
    return isinstance(job_input.get("workflow"), dict)


def build_workflow_cache_key(
    workflow: dict[str, Any], images: list[dict[str, str]] | None
) -> str:
    normalized = {"workflow": workflow, "images": images or []}
    payload = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def decode_base64_data(data: str) -> bytes:
    if "," in data and data.split(",", 1)[0].endswith(";base64"):
        data = data.split(",", 1)[1]

    try:
        return base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Invalid base64 image payload.") from exc


def safe_input_path(base_dir: str, image_name: str) -> Path:
    relative_path = Path(image_name)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise ValueError("Input image name must be a safe relative path.")

    target = (Path(base_dir) / relative_path).resolve()
    root = Path(base_dir).resolve()
    if root not in target.parents and target != root:
        raise ValueError("Input image path escapes COMFY_INPUT_DIR.")

    return target


def write_input_images(
    base_dir: str, images: list[dict[str, str]] | None
) -> list[str]:
    if not images:
        return []

    written_files: list[str] = []
    for image in images:
        name = image.get("name")
        data = image.get("image")
        if not name or not data:
            raise ValueError(
                "'images' must be a list of objects with 'name' and 'image' keys."
            )

        target = safe_input_path(base_dir, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(decode_base64_data(data))
        written_files.append(str(target))

    return written_files


def apply_input_filename_map(
    workflow: dict[str, Any], replacements: dict[str, str]
) -> dict[str, Any]:
    def _replace(value: Any) -> Any:
        if isinstance(value, str):
            return replacements.get(value, value)
        if isinstance(value, list):
            return [_replace(item) for item in value]
        if isinstance(value, dict):
            return {key: _replace(item) for key, item in value.items()}
        return value

    return _replace(copy.deepcopy(workflow))


def collect_output_entries(outputs: dict[str, Any]) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []

    for node_output in outputs.values():
        if not isinstance(node_output, dict):
            continue

        for output_key, media_kind in OUTPUT_KEYS.items():
            files = node_output.get(output_key, [])
            if not isinstance(files, list):
                continue

            for file_info in files:
                filename = file_info.get("filename")
                if not filename:
                    continue

                entries.append(
                    {
                        "filename": filename,
                        "subfolder": file_info.get("subfolder", ""),
                        "media_kind": media_kind,
                    }
                )

    return entries


def build_output_path(base_dir: str, entry: dict[str, str]) -> Path:
    subfolder = entry.get("subfolder") or ""
    target = (Path(base_dir) / subfolder / entry["filename"]).resolve()
    root = Path(base_dir).resolve()
    if root not in target.parents and target != root:
        raise ValueError("Output path escapes COMFY_OUTPUT_DIR.")
    return target


def guess_media_type(filename: str, media_kind: str) -> str:
    guessed, _ = mimetypes.guess_type(filename)
    if guessed:
        return guessed
    return "image/png" if media_kind == "image" else "video/mp4"
