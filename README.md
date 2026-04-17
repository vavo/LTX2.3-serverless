# LTX2.3 Serverless Worker

Serverless LTX 2.3, minus the goldfish-memory cold start.

This repo turns ComfyUI + LTX 2.3 into a RunPod serverless template that keeps its brain on `/workspace`: Comfy install, Python venv, caches, and downloaded model assets survive worker churn instead of being painfully rediscovered on every boot.

Less boot drama. More actual inference.

<p align="center">
  <img src="assets/worker_sitting_in_comfy_chair.jpg" title="Worker sitting in comfy chair" />
</p>

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

For detailed deployment steps, see [Deployment Guide](docs/deployment.md).

## Available Docker Images

| Target | Use Case |
| --- | --- |
| `base` | Default clean CUDA 12.8 / cu128 base image |
| `ltx2-3-distilled` | Default target for CUDA 12.8 deployments |
| `ltx2-3-distilled-fp8` | Lower VRAM pressure with the FP8 distilled checkpoint |
| `ltx2-3-distilled-cuda13` | Experimental CUDA 13 path for newer Blackwell-oriented stacks |
| `base-cuda12-8-1` | Explicit CUDA 12.8 base image alias for custom LTX builds |
| `base-cuda13-0` | Clean CUDA 13 base image for custom experimental builds |

Example image tags (replace `<repo>` and `<version>` with your values):
- `<repo>:<version>-base`
- `<repo>:<version>-ltx2.3-distilled-cu128`
- `<repo>:<version>-ltx2.3-distilled-fp8-cu128`
- `<repo>:<version>-ltx2.3-distilled-cu130`

Hardware requirements: 32GB+ VRAM and 100GB+ free disk recommended. See [Deployment Guide](docs/deployment.md) for details.

## Essential Configuration

### Recommended First Boot Env

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

This preloads the main LTX checkpoint plus the official latent upscalers and distilled LoRA into persistent storage. Some secondary assets may still download on first render.

For the full list of environment variables, see [Configuration Guide](docs/configuration.md).

## Runtime Modes

The container supports explicit runtime modes via `RUN_MODE`:

- `worker`: default serverless worker behavior, starts ComfyUI, the frontend, and `runpod.serverless.start(...)`
- `local-api`: starts ComfyUI, the frontend, and the local RunPod-style API on port `8000`
- `pod`: starts ComfyUI and the frontend only, without the serverless handler

If `RUN_MODE` is unset, the image stays backward compatible:
- `SERVE_API_LOCALLY=true` maps to `RUN_MODE=local-api`
- otherwise it falls back to `RUN_MODE=worker`

## API Specification

### Input

The worker accepts:

- `input.workflow`: required ComfyUI API workflow JSON
- `input.images`: optional list of base64-encoded input images
- `input.priority`: optional queue hint, `standard` by default and `vip` for the legacy custom path

### Output

The worker returns:

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

If S3 is configured, `type` becomes `url` and `data` is a presigned URL. See [Configuration Guide](docs/configuration.md#aws-s3-upload-configuration) for S3 setup.

### Minimal Request Example

```bash
curl -X POST \
  -H "Authorization: Bearer <runpod_api_key>" \
  -H "Content-Type: application/json" \
  -d '{"input":{"workflow":{... your Comfy API workflow ...},"images":[{"name":"source.png","image":"data:image/png;base64,..." }]}}' \
  https://api.runpod.ai/v2/<endpoint_id>/runsync
```

## Getting the ComfyUI Workflow JSON

To get your workflow JSON:

1. Open your ComfyUI instance
2. Enable "Dev mode Options" in settings
3. Build your workflow
4. Click `Workflow > Export (API)`
5. Use the exported JSON in your API request

A checked-in LTX image-to-video API workflow is available at [`video_ltx2_3_i2v_API.json`](./video_ltx2_3_i2v_API.json).

## Legacy Compatibility

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

## Documentation

- [Deployment Guide](docs/deployment.md) - Detailed RunPod template/endpoint creation, GPU recommendations
- [Configuration Guide](docs/configuration.md) - Comprehensive list and explanation of all environment variables
- [Customization Guide](docs/customization.md) - In-depth guide on using Network Volumes and building custom Docker images
- [Network Volumes & Model Paths](docs/network-volumes.md) - How to use network volumes and debug model detection issues
- [Development Guide](docs/development.md) - Instructions for local setup, running tests, using docker-compose
- [CI/CD Guide](docs/ci-cd.md) - Explanation of the GitHub Actions workflows for Docker Hub deployment
- [Conventions](docs/conventions.md) - Project conventions and rules for development
- [Acknowledgments](docs/acknowledgments.md) - Credits and thanks
