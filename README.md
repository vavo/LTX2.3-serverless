# LTX2.3 Serverless Worker

Serverless LTX 2.3, minus the goldfish-memory cold start.

This repo turns ComfyUI + LTX 2.3 into a RunPod serverless template that keeps its brain on `/workspace`: Comfy install, Python venv, caches, and downloaded model assets survive worker churn instead of being painfully rediscovered on every boot.

Less boot drama. More actual inference.

<p align="center">
  <img src="assets/worker_sitting_in_comfy_chair.jpg" title="Worker sitting in comfy chair" />
</p>

## Why This Exists

- Builds LTX-oriented Docker targets for RunPod serverless.
- Uses Python 3.12 and a persistent `/workspace` bootstrap for ComfyUI, the venv, and caches.
- Installs the official `ComfyUI-LTXVideo` nodes in the LTX image targets.
- Targets CUDA 12.8 by default and CUDA 13 experimentally for newer Blackwell-oriented deployments.
- Can preload the main LTX 2.3 checkpoint at startup into persistent storage.
- Can also preload the official latent upscalers and distilled LoRA for the two-stage distilled path.

## Current Truth

### Works today

- RunPod serverless worker around ComfyUI.
- Persistent state on `/workspace` via network volume.
- LTX-focused image targets:
  - `<repo>:<version>-base`
  - `<repo>:<version>-ltx2.3-distilled-cu128`
  - `<repo>:<version>-ltx2.3-distilled-fp8-cu128`
  - `<repo>:<version>-ltx2.3-distilled-cu130`
  - `<repo>:<version>-base-cuda12.8.1`
  - `<repo>:<version>-base-cuda13.0`
- Standard RunPod endpoints: `/run`, `/runsync`, `/health`.
- Input workflow JSON plus optional input images.
- Output handling for image and video artifacts from ComfyUI.
- Checked-in LTX image-to-video API workflow at [`video_ltx2_3_i2v_API.json`](./video_ltx2_3_i2v_API.json).

### Compatibility baggage

- The worker still accepts the older custom request shape based on `input.prompt`, `input.image_url`, and `input.api_key`.
- New integrations should use the workflow contract below instead of building against the legacy compatibility path.
- The worker currently returns image and video files only. Audio-only artifacts are still not exposed as a first-class output collection.

## Why It Wins

LTX 2.3 is interesting. Rebuilding Comfy, reinstalling nodes, and redownloading weights on every serverless boot is not.

This repo optimizes the boring part:

- keep the expensive state on `/workspace`
- use a sane CUDA matrix for newer Nvidia cards
- make RunPod serverless usable for LTX workflows without turning deployment into a ritual

## Recommended Targets

| Target | Use Case |
| --- | --- |
| `base` | Default clean CUDA 12.8 / cu128 base image |
| `ltx2-3-distilled` | Default target for CUDA 12.8 deployments |
| `ltx2-3-distilled-fp8` | Lower VRAM pressure with the FP8 distilled checkpoint |
| `ltx2-3-distilled-cuda13` | Experimental CUDA 13 path for newer Blackwell-oriented stacks |
| `base-cuda12-8-1` | Explicit CUDA 12.8 base image alias for custom LTX builds |
| `base-cuda13-0` | Clean CUDA 13 base image for custom experimental builds |

## Hardware Baseline

- CUDA 12.8 is the default target in this repo.
- Plain `docker build ...` and bake target `base` now default to CUDA 12.8.1 with the cu128 PyTorch wheel index.
- CUDA 13 is supported here as an experimental path.
- The LTX / ComfyUI docs recommend 32GB+ VRAM and 100GB+ free disk for a comfortable setup.
- For the CUDA 12.8 path, PyTorch 2.8+ is the intended floor.
- For the CUDA 13 path, official `cu130` wheels start at PyTorch 2.9+, so treat that lane accordingly.

## Quickstart

1. Build or publish one of the LTX image targets from [`docker-bake.hcl`](./docker-bake.hcl).
2. Create a RunPod serverless template that uses that image.
3. Attach a network volume so `/workspace` is persistent.
4. Deploy the endpoint with `Active Workers = 0` unless you enjoy paying for idle GPUs.
5. Set at least:
   - `PERSIST_WORKSPACE=true`
   - `LTX23_PRELOAD_VARIANT=distilled`
   - `LTX23_PRELOAD_UPSCALERS=true`
   - `HUGGINGFACE_ACCESS_TOKEN=<your_hf_read_token>`
6. Export your ComfyUI workflow with `Workflow > Export (API)`.
7. Send it to `/run` or `/runsync`.
8. If you scale beyond one worker on a shared network volume, the startup bootstrap now serializes ComfyUI/venv seeding with a shared lock under `/workspace/worker-comfyui/.bootstrap.lock`.

## Recommended First Boot Env

For a sane first boot on RunPod serverless, use:

```env
PERSIST_WORKSPACE=true
RUN_MODE=worker
COMFY_NODES=127.0.0.1:8188
LTX23_PRELOAD_VARIANT=distilled
LTX23_PRELOAD_UPSCALERS=true
HUGGINGFACE_ACCESS_TOKEN=hf_xxx
```

For a plain pod instead of a serverless worker:

```env
PERSIST_WORKSPACE=true
RUN_MODE=pod
LOCAL_COMFY_NODE=127.0.0.1:8188
LTX23_PRELOAD_VARIANT=distilled
LTX23_PRELOAD_UPSCALERS=true
HUGGINGFACE_ACCESS_TOKEN=hf_xxx
```

This preloads the main LTX checkpoint plus the official latent upscalers and distilled LoRA into persistent storage. Some secondary assets, especially Gemma and text-encoder weights used by `ComfyUI-LTXVideo`, may still download on first render through Hugging Face cache. Because apparently one startup path was not enough.

