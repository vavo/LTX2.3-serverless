# LTX 2.5 Serverless Worker

Blackwell-first LTX 2.5 inference on ComfyUI and RunPod, with persistent models, caches, ComfyUI, and Python environment under `/workspace`.

## Stack

- CUDA 13.0.2 primary; CUDA 12.8.1 secondary
- Ubuntu 24.04 base; CUDA user-space libraries supplied by the pinned PyTorch wheels
- PyTorch 2.11.0, torchvision 0.26.0, torchaudio 2.11.0
- ComfyUI v0.33.1 with built-in Manager 4.2.2
- Comfy CLI 1.16.0 and Hugging Face Hub CLI 1.27.0
- Official LTX 2.5 nodes and local image-to-video workflow
- Distilled INT8 ConvRot for Blackwell-efficient inference

## Quickstart

1. Accept the model terms on [Lightricks/LTX-2.5](https://huggingface.co/Lightricks/LTX-2.5).
2. Build and publish the `ltx2-5-distilled-int8` target from [`docker-bake.hcl`](./docker-bake.hcl):

```bash
docker buildx bake ltx2-5-distilled-int8 \
  --set 'ltx2-5-distilled-int8.tags=<registry>/<image>:<version>-ltx2.5-distilled-int8-cu130' \
  --push
```

3. Create a RunPod serverless template using that image and attach a network volume.
4. Set:

```env
PERSIST_WORKSPACE=true
RUN_MODE=worker
LTX25_PRELOAD_VARIANT=distilled-int8
LTX25_PRELOAD_PROMPT_ENHANCER=true
HUGGINGFACE_ACCESS_TOKEN=hf_xxx
```

5. Send the checked-in [LTX 2.5 I2V API workflow](./video_ltx2_5_i2v_API.json) to `/run` or `/runsync` using the [workflow request contract](#api-contract).

The model bootstrap downloads weights to the persistent model root. Model weights are never baked into Docker layers.

## Docker targets

| Target | CUDA | Model profile |
| --- | --- | --- |
| `base` | 13.0.2 | No startup preload |
| `base-cuda12-8-1` | 12.8.1 | No startup preload |
| `ltx2-5-distilled-int8` | 13.0.2 | Distilled INT8 ConvRot, recommended |
| `ltx2-5-distilled-int8-cu128` | 12.8.1 | Distilled INT8 ConvRot fallback |

All bake targets build for `linux/amd64`. For a direct Docker build, keep the platform explicit:

```bash
docker build --platform linux/amd64 --target base -t ltx25-worker:dev .
```

Image tags follow `<version>-ltx2.5-distilled-int8-cu130` and `<version>-ltx2.5-distilled-int8-cu128`.

## Runtime modes

- `worker`: ComfyUI, bundled frontend, and RunPod serverless handler
- `local-api`: ComfyUI, frontend, and local RunPod-compatible API on port `8000`
- `pod`: ComfyUI and frontend without the serverless handler

The frontend is served on port `7777`; ComfyUI uses `8188`.

## API contract

The preferred request shape is below. `workflow` must be an API-format ComfyUI workflow; `{}` is only a structural placeholder.

```json
{
  "input": {
    "workflow": {},
    "images": [
      {
        "name": "source.png",
        "image": "data:image/png;base64,..."
      }
    ]
  }
}
```

The worker returns `output.images[]` and/or `output.videos[]`. Artifacts are inline base64 unless S3 is configured. The older `input.prompt` + `input.image_url` request remains available for existing clients.

## Model layout

The default INT8 workflow preloads:

- `models/diffusion_models/ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors`
- `models/text_encoders/gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors`
- `models/text_encoders/gemma4_e2b_it_bf16.safetensors`
- `models/vae/ltx-2.5-video-vae-bf16.safetensors`
- `models/vae/ltx-2.5-audio-vae-bf16.safetensors`
- `models/latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors`

Start with at least 48 GB VRAM for the distilled INT8 profile and validate the exact workflow before production. Attach at least 100 GB of persistent storage for the default stack and caches.

## Validation boundary

The test workflow validates shell scripts, JSON, Python syntax, workflow transformation, payload handling, and Docker bake definitions. A release is not GPU-validated until the image has been built for `linux/amd64`, booted on the target CUDA/GPU class, and completed the checked-in workflow.

## Documentation

- [Deployment](docs/deployment.md)
- [Configuration](docs/configuration.md)
- [Network volumes and model paths](docs/network-volumes.md)
- [Development](docs/development.md)
- [CI/CD](docs/ci-cd.md)
- [Customization](docs/customization.md)
