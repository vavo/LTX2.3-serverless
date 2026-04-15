# Configuration

This document outlines the environment variables available for configuring the worker.

## General Configuration

| Environment Variable | Description                                                                                                                                                                                                                  | Default |
| -------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- |
| `REFRESH_WORKER`     | When `true`, the worker pod will stop after each completed job to ensure a clean state for the next job. See the [RunPod documentation](https://docs.runpod.io/docs/handler-additional-controls#refresh-worker) for details. | `false` |
| `RUN_MODE` | Container startup mode: `worker`, `local-api`, or `pod`. | `worker` |
| `SERVE_API_LOCALLY`  | Legacy compatibility flag. When `RUN_MODE` is unset and this is `true`, startup falls back to `local-api`. See the [Development Guide](development.md#local-api-simulation-using-docker-compose) for more details. | `false` |
| `PERSIST_WORKSPACE`  | When `true`, persist ComfyUI, the Python venv, caches, and downloaded assets under `/workspace` (which aliases `/runpod-volume` on serverless).                                                                            | `true`  |
| `WORKSPACE_ROOT`     | Override the detected persistent workspace root. Useful only if your mount layout differs from RunPod defaults.                                                                                                              | auto    |
| `WORKSPACE_STATE_ROOT` | Override the state directory inside the persistent workspace.                                                                                                                         | `/workspace/worker-comfyui` |
| `HUGGINGFACE_ACCESS_TOKEN` | Optional token used for startup downloads and other Hugging Face fetches. `HF_TOKEN` and `HUGGINGFACE_TOKEN` are also accepted aliases by the preload script.                 | –       |
| `LTX23_PRELOAD_VARIANT` | Optional LTX checkpoint preload at worker startup: `distilled`, `dev`, `distilled-fp8`, or `dev-fp8`.                                                                     | empty   |
| `LTX23_PRELOAD_UPSCALERS` | When `true`, also preload the official LTX latent upscalers and distilled LoRA for the two-stage path.                                                                  | `false` |
| `LTX23_DOWNLOAD_BACKEND` | LTX preload download backend: `auto` (prefer `huggingface_hub` + `hf_transfer`), `hf_hub`, or `wget`.                                                                   | `auto`  |
| `COMFYUI_MANAGER_CONFIG` | Override the ComfyUI-Manager `config.ini` path used by `comfy-manager-set-mode`.                                                                                             | `/comfyui/user/default/ComfyUI-Manager/config.ini` |
| `INDRO_API_KEY` | Secret checked only by the legacy custom `input.prompt` + `input.image_url` handler path. Workflow-mode jobs do not use it. | `dev_token_123` |
| `REDIS_URL` | Redis connection used for rate limiting, dedupe, job status, and circuit breaker state. | `redis://localhost:6379` |
| `COMFY_NODES` | Comma-separated ComfyUI API hosts that can accept `/prompt` and `/history` requests. | `127.0.0.1:8188` |
| `LOCAL_COMFY_NODE` | Local ComfyUI host used by the bundled frontend for pod-mode submits. | `127.0.0.1:8188` |
| `COMFY_INPUT_DIR` | Directory where workflow-mode uploaded input files are staged before queueing the workflow. | `/comfyui/input` |
| `COMFY_OUTPUT_DIR` | Directory where generated images and videos are read back from after completion. | `/comfyui/output` |
| `MAX_INLINE_VIDEO_MB` | Maximum inline base64 video size. Larger video responses require S3 or they fail. | `50` |
| `CACHE_TTL_SECONDS` | How long successful deduped responses stay cached in Redis. | `604800` |
| `AWS_BUCKET_NAME` | Enable S3 upload mode for generated image and video outputs. | – |
| `LTX_FRONTEND_ENABLED` | When `true`, starts the bundled FastAPI frontend inside the container on port `7777`. | `true` |

## Bootstrap Locking

When multiple workers share the same persisted `/workspace`, the bootstrap now uses a shared lock at `/workspace/worker-comfyui/.bootstrap.lock` while seeding the persisted ComfyUI root and Python virtualenv.

That prevents concurrent first-boot workers from trampling the same shared venv. If a worker dies while holding the lock, stale-lock cleanup will eventually remove it.

## Recommended First Boot

For the least annoying first worker boot on RunPod serverless, set:

```env
PERSIST_WORKSPACE=true
RUN_MODE=worker
COMFY_NODES=127.0.0.1:8188
LTX23_PRELOAD_VARIANT=distilled
LTX23_PRELOAD_UPSCALERS=true
HUGGINGFACE_ACCESS_TOKEN=hf_xxx
```

For a plain pod:

```env
PERSIST_WORKSPACE=true
RUN_MODE=pod
LOCAL_COMFY_NODE=127.0.0.1:8188
LTX23_PRELOAD_VARIANT=distilled
LTX23_PRELOAD_UPSCALERS=true
HUGGINGFACE_ACCESS_TOKEN=hf_xxx
```

That startup preload covers the main LTX checkpoint, the official latent upscalers, and the distilled LoRA. Some secondary weights used by `ComfyUI-LTXVideo`, such as Gemma or text encoders, can still download on first render into the persistent Hugging Face cache.

## Runtime Paths

With workspace persistence enabled, the worker uses these paths:

| Purpose | Path |
| ------- | ---- |
| Persistent root | `/workspace` |
| ComfyUI code and user config | `/workspace/worker-comfyui/comfyui` |
| Python virtualenv | `/workspace/worker-comfyui/venv` |
| Download and compiler caches | `/workspace/worker-comfyui/cache` |
| Shared bootstrap lock | `/workspace/worker-comfyui/.bootstrap.lock` |
| Shared model root | `/workspace/models` |
| Generated model-path config | `/comfyui/extra_model_paths.yaml` |
| Current handler input staging | `/comfyui/input` |
| Current handler output pickup | `/comfyui/output` |
| ComfyUI-Manager config | `/comfyui/user/default/ComfyUI-Manager/config.ini` |

On serverless, `/workspace` is the worker's internal alias for `/runpod-volume`.

## Logging Configuration

| Environment Variable   | Description                                                                                                                                                      | Default |
| ---------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- |
| `COMFY_LOG_LEVEL`      | Controls ComfyUI's internal logging verbosity. Options: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. Use `DEBUG` for troubleshooting, `INFO` for production. | `DEBUG` |
| `NETWORK_VOLUME_DEBUG` | Enable detailed network volume diagnostics in worker logs. Useful for debugging model path issues. See [Network Volumes & Model Paths](network-volumes.md).      | `false` |

## Debugging Configuration

| Environment Variable           | Description                                                                                                            | Default |
| ------------------------------ | ---------------------------------------------------------------------------------------------------------------------- | ------- |
| `WEBSOCKET_RECONNECT_ATTEMPTS` | Number of websocket reconnection attempts when connection drops during job execution.                                  | `5`     |
| `WEBSOCKET_RECONNECT_DELAY_S`  | Delay in seconds between websocket reconnection attempts.                                                              | `3`     |
| `WEBSOCKET_TRACE`              | Enable low-level websocket frame tracing for protocol debugging. Set to `true` only when diagnosing connection issues. | `false` |

## AWS S3 Upload Configuration

Configure these variables **only** if you want the worker to upload generated images and videos directly to an AWS S3 bucket. If these are not set, artifacts are returned inline as base64 when they fit inside the configured limits.

- **Prerequisites:**
  - An AWS S3 bucket in your desired region.
  - An AWS IAM user with programmatic access (Access Key ID and Secret Access Key).
  - Permissions attached to the IAM user allowing `s3:PutObject` (and potentially `s3:PutObjectAcl` if you need specific ACLs) on the target bucket.

| Environment Variable | Description | Example |
| -------------------- | ----------- | ------- |
| `AWS_BUCKET_NAME` | Bucket name used by the worker when uploading artifacts. **Must be set to enable S3 mode.** | `my-ltx-renders` |
| `AWS_ACCESS_KEY_ID` | AWS access key ID for the IAM principal that can write to the bucket. | `AKIAIOSFODNN7EXAMPLE` |
| `AWS_SECRET_ACCESS_KEY` | AWS secret access key for that IAM principal. | `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` |
| `AWS_DEFAULT_REGION` | AWS region used by the S3 client. | `eu-central-1` |

The current worker uploads directly with `boto3` and returns presigned URLs.

### Example S3 Response

If the S3 environment variables are correctly configured, a successful workflow response can look like this:

```json
{
  "status": "success",
  "output": {
    "videos": [
      {
        "filename": "LTX_2.3_i2v.mp4",
        "type": "url",
        "data": "https://example-bucket.s3.amazonaws.com/renders/job-123/00-LTX_2.3_i2v.mp4?...",
        "media_type": "video/mp4"
      }
    ]
  },
  "metadata": {
    "render_time_sec": 42.1,
    "node_used": "127.0.0.1:8188"
  },
  "cached": false
}
```

The `data` field contains a presigned URL to the uploaded artifact. The S3 object key includes the job ID and output index.