## Runtime Modes

The container now supports explicit runtime modes via `RUN_MODE`:

- `worker`: default serverless worker behavior, starts ComfyUI, the frontend, and `runpod.serverless.start(...)`
- `local-api`: starts ComfyUI, the frontend, and the local RunPod-style API on port `8000`
- `pod`: starts ComfyUI and the frontend only, without the serverless handler

If `RUN_MODE` is unset, the image stays backward compatible:

- `SERVE_API_LOCALLY=true` maps to `RUN_MODE=local-api`
- otherwise it falls back to `RUN_MODE=worker`

## API Contract Today

### Input

The worker accepts:

- `input.workflow`: required ComfyUI API workflow JSON
- `input.images`: optional list of base64-encoded input images
- `input.priority`: optional queue hint, `standard` by default and `vip` for the legacy custom path

### Output

The worker currently returns:

- `output.images[]` when the workflow produces image outputs
- `output.videos[]` when the workflow produces video outputs

Artifact entries look like this:

```json
{
  "filename": "LTX_2.3_i2v.mp4",
  "type": "base64",
  "data": "AAAAIGZ0eXBpc29tAAACAGlzb20uLi4=",
  "media_type": "video/mp4"
}
```

If S3 is configured, `type` becomes `url` and `data` is a presigned URL.

## Minimal Request Example

```bash
curl -X POST \
  -H "Authorization: Bearer <runpod_api_key>" \
  -H "Content-Type: application/json" \
  -d '{"input":{"workflow":{... your Comfy API workflow ...},"images":[{"name":"source.png","image":"data:image/png;base64,..." }]}}' \
  https://api.runpod.ai/v2/<endpoint_id>/runsync
```

## Legacy Compatibility Mode

The checked-in frontend and the primary docs target the workflow contract above.

The worker still accepts the older compatibility payload below for existing clients:

```json
{
  "input": {
    "api_key": "your-worker-secret",
    "prompt": "your prompt",
    "image_url": "https://example.com/source.png",
    "priority": "standard"
  }
}
```

Treat that mode as legacy. It exists so old callers do not explode on contact, not because it is the API you should build new things around.

## Environment Variables That Matter

| Variable | What It Does |
| --- | --- |
| `PERSIST_WORKSPACE` | Persist ComfyUI, venv, caches, and downloaded assets on the network volume |
| `WORKSPACE_ROOT` | Override the detected persistent root |
| `WORKSPACE_STATE_ROOT` | Override where worker state lives inside the persistent root |
| `LTX23_PRELOAD_VARIANT` | Preload `distilled`, `dev`, `distilled-fp8`, or `dev-fp8` |
| `LTX23_PRELOAD_UPSCALERS` | Also preload the official LTX latent upscalers and distilled LoRA |
| `LTX23_DOWNLOAD_BACKEND` | LTX preload download backend: `auto` (default), `hf_hub`, or `wget` |
| `HUGGINGFACE_ACCESS_TOKEN` | Optional Hugging Face token for startup downloads |
| `INDRO_API_KEY` | Secret expected only by the legacy custom prompt/image_url path |
| `REDIS_URL` | Redis connection for queue telemetry, rate limiting, dedupe, and circuit breaker state |
| `COMFY_NODES` | Comma-separated ComfyUI API hosts the worker can route jobs to |
| `LOCAL_COMFY_NODE` | Local ComfyUI host used by the bundled frontend when `RUN_MODE=pod` |
| `COMFY_INPUT_DIR` | Where uploaded workflow input files are staged before queueing |
| `COMFY_OUTPUT_DIR` | Where generated Comfy artifacts are read back from |
| `AWS_BUCKET_NAME` | Enable S3 upload mode for image and video outputs |
| `MAX_INLINE_VIDEO_MB` | Max inline base64 video size before the worker forces S3 or errors |
| `CACHE_TTL_SECONDS` | Deduped success-response cache retention |

The full list lives in [docs/configuration.md](./docs/configuration.md).

## Facts Worth Knowing

- On serverless, the volume is mounted at `/runpod-volume`, but the worker normalizes on `/workspace` internally by creating `/workspace -> /runpod-volume` when needed.
- The worker bootstraps persistent ComfyUI state under `/workspace/worker-comfyui`.
- Shared bootstrap seeding is guarded by `/workspace/worker-comfyui/.bootstrap.lock` so multiple workers do not try to initialize the same persisted venv at once.
- ComfyUI model directories are mapped from `/workspace/models/...` via `/comfyui/extra_model_paths.yaml`. On serverless that is the same storage as `/runpod-volume/models/...`.
- The current handler uses `/comfyui/input` and `/comfyui/output` by default.
- The local/container frontend auto-starts on port `7777` unless `LTX_FRONTEND_ENABLED=false`.
- For pod deployments, set `RUN_MODE=pod` so the container does not launch the serverless handler.
- ComfyUI-Manager is installed in the image by default, and its configuration lives at `/comfyui/user/default/ComfyUI-Manager/config.ini` unless `COMFYUI_MANAGER_CONFIG` overrides it.
- LTX image targets install `ComfyUI-LTXVideo` from Lightricks.
- The startup bootstrap can seed ComfyUI and the venv into persistent storage on first run.
- Uploaded workflow input images are staged under per-job subfolders inside `/comfyui/input` and cleaned up after execution.
- The current local `test_input.json` is legacy and not an LTX example.

## Docs

- [Deployment Guide](./docs/deployment.md)
- [Configuration Guide](./docs/configuration.md)
- [Customization Guide](./docs/customization.md)
- [Network Volumes](./docs/network-volumes.md)
- [Development Guide](./docs/development.md)
- [CI/CD Guide](./docs/ci-cd.md)
