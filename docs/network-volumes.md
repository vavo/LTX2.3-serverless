# Network volumes and model paths

Model weights are deliberately excluded from Docker layers. Use a RunPod network volume so workers do not redownload the LTX stack after every scale-to-zero cycle.

## Mount mapping

RunPod mounts a Serverless network volume at `/runpod-volume`. This worker aliases it to `/workspace`, giving Serverless and Pod modes the same internal layout.

| Purpose | Worker path |
| --- | --- |
| Persistent root | `/workspace` |
| Serverless backing mount | `/runpod-volume` |
| Models | `/workspace/models` |
| ComfyUI state | `/workspace/worker-comfyui/comfyui` |
| Python virtualenv | `/workspace/worker-comfyui/venv` |
| Caches | `/workspace/worker-comfyui/cache` |
| Bootstrap lock | `/workspace/worker-comfyui/.bootstrap.lock` |

RunPod network volumes persist independently of workers, but bind an endpoint to the volume's data center. Multiple volumes can improve geographic GPU availability, though RunPod does not synchronize their contents.

## LTX 2.5 layout

The default `distilled-int8` preload creates this structure:

```text
/workspace/models/
├── diffusion_models/
│   └── ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors
├── text_encoders/
│   ├── gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors
│   └── gemma4_e2b_it_bf16.safetensors
├── vae/
│   ├── ltx-2.5-video-vae-bf16.safetensors
│   └── ltx-2.5-audio-vae-bf16.safetensors
└── latent_upscale_models/
    └── ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors
```

The prompt-enhancer file is omitted when `LTX25_PRELOAD_PROMPT_ENHANCER=false`.

The generated `/comfyui/extra_model_paths.yaml` also maps these optional model directories under `/workspace/models`:

```text
checkpoints  clip  clip_vision  configs  controlnet  embeddings
loras  unet  upscale_models
```

Only create directories used by your workflows. The loader node determines the directory: `UNETLoader` uses `diffusion_models`, `DualCLIPLoader` uses `text_encoders`, `VAELoader` uses `vae`, and `LoraLoader` uses `loras`.

## Attach and preload

1. Create a volume in a data center offering the target GPU.
2. Attach it under the endpoint's advanced network-volume settings.
3. Set the preload variables from the [configuration guide](configuration.md#ltx-25-preload).
4. Start one worker and let bootstrap finish before scaling concurrency.
5. Confirm all expected files exist under `/workspace/models` in the worker logs or shell.

The bootstrap lock prevents two workers from seeding the persisted ComfyUI and venv concurrently. Model downloads use partial files and atomic renames, but the calmest first boot is still one worker. Distributed filesystems reward modesty.

## Troubleshooting

- **Models are missing:** verify the volume is attached and files are below `/runpod-volume/models`, not `/runpod-volume` directly.
- **Access denied:** accept the model license and provide a valid read token.
- **A workflow reports an unknown model:** compare its loader widget value with the exact filename and directory above.
- **Every cold start downloads again:** confirm `PERSIST_WORKSPACE=true` and that `/workspace` resolves to the attached volume.
- **A second region fails:** populate every attached volume; RunPod does not mirror them automatically.

See RunPod's [network volume documentation](https://docs.runpod.io/storage/network-volumes) for current attachment and multi-volume behavior.
