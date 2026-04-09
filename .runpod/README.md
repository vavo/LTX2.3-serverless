![LTX 2.3 Worker Banner](https://cpjrphpz3t5wbwfe.public.blob.vercel-storage.com/worker-comfyui_banner-CDZ6JIEByEePozCT1ZrmeVOsN5NX3U.jpeg)

---

Run [LTX 2.3](https://huggingface.co/Lightricks/LTX-2.3) video workflows on [ComfyUI](https://github.com/comfyanonymous/ComfyUI) as a RunPod serverless endpoint.

---

[![RunPod](https://api.runpod.io/badge/runpod-workers/worker-comfyui)](https://www.runpod.io/console/hub/runpod-workers/worker-comfyui)

---

## What is included?

- Latest ComfyUI base image with persistent `/workspace` bootstrap
- Official `ComfyUI-LTXVideo` custom nodes
- Optional startup preload for the main LTX 2.3 checkpoint
- CUDA 12.8 as the default track, with an experimental CUDA 13 path for newer Blackwell-oriented hosts

## Recommended deployment shape

- Attach a network volume. Without it, cold starts will repeatedly redownload large model assets like the machine has a concussion.
- Keep `PERSIST_WORKSPACE=true`.
- Use at least 32 GB VRAM for practical LTX 2.3 usage.
- Plan for roughly 100 GB or more of disk if you want a comfortable setup with cached assets and optional upscalers.

## Important environment variables

- `LTX23_PRELOAD_VARIANT`: `distilled`, `dev`, `distilled-fp8`, or `dev-fp8`
- `LTX23_PRELOAD_UPSCALERS`: preload official LTX spatial and temporal upscalers
- `HUGGINGFACE_ACCESS_TOKEN`: optional token for startup downloads
- `COMFY_ORG_API_KEY`: optional key for Comfy.org API nodes

## Usage

1. Export your ComfyUI workflow with `Workflow > Export (API)`.
2. Send it to the RunPod `/run` or `/runsync` endpoint.
3. If your workflow references additional LTX assets not preloaded at boot, the LTX nodes can fetch them into the persistent workspace on first use.

The full API payload format and deployment notes live in the main project docs:

- [Repository README](https://github.com/vavo/LTX2.3-serverless/blob/main/README.md)
- [Deployment Guide](https://github.com/vavo/LTX2.3-serverless/blob/main/docs/deployment.md)
- [Network Volume Notes](https://github.com/vavo/LTX2.3-serverless/blob/main/docs/network-volumes.md)
