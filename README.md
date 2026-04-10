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
  - `<repo>:<version>-ltx2.3-distilled-cu128`
  - `<repo>:<version>-ltx2.3-distilled-fp8-cu128`
  - `<repo>:<version>-ltx2.3-distilled-cu130`
  - `<repo>:<version>-base-cuda12.8.1`
  - `<repo>:<version>-base-cuda13.0`
- Standard RunPod endpoints: `/run`, `/runsync`, `/health`.
- Input workflow JSON plus optional input images.
- Output handling for image outputs from ComfyUI.

### Not true yet

- This repo does **not** currently return video or audio artifacts in the API response.
- The handler currently collects `output.images` only. If your workflow emits `SaveVideo`, `CreateVideo`, audio, or other non-image outputs, those outputs are not returned by the API yet.
- There is no checked-in canonical LTX API sample workflow in the repo yet.

If you want proper video-file responses, that is a handler feature still waiting for its promotion.

## Why It Wins

LTX 2.3 is interesting. Rebuilding Comfy, reinstalling nodes, and redownloading weights on every serverless boot is not.

This repo optimizes the boring part:

- keep the expensive state on `/workspace`
- use a sane CUDA matrix for newer Nvidia cards
- make RunPod serverless usable for LTX workflows without turning deployment into a ritual

## Recommended Targets

| Target | Use Case |
| --- | --- |
| `ltx2-3-distilled` | Default target for CUDA 12.8 deployments |
| `ltx2-3-distilled-fp8` | Lower VRAM pressure with the FP8 distilled checkpoint |
| `ltx2-3-distilled-cuda13` | Experimental CUDA 13 path for newer Blackwell-oriented stacks |
| `base-cuda12-8-1` | Clean CUDA 12.8 base image for custom LTX builds |
| `base-cuda13-0` | Clean CUDA 13 base image for custom experimental builds |

## Hardware Baseline

- CUDA 12.8 is the default target in this repo.
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
6. Export your ComfyUI workflow with `Workflow > Export (API)`.
7. Send it to `/run` or `/runsync`.
8. If you scale beyond one worker on a shared network volume, the startup bootstrap now serializes ComfyUI/venv seeding with a shared lock under `/workspace/worker-comfyui/.bootstrap.lock`.

## API Contract Today

### Input

The worker accepts:

- `input.workflow`: required ComfyUI API workflow JSON
- `input.images`: optional list of base64-encoded input images
- `input.comfy_org_api_key`: optional per-request Comfy.org API key

### Output

The worker currently returns:

- `output.images[]` when the workflow produces image outputs
- optional `output.errors[]` for non-fatal warnings

Image entries look like this:

```json
{
  "filename": "ComfyUI_00001_.png",
  "type": "base64",
  "data": "iVBORw0KGgoAAAANSUhEUg..."
}
```

If S3 is configured, `type` becomes `s3_url`.

## Minimal Request Example

```bash
curl -X POST \
  -H "Authorization: Bearer <runpod_api_key>" \
  -H "Content-Type: application/json" \
  -d '{"input":{"workflow":{... your Comfy API workflow ...}}}' \
  https://api.runpod.ai/v2/<endpoint_id>/runsync
```

## Environment Variables That Matter

| Variable | What It Does |
| --- | --- |
| `PERSIST_WORKSPACE` | Persist ComfyUI, venv, caches, and downloaded assets on the network volume |
| `WORKSPACE_ROOT` | Override the detected persistent root |
| `WORKSPACE_STATE_ROOT` | Override where worker state lives inside the persistent root |
| `LTX23_PRELOAD_VARIANT` | Preload `distilled`, `dev`, `distilled-fp8`, or `dev-fp8` |
| `LTX23_PRELOAD_UPSCALERS` | Also preload the official LTX latent upscalers and distilled LoRA |
| `HUGGINGFACE_ACCESS_TOKEN` | Optional Hugging Face token for startup downloads |
| `COMFY_ORG_API_KEY` | Optional Comfy.org API key |
| `BUCKET_ENDPOINT_URL` | Enable S3 upload mode for image outputs |

The full list lives in [docs/configuration.md](./docs/configuration.md).

## Facts Worth Knowing

- On serverless, the volume is mounted at `/runpod-volume`, but the worker normalizes on `/workspace` internally by creating `/workspace -> /runpod-volume` when needed.
- The worker bootstraps persistent ComfyUI state under `/workspace/worker-comfyui`.
- Shared bootstrap seeding is guarded by `/workspace/worker-comfyui/.bootstrap.lock` so multiple workers do not try to initialize the same persisted venv at once.
- ComfyUI model directories are mapped from `/workspace/models/...` via `/comfyui/extra_model_paths.yaml`. On serverless that is the same storage as `/runpod-volume/models/...`.
- The current handler uses `/comfyui/input` and `/comfyui/output` by default.
- ComfyUI-Manager configuration lives at `/comfyui/user/default/ComfyUI-Manager/config.ini` unless `COMFYUI_MANAGER_CONFIG` overrides it.
- LTX image targets install `ComfyUI-LTXVideo` from Lightricks.
- The startup bootstrap can seed ComfyUI and the venv into persistent storage on first run.
- The current local `test_input.json` is legacy and not an LTX example.

## Docs

- [Deployment Guide](./docs/deployment.md)
- [Configuration Guide](./docs/configuration.md)
- [Customization Guide](./docs/customization.md)
- [Network Volumes](./docs/network-volumes.md)
- [Development Guide](./docs/development.md)
- [CI/CD Guide](./docs/ci-cd.md)
