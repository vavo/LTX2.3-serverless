# syntax=docker/dockerfile:1.7

# Build argument for base image selection
ARG BASE_IMAGE=nvidia/cuda:12.8.1-cudnn-runtime-ubuntu24.04

# Stage 1: Base image with common dependencies
FROM ${BASE_IMAGE} AS base

# Build arguments for this stage with sensible defaults for standalone builds
ARG COMFYUI_VERSION=latest
ARG CUDA_VERSION_FOR_COMFY
ARG ENABLE_PYTORCH_UPGRADE=true
ARG PYTORCH_INDEX_URL=https://download.pytorch.org/whl/cu128
ARG PYTORCH_PACKAGES="torch torchvision torchaudio"
ARG EXTRA_PYTHON_PACKAGES=""
ARG EXTRA_PYTHON_INDEX_URL=""
ARG INSTALL_LTX_VIDEO_NODES=false
ARG LTX_VIDEO_REF=master
ARG INSTALL_COMFYUI_MANAGER=true
ARG COMFYUI_MANAGER_REF=main
ARG LTX23_PRELOAD_VARIANT=""
ARG LTX23_PRELOAD_UPSCALERS=false

# Prevents prompts from packages asking for user input during installation
ENV DEBIAN_FRONTEND=noninteractive
# Prefer binary wheels over source distributions for faster pip installations
ENV PIP_PREFER_BINARY=1
# Ensures output from python is printed immediately to the terminal without buffering
ENV PYTHONUNBUFFERED=1
# Speed up some cmake builds
ENV CMAKE_BUILD_PARALLEL_LEVEL=8

# Install Python, git and other necessary tools
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y \
    python3.12 \
    python3.12-venv \
    redis-server \
    git \
    wget \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    ffmpeg \
    openssh-server \
    && ln -sf /usr/bin/python3.12 /usr/bin/python \
    && ln -sf /usr/bin/pip3 /usr/bin/pip \
    && apt-get autoremove -y \
    && apt-get clean -y \
    && rm -rf /var/lib/apt/lists/*

# Create the virtualenv with Python.
RUN python -m venv /opt/venv

# Use the virtual environment for all subsequent commands
ENV VIRTUAL_ENV="/opt/venv"
ENV PATH="/opt/venv/bin:${PATH}"

# Install comfy-cli + base Python tooling used by the image.
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install comfy-cli triton

# Install ComfyUI
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    if [ -n "${CUDA_VERSION_FOR_COMFY}" ]; then \
      /usr/bin/yes | comfy --workspace /comfyui install --version "${COMFYUI_VERSION}" --cuda-version "${CUDA_VERSION_FOR_COMFY}" --nvidia; \
    else \
      /usr/bin/yes | comfy --workspace /comfyui install --version "${COMFYUI_VERSION}" --nvidia; \
    fi

# Upgrade PyTorch if needed (for newer CUDA versions)
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    if [ "$ENABLE_PYTORCH_UPGRADE" = "true" ]; then \
      python -m pip install --force-reinstall ${PYTORCH_PACKAGES} --index-url ${PYTORCH_INDEX_URL}; \
    fi

# Change working directory to ComfyUI
WORKDIR /comfyui

# Support for the network volume
ADD src/extra_model_paths.yaml ./

# Go back to the root
WORKDIR /

# Install Python runtime dependencies for the handler
ADD requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    python -m pip install -r /requirements.txt

# Optional image-level extras for specific GPU/model stacks.
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    if [ -n "${EXTRA_PYTHON_PACKAGES}" ]; then \
      if [ -n "${EXTRA_PYTHON_INDEX_URL}" ]; then \
        python -m pip install --index-url ${EXTRA_PYTHON_INDEX_URL} ${EXTRA_PYTHON_PACKAGES}; \
      else \
        python -m pip install ${EXTRA_PYTHON_PACKAGES}; \
      fi; \
    fi

# Add application code and scripts
ADD src/start.sh src/bootstrap_workspace.sh src/bootstrap_ltx23.sh src/network_volume.py handler.py workflow_support.py frontend_app.py ltx_payload_builder.py video_ltx2_3_i2v_API.json test_input.json ./
ADD frontend /frontend
RUN chmod +x /start.sh
RUN chmod +x /bootstrap_workspace.sh
RUN chmod +x /bootstrap_ltx23.sh

# Add script to install custom nodes
COPY scripts/comfy-node-install.sh /usr/local/bin/comfy-node-install
RUN chmod +x /usr/local/bin/comfy-node-install

# Install ComfyUI-Manager by default so the runtime config line is not fiction.
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    if [ "${INSTALL_COMFYUI_MANAGER}" = "true" ]; then \
      git clone --depth=1 --branch "${COMFYUI_MANAGER_REF}" https://github.com/ltdrdata/ComfyUI-Manager.git /comfyui/custom_nodes/ComfyUI-Manager && \
      if [ -f /comfyui/custom_nodes/ComfyUI-Manager/requirements.txt ]; then \
        python -m pip install -r /comfyui/custom_nodes/ComfyUI-Manager/requirements.txt; \
      fi; \
    fi

# Prevent pip from asking for confirmation during uninstall steps in custom nodes
ENV PIP_NO_INPUT=1

# Copy helper script to switch Manager network mode at container start
COPY scripts/comfy-manager-set-mode.sh /usr/local/bin/comfy-manager-set-mode
RUN chmod +x /usr/local/bin/comfy-manager-set-mode

# Install the official LTX ComfyUI nodes when requested by the image target.
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    if [ "${INSTALL_LTX_VIDEO_NODES}" = "true" ]; then \
      git clone --depth=1 --branch "${LTX_VIDEO_REF}" https://github.com/Lightricks/ComfyUI-LTXVideo.git /comfyui/custom_nodes/ComfyUI-LTXVideo && \
      python -m pip install -r /comfyui/custom_nodes/ComfyUI-LTXVideo/requirements.txt; \
    fi

ENV LTX23_PRELOAD_VARIANT="${LTX23_PRELOAD_VARIANT}"
ENV LTX23_PRELOAD_UPSCALERS="${LTX23_PRELOAD_UPSCALERS}"

# Set the default command to run when starting the container
CMD ["/start.sh"]
