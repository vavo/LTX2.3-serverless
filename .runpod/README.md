![LTX 2.5 Worker Banner](https://cpjrphpz3t5wbwfe.public.blob.vercel-storage.com/worker-comfyui_banner-CDZ6JIEByEePozCT1ZrmeVOsN5NX3U.jpeg)

---

Run [LTX 2.5](https://huggingface.co/Lightricks/LTX-2.5) video workflows on [ComfyUI](https://github.com/comfyanonymous/ComfyUI) as a RunPod serverless endpoint.

---

Use the hub metadata in `.runpod/hub.json` when publishing this template to RunPod Hub.

---

## What is included?

- Pinned ComfyUI v0.33.1 with built-in Manager and persistent `/workspace` bootstrap
- Official `ComfyUI-LTXVideo` custom nodes
- Optional startup preload for the complete LTX 2.5 local workflow stack
- CUDA 13.0 as the Blackwell-first default, with CUDA 12.8 as the only fallback

## Recommended deployment shape

- Attach a network volume. Without it, cold starts will repeatedly redownload large model assets like the machine has a concussion.
- Keep `PERSIST_WORKSPACE=true`.
- Use at least 48 GB VRAM for the distilled INT8 profile.
- Plan for roughly 100 GB or more of disk if you want a comfortable setup with cached assets and optional upscalers.

## Important environment variables

- `LTX25_PRELOAD_VARIANT`: `distilled-int8`
- `LTX25_PRELOAD_PROMPT_ENHANCER`: preload the Gemma prompt enhancer
- `HUGGINGFACE_ACCESS_TOKEN`: token with accepted access to the gated LTX 2.5 repository
- `COMFY_ORG_API_KEY`: optional key for Comfy.org API nodes

## Usage

1. Export your ComfyUI workflow with `Workflow > Export (API)`.
2. Send it to the RunPod `/run` or `/runsync` endpoint.
3. If your workflow references additional LTX assets not preloaded at boot, the LTX nodes can fetch them into the persistent workspace on first use.

The full API payload format and deployment notes live in the main project docs:

- [Repository README](https://github.com/vavo/LTX2.3-serverless/blob/main/README.md)
- [Deployment Guide](https://github.com/vavo/LTX2.3-serverless/blob/main/docs/deployment.md)
- [Network Volume Notes](https://github.com/vavo/LTX2.3-serverless/blob/main/docs/network-volumes.md)
