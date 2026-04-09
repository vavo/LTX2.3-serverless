# LTX2.3 Serverless Worker

> [ComfyUI](https://github.com/comfyanonymous/ComfyUI) + [LTX 2.3](https://huggingface.co/Lightricks/LTX-2.3) as a serverless video inference worker on [RunPod](https://www.runpod.io/)

<p align="center">
  <img src="assets/worker_sitting_in_comfy_chair.jpg" title="Worker sitting in comfy chair" />
</p>

[![RunPod](https://api.runpod.io/badge/runpod-workers/worker-comfyui)](https://www.runpod.io/console/hub/runpod-workers/worker-comfyui)

---

This project is a RunPod serverless template for LTX 2.3 video inference on top of the generic ComfyUI worker pattern. It is tuned for persistent `/workspace` state so ComfyUI, the Python venv, caches, custom nodes, and downloaded model assets can survive worker churn instead of being re-fetched every time RunPod decides to rediscover entropy.

## Table of Contents

- [Quickstart](#quickstart)
- [Available Docker Images](#available-docker-images)
- [API Specification](#api-specification)
- [Usage](#usage)
- [Getting the Workflow JSON](#getting-the-workflow-json)
- [Further Documentation](#further-documentation)

---

## Quickstart

1.  Build or use one of the LTX-oriented image targets from [docker-bake.hcl](./docker-bake.hcl), preferably `ltx2-3-distilled` for CUDA 12.8 or `ltx2-3-distilled-cuda13` if you are specifically targeting newer Blackwell-friendly hosts.
2.  Attach a RunPod network volume so `/workspace` is persistent across worker boots.
3.  Deploy the image as a serverless endpoint and keep active workers at `0` unless you enjoy paying for idle silicon.
4.  Export an LTX workflow from ComfyUI using `Workflow > Export (API)`.
5.  Send the workflow to `/run` or `/runsync` as described below.

## Available Docker Images

Key image targets in this repository:

- **`<repo>:<version>-ltx2.3-distilled-cu128`**: CUDA 12.8 base, latest ComfyUI, official `ComfyUI-LTXVideo` nodes, LTX 2.3 distilled checkpoint preloaded into persistent storage on first boot.
- **`<repo>:<version>-ltx2.3-distilled-fp8-cu128`**: Same as above, but with the FP8 distilled checkpoint for lower VRAM pressure.
- **`<repo>:<version>-ltx2.3-distilled-cu130`**: Experimental CUDA 13 image for newer Blackwell-oriented stacks. This uses PyTorch's `cu130` wheels, which currently start at 2.9 rather than 2.8.
- **`<repo>:<version>-base-cuda12.8.1`**: Clean CUDA 12.8 ComfyUI base for custom LTX or non-LTX builds.
- **`<repo>:<version>-base-cuda13.0`**: Clean CUDA 13 base for newer Nvidia hosts where you want to bring your own workflow, nodes, and model strategy.

The repository still carries the generic image targets from upstream, but the useful ones for this template are the LTX 2.3 and modern CUDA variants.

## LTX Notes

- Official LTX guidance for ComfyUI is to install `ComfyUI-LTXVideo` and let the nodes auto-download required assets on first use.
- This worker can also preload the main LTX 2.3 checkpoint at boot via `LTX23_PRELOAD_VARIANT`, with files landing under the persistent model root on `/workspace`.
- If `LTX23_PRELOAD_UPSCALERS=true`, the worker also preloads the official LTX spatial/temporal upscalers into `models/latent_upscale_models` and the distilled LoRA into `models/loras` for the two-stage distilled path.
- The current default LTX preload choices are `distilled`, `dev`, `distilled-fp8`, and `dev-fp8`.
- A network volume is effectively mandatory here unless you want every cold worker to rediscover the same multi-GB files like it has short-term memory loss.

## GPU Baseline

- CUDA 12.8 is the default target for this repo.
- CUDA 13 is provided as an experimental track for Blackwell-era deployments.
- LTX's own ComfyUI documentation recommends a CUDA-capable GPU with 32GB+ VRAM and 100GB+ free disk for a comfortable setup.

## API Specification

The worker exposes standard RunPod serverless endpoints (`/run`, `/runsync`, `/health`). By default, images are returned as base64 strings. You can configure the worker to upload images to an S3 bucket instead by setting specific environment variables (see [Configuration Guide](docs/configuration.md)).

Use the `/runsync` endpoint for synchronous requests that wait for the job to complete and return the result directly. Use the `/run` endpoint for asynchronous requests that return immediately with a job ID; you'll need to poll the `/status` endpoint separately to get the result.

### Input

```json
{
  "input": {
    "workflow": {
      "6": {
        "inputs": {
          "text": "a ball on the table",
          "clip": ["30", 1]
        },
        "class_type": "CLIPTextEncode",
        "_meta": {
          "title": "CLIP Text Encode (Positive Prompt)"
        }
      }
    },
    "images": [
      {
        "name": "input_image_1.png",
        "image": "data:image/png;base64,iVBOR..."
      }
    ]
  }
}
```

The following tables describe the fields within the `input` object:

| Field Path                | Type   | Required | Description                                                                                                                                |
| ------------------------- | ------ | -------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `input`                   | Object | Yes      | Top-level object containing request data.                                                                                                  |
| `input.workflow`          | Object | Yes      | The ComfyUI workflow exported in the [required format](#getting-the-workflow-json).                                                        |
| `input.images`            | Array  | No       | Optional array of input images. Each image is uploaded to ComfyUI's `input` directory and can be referenced by its `name` in the workflow. |
| `input.comfy_org_api_key` | String | No       | Optional per-request Comfy.org API key for API Nodes. Overrides the `COMFY_ORG_API_KEY` environment variable if both are set.              |

#### `input.images` Object

Each object within the `input.images` array must contain:

| Field Name | Type   | Required | Description                                                                                                                       |
| ---------- | ------ | -------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `name`     | String | Yes      | Filename used to reference the image in the workflow (e.g., via a "Load Image" node). Must be unique within the array.            |
| `image`    | String | Yes      | Base64 encoded string of the image. A data URI prefix (e.g., `data:image/png;base64,`) is optional and will be handled correctly. |

> [!NOTE]
>
> **Size Limits:** RunPod endpoints have request size limits (e.g., 10MB for `/run`, 20MB for `/runsync`). Large base64 input images can exceed these limits. See [RunPod Docs](https://docs.runpod.io/docs/serverless-endpoint-urls).

### Output

> [!WARNING]
>
> **Breaking Change in Output Format (5.0.0+)**
>
> Versions `< 5.0.0` returned the primary image data (S3 URL or base64 string) directly within an `output.message` field.
> Starting with `5.0.0`, the output format has changed significantly, see below

```json
{
  "id": "sync-uuid-string",
  "status": "COMPLETED",
  "output": {
    "images": [
      {
        "filename": "ComfyUI_00001_.png",
        "type": "base64",
        "data": "iVBORw0KGgoAAAANSUhEUg..."
      }
    ]
  },
  "delayTime": 123,
  "executionTime": 4567
}
```

| Field Path      | Type             | Required | Description                                                                                                 |
| --------------- | ---------------- | -------- | ----------------------------------------------------------------------------------------------------------- |
| `output`        | Object           | Yes      | Top-level object containing the results of the job execution.                                               |
| `output.images` | Array of Objects | No       | Present if the workflow generated images. Contains a list of objects, each representing one output image.   |
| `output.errors` | Array of Strings | No       | Present if non-fatal errors or warnings occurred during processing (e.g., S3 upload failure, missing data). |

#### `output.images`

Each object in the `output.images` array has the following structure:

| Field Name | Type   | Description                                                                                     |
| ---------- | ------ | ----------------------------------------------------------------------------------------------- |
| `filename` | String | The original filename assigned by ComfyUI during generation.                                    |
| `type`     | String | Indicates the format of the data. Either `"base64"` or `"s3_url"` (if S3 upload is configured). |
| `data`     | String | Contains either the base64 encoded image string or the S3 URL for the uploaded image file.      |

> [!NOTE]
> The `output.images` field provides a list of all generated images (excluding temporary ones).
>
> - If S3 upload is **not** configured (default), `type` will be `"base64"` and `data` will contain the base64 encoded image string.
> - If S3 upload **is** configured, `type` will be `"s3_url"` and `data` will contain the S3 URL. See the [Configuration Guide](docs/configuration.md#example-s3-response) for an S3 example response.
> - Clients interacting with the API need to handle this list-based structure under `output.images`.

## Usage

To interact with your deployed RunPod endpoint:

1.  **Get API Key:** Generate a key in RunPod [User Settings](https://www.runpod.io/console/serverless/user/settings) (`API Keys` section).
2.  **Get Endpoint ID:** Find your endpoint ID on the [Serverless Endpoints](https://www.runpod.io/console/serverless/user/endpoints) page or on the `Overview` page of your endpoint.

### Generate Image (Sync Example)

Send a workflow to the `/runsync` endpoint (waits for completion). Replace `<api_key>` and `<endpoint_id>`. The `-d` value should contain the [JSON input described above](#input).

```bash
curl -X POST \
  -H "Authorization: Bearer <api_key>" \
  -H "Content-Type: application/json" \
  -d '{"input":{"workflow":{... your workflow JSON ...}}}' \
  https://api.runpod.ai/v2/<endpoint_id>/runsync
```

You can also use the `/run` endpoint for asynchronous jobs and then poll the `/status` to see when the job is done. Or you [add a `webhook` into your request](https://docs.runpod.io/serverless/endpoints/send-requests#webhook-notifications) to be notified when the job is done.

Refer to [`test_input.json`](./test_input.json) for a complete input example.

## Getting the Workflow JSON

To get the correct `workflow` JSON for the API:

1.  Open ComfyUI in your browser.
2.  In the top navigation, select `Workflow > Export (API)`
3.  A `workflow.json` file will be downloaded. Use the content of this file as the value for the `input.workflow` field in your API requests.

## SSH Access

To enable SSH access to the worker, set the `PUBLIC_KEY` environment variable to your SSH public key. The worker will start an SSH server automatically. Make sure to expose **port 22** in your RunPod template so you can connect.

## Further Documentation

- **[Deployment Guide](docs/deployment.md):** Detailed steps for deploying on RunPod.
- **[Configuration Guide](docs/configuration.md):** Full list of environment variables (including S3 setup).
- **[Customization Guide](docs/customization.md):** Adding custom models and nodes (Network Volumes, Docker builds).
- **[Development Guide](docs/development.md):** Setting up a local environment for development & testing
- **[CI/CD Guide](docs/ci-cd.md):** Information about the automated Docker build and publish workflows.
- **[Acknowledgments](docs/acknowledgments.md):** Credits and thanks
