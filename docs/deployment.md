# Deployment

This guide explains how to deploy this ComfyUI-based LTX 2.3 worker as a RunPod serverless endpoint, covering both pre-built image targets and custom-built images.

## Deploying Pre-Built Official Images

This is the simplest method if the official images meet your needs.

### Create your template (optional)

- Create a [new template](https://runpod.io/console/serverless/user/templates) by clicking on `New Template`
- In the dialog, configure:
  - Template Name: `ltx2.3-worker` (or your preferred name)
  - Template Type: serverless (change template type to "serverless")
  - Container Image: Use one of the LTX-oriented tags from the main [README.md](../README.md#available-docker-images), for example `<repo>:<version>-ltx2.3-distilled-cu128`. If you are building your own clean base, plain `base` now defaults to CUDA 12.8.1 / cu128.
  - Container Registry Credentials: Leave as default (images are public).
  - Container Disk: Adjust based on the chosen image tag, see [GPU Recommendations](#gpu-recommendations).
  - (optional) Environment Variables: Configure `LTX23_PRELOAD_VARIANT`, `HUGGINGFACE_ACCESS_TOKEN`, S3, or other settings (see [Configuration Guide](configuration.md)).
    - Note: If you don't configure S3, images are returned as base64. For persistent storage across jobs without S3, consider using a [Network Volume](customization.md#method-2-network-volume-alternative-for-models). If models on your network volume are not being detected, see [Network Volumes & Model Paths](network-volumes.md) for troubleshooting steps.
- Click on `Save Template`

### Create your endpoint

- Navigate to [`Serverless > Endpoints`](https://www.runpod.io/console/serverless/user/endpoints) and click on `New Endpoint`
- In the dialog, configure:

  - Endpoint Name: `ltx2-3` (or your preferred name)
  - Worker configuration: Select a GPU that can run the model included in your chosen image (see [GPU recommendations](#gpu-recommendations)).
  - Active Workers: `0` (Scale as needed based on expected load).
  - Max Workers: `3` (Set a limit based on your budget and scaling needs).
  - GPUs/Worker: `1`
  - Idle Timeout: `5` (Default is usually fine, adjust if needed).
  - Flash Boot: `enabled` (Recommended for faster worker startup).
  - Select Template: `ltx2.3-worker` (or the name you gave your template).
  - (optional) Advanced: Attach a Network Volume under `Select Network Volume`. For this repo that is not really optional unless you like paying cold-start tax on every worker boot. See the [Customization Guide](customization.md#method-2-network-volume-alternative-for-models) and [Network Volumes & Model Paths](network-volumes.md).
  - For serverless endpoints, leave `RUN_MODE` unset or set it explicitly to `worker`.

### Recommended first-boot env

Use this for a sane first worker boot:

```env
PERSIST_WORKSPACE=true
RUN_MODE=worker
COMFY_NODES=127.0.0.1:8188
LTX23_PRELOAD_VARIANT=distilled
LTX23_PRELOAD_UPSCALERS=true
HUGGINGFACE_ACCESS_TOKEN=hf_xxx
```

That preloads the main LTX model stack into persistent storage. Secondary assets used by `ComfyUI-LTXVideo`, especially Gemma and text-encoder weights, may still fetch on the first render and then stay cached under `/workspace/worker-comfyui/cache/huggingface`.

## Hardware Baseline

- CUDA 12.8 is the default target in this repo.
- Plain `docker build ...` and bake target `base` now default to CUDA 12.8.1 with the cu128 PyTorch wheel index.
- CUDA 13 is supported here as an experimental path.
- The LTX / ComfyUI docs recommend 32GB+ VRAM and 100GB+ free disk for a comfortable setup.
- For the CUDA 12.8 path, PyTorch 2.8+ is the intended floor.
- For the CUDA 13 path, official `cu130` wheels start at PyTorch 2.9+, so treat that lane accordingly.

## Current Truth

### Works Today

- RunPod serverless worker around ComfyUI.
- Persistent state on `/workspace` via network volume.
- LTX-focused image targets as listed in the main [README.md](../README.md#available-docker-images).
- Standard RunPod endpoints: `/run`, `/runsync`, `/health`.
- Input workflow JSON plus optional input images.
- Output handling for image and video artifacts from ComfyUI.
- Checked-in LTX image-to-video API workflow at [`video_ltx2_3_i2v_API.json`](../video_ltx2_3_i2v_API.json).

### Compatibility Baggage

- The worker still accepts the older custom request shape based on `input.prompt`, `input.image_url`, and `input.api_key`.
- New integrations should use the workflow contract documented in the main [README.md](../README.md#api-specification) instead of building against the legacy compatibility path.
- The worker currently returns image and video files only. Audio-only artifacts are still not exposed as a first-class output collection.

- Click `deploy`
- Your endpoint will be created. You can click on it to view the dashboard and find its ID.

### GPU recommendations (for Official Images)

| Target                           | Image Tag Suffix              | Minimum VRAM Required | Recommended Container Size |
| -------------------------------- | ----------------------------- | --------------------- | -------------------------- |
| Clean base, default CUDA 12.8    | `base`                        | N/A                   | 20 GB                      |
| LTX 2.3 distilled                | `ltx2.3-distilled-cu128`      | 32 GB                 | 100 GB                     |
| LTX 2.3 distilled fp8            | `ltx2.3-distilled-fp8-cu128`  | 24-32 GB              | 100 GB                     |
| LTX 2.3 distilled, experimental  | `ltx2.3-distilled-cu130`      | 32 GB                 | 100 GB                     |
| CUDA 12.8 clean base, explicit alias | `base-cuda12.8.1`         | N/A                   | 20 GB                      |
| CUDA 13 clean base               | `base-cuda13.0`               | N/A                   | 20 GB                      |

_Note: Container sizes are approximate and assume a network volume for persistent state. Without a network volume, you will need more local disk and much more patience._

## Deploying Custom Setups

If you have created a custom environment using the methods in the [Customization Guide](customization.md), here's how to deploy it.

> [!TIP] > **Want to skip the manual setup?**
>
> [ComfyUI-to-API](https://comfy.getrunpod.io) automatically generates a GitHub repository with a custom Dockerfile from your ComfyUI workflow. You can then deploy it using [Method 2: GitHub Integration](#method-2-deploying-via-runpod-github-integration) below with no manual Docker building required. See the [ComfyUI-to-API Documentation](https://docs.runpod.io/community-solutions/comfyui-to-api/overview) for details.

### Method 1: Manual Build, Push, and Deploy

This method involves building your custom Docker image locally, pushing it to a registry, and then deploying that image on RunPod.

1.  **Write your Dockerfile:** Follow the instructions in the [Customization Guide](customization.md#method-1-custom-dockerfile-recommended) to create your `Dockerfile` specifying the base image, nodes, models, and any static files.
2.  **Build the Docker image:** Navigate to the directory containing your `Dockerfile` and run:
    ```bash
    # Replace <your-image-name>:<tag> with your desired name and tag
    docker build --platform linux/amd64 -t <your-image-name>:<tag> .
    ```
    - **Crucially**, always include `--platform linux/amd64` for RunPod compatibility.
3.  **Tag the image for your registry:** Replace `<your-registry-username>` and `<your-image-name>:<tag>` accordingly.
    ```bash
    # Example for Docker Hub:
    docker tag <your-image-name>:<tag> <your-registry-username>/<your-image-name>:<tag>
    ```
4.  **Log in to your container registry:**
    ```bash
    # Example for Docker Hub:
    docker login
    ```
5.  **Push the image:**
    ```bash
    # Example for Docker Hub:
    docker push <your-registry-username>/<your-image-name>:<tag>
    ```
6.  **Deploy on RunPod:**
    - Follow the steps in [Create your template](#create-your-template-optional) above, but for the `Container Image` field, enter the full name of the image you just pushed (e.g., `<your-registry-username>/<your-image-name>:<tag>`).
    - If your registry is private, you will need to provide [Container Registry Credentials](https://docs.runpod.io/serverless/templates#container-registry-credentials).
    - Adjust the `Container Disk` size based on your custom image contents.
    - Follow the steps in [Create your endpoint](#create-your-endpoint) using the template you just created.

### Method 2: Deploying via RunPod GitHub Integration

RunPod offers a seamless way to deploy directly from your GitHub repository containing the `Dockerfile`. RunPod handles the build and deployment.

1.  **Prepare your GitHub Repository:** Ensure your repository contains the custom `Dockerfile` (as described in the [Customization Guide](customization.md#method-1-custom-dockerfile-recommended)) at the root or a specified path.
2.  **Connect GitHub to RunPod:** Authorize RunPod to access your repository via your RunPod account settings or when creating a new endpoint.
3.  **Create a New Serverless Endpoint:** In RunPod, navigate to Serverless -> `+ New Endpoint` and select the **"Start from GitHub Repo"** option.
4.  **Configure:**
    - Select the GitHub repository and branch you want to deploy (e.g., `main`).
    - Specify the **Context Path** (usually `/` if the Dockerfile is at the root).
    - Specify the **Dockerfile Path** (usually `Dockerfile`).
    - Configure your desired compute resources (GPU type, workers, etc.).
    - Configure any necessary [Environment Variables](configuration.md).
5.  **Deploy:** RunPod will clone the repository, build the image from your specified branch and Dockerfile, push it to a temporary registry, and deploy the endpoint.

Every `git push` to the configured branch will automatically trigger a new build and update your RunPod endpoint. For more details, refer to the [RunPod GitHub Integration Documentation](https://docs.runpod.io/serverless/github-integration).

## Using the Image in a Pod

If you use this image for a plain pod instead of a serverless worker, set:

```bash
RUN_MODE=pod
```

That starts ComfyUI and the bundled frontend, but skips `runpod.serverless.start(...)`.

For a sane first pod boot, use:

```env
PERSIST_WORKSPACE=true
RUN_MODE=pod
LOCAL_COMFY_NODE=127.0.0.1:8188
LTX23_PRELOAD_VARIANT=distilled
LTX23_PRELOAD_UPSCALERS=true
HUGGINGFACE_ACCESS_TOKEN=hf_xxx
```
