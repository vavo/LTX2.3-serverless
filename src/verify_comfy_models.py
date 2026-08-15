#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from collections.abc import Iterable


REQUIRED_MODELS = {
    "diffusion_models": {
        "ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors",
    },
    "text_encoders": {
        "gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors",
    },
    "vae": {
        "ltx-2.5-video-vae-bf16.safetensors",
        "ltx-2.5-audio-vae-bf16.safetensors",
    },
    "latent_upscale_models": {
        "ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors",
    },
}
PROMPT_ENHANCER = "gemma4_e2b_it_bf16.safetensors"


def normalize_model_names(payload: object) -> set[str]:
    if not isinstance(payload, list):
        raise ValueError("expected a JSON list")

    names = set()
    for item in payload:
        if not isinstance(item, str):
            raise ValueError("expected every model entry to be a string")
        names.add(item.replace("\\", "/"))
    return names


def model_is_visible(visible_models: Iterable[str], expected: str) -> bool:
    return any(
        model == expected or model.endswith(f"/{expected}")
        for model in visible_models
    )


def missing_models(
    listings: dict[str, set[str]], *, require_prompt_enhancer: bool
) -> dict[str, list[str]]:
    expected_by_folder = {
        folder: set(models) for folder, models in REQUIRED_MODELS.items()
    }
    if require_prompt_enhancer:
        expected_by_folder["text_encoders"].add(PROMPT_ENHANCER)

    missing = {}
    for folder, expected_models in expected_by_folder.items():
        visible_models = listings.get(folder, set())
        missing_in_folder = sorted(
            model
            for model in expected_models
            if not model_is_visible(visible_models, model)
        )
        if missing_in_folder:
            missing[folder] = missing_in_folder
    return missing


def fetch_listing(server: str, folder: str, timeout: float) -> set[str]:
    url = f"{server.rstrip('/')}/models/{folder}"
    with urllib.request.urlopen(url, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"{url} returned HTTP {response.status}")
        return normalize_model_names(json.load(response))


def verify_model_discovery(
    server: str, *, timeout: float, require_prompt_enhancer: bool
) -> None:
    deadline = time.monotonic() + timeout
    last_error = "ComfyUI did not become ready"

    while time.monotonic() < deadline:
        try:
            listings = {
                folder: fetch_listing(server, folder, min(5.0, timeout))
                for folder in REQUIRED_MODELS
            }
            missing = missing_models(
                listings, require_prompt_enhancer=require_prompt_enhancer
            )
            if not missing:
                counts = ", ".join(
                    f"{folder}={len(models)}"
                    for folder, models in listings.items()
                )
                print(f"worker-comfyui: ComfyUI model discovery verified ({counts})")
                return
            last_error = f"required models are not visible: {json.dumps(missing)}"
        except (
            json.JSONDecodeError,
            OSError,
            RuntimeError,
            urllib.error.URLError,
            ValueError,
        ) as exc:
            last_error = str(exc)

        time.sleep(2)

    raise SystemExit(
        f"worker-comfyui: ComfyUI model discovery failed after {timeout:g}s: "
        f"{last_error}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify required LTX 2.5 models through ComfyUI's live API."
    )
    parser.add_argument("--server", default="http://127.0.0.1:8188")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--require-prompt-enhancer", action="store_true")
    args = parser.parse_args()

    verify_model_discovery(
        args.server,
        timeout=args.timeout,
        require_prompt_enhancer=args.require_prompt_enhancer,
    )


if __name__ == "__main__":
    main()
