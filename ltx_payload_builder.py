from __future__ import annotations

import copy
import json
import random
import re
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent
WORKFLOW_TEMPLATE_PATH = ROOT_DIR / "video_ltx2_3_i2v_API.json"

FPS = 24
SECONDS_MIN = 1.0
SECONDS_MAX = 10.0
SECONDS_STEP = 0.5

ASPECT_RATIOS: dict[str, dict[str, int]] = {
    "16:9": {"width": 1280, "height": 720},
    "9:16": {"width": 720, "height": 1280},
    "1:1": {"width": 1024, "height": 1024},
}

PROMPT_NODE = "267:266"
IMAGE_NODE = "269"
LENGTH_NODE = "267:225"
WIDTH_NODE = "267:257"
HEIGHT_NODE = "267:258"
FPS_NODE = "267:260"
PROMPT_OPTIMIZER_NODE = "267:274"
SEED_NODE_1 = "267:216"
SEED_NODE_2 = "267:237"

with WORKFLOW_TEMPLATE_PATH.open("r", encoding="utf-8") as template_file:
    WORKFLOW_TEMPLATE = json.load(template_file)


def seconds_to_frames(seconds: float) -> int:
    if seconds < SECONDS_MIN or seconds > SECONDS_MAX:
        raise ValueError(
            f"Duration must be between {SECONDS_MIN:g} and {SECONDS_MAX:g} seconds."
        )
    return int(round(seconds * FPS)) + 1


def sanitize_image_name(image_name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", image_name.strip())
    cleaned = cleaned.strip("._")
    return cleaned or "source-image.png"


def build_payload(
    *,
    prompt: str,
    seconds: float,
    aspect_ratio: str,
    image_name: str,
    image_data_url: str,
    optimize_prompt: bool,
    rng: random.Random | None = None,
) -> dict[str, Any]:
    prompt = prompt.strip()
    if not prompt:
        raise ValueError("Prompt is required.")

    if aspect_ratio not in ASPECT_RATIOS:
        raise ValueError(f"Unsupported aspect ratio: {aspect_ratio}")

    if not image_data_url.startswith("data:image/"):
        raise ValueError("Source image must be provided as a data URL.")

    dimensions = ASPECT_RATIOS[aspect_ratio]
    frames = seconds_to_frames(seconds)
    normalized_image_name = sanitize_image_name(image_name)
    random_source = rng or random.SystemRandom()

    workflow = copy.deepcopy(WORKFLOW_TEMPLATE)
    workflow[PROMPT_NODE]["inputs"]["value"] = prompt
    workflow[IMAGE_NODE]["inputs"]["image"] = normalized_image_name
    workflow[LENGTH_NODE]["inputs"]["value"] = frames
    workflow[WIDTH_NODE]["inputs"]["value"] = dimensions["width"]
    workflow[HEIGHT_NODE]["inputs"]["value"] = dimensions["height"]
    workflow[FPS_NODE]["inputs"]["value"] = FPS
    workflow[PROMPT_OPTIMIZER_NODE]["inputs"]["sampling_mode"] = (
        "on" if optimize_prompt else "off"
    )
    workflow[PROMPT_OPTIMIZER_NODE]["inputs"]["sampling_mode.seed"] = random_source.randrange(
        1, 10**9
    )
    workflow[SEED_NODE_1]["inputs"]["noise_seed"] = random_source.randrange(1, 10**15)
    workflow[SEED_NODE_2]["inputs"]["noise_seed"] = random_source.randrange(1, 10**15)

    return {
        "input": {
            "workflow": workflow,
            "images": [
                {
                    "name": normalized_image_name,
                    "image": image_data_url,
                }
            ],
        }
    }
