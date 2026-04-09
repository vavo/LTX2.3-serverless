variable "DOCKERHUB_REPO" {
  default = "runpod"
}

variable "DOCKERHUB_IMG" {
  default = "ltx23-worker"
}

variable "RELEASE_VERSION" {
  default = "latest"
}

variable "COMFYUI_VERSION" {
  default = "latest"
}

# Global defaults for standard CUDA 12.6.3 images
variable "BASE_IMAGE" {
  default = "nvidia/cuda:12.6.3-cudnn-runtime-ubuntu24.04"
}

variable "CUDA_VERSION_FOR_COMFY" {
  default = "12.6"
}

variable "ENABLE_PYTORCH_UPGRADE" {
  default = "false"
}

variable "PYTORCH_INDEX_URL" {
  default = ""
}

variable "PYTORCH_PACKAGES" {
  default = "torch torchvision torchaudio"
}

variable "EXTRA_PYTHON_PACKAGES" {
  default = ""
}

variable "EXTRA_PYTHON_INDEX_URL" {
  default = ""
}

variable "INSTALL_LTX_VIDEO_NODES" {
  default = "false"
}

variable "LTX_VIDEO_REF" {
  default = "master"
}

variable "LTX23_PRELOAD_VARIANT" {
  default = ""
}

variable "LTX23_PRELOAD_UPSCALERS" {
  default = "false"
}

group "default" {
  targets = ["base", "base-cuda12-8-1", "base-cuda13-0", "ltx2-3-distilled", "ltx2-3-distilled-fp8", "ltx2-3-distilled-cuda13"]
}

target "base" {
  context = "."
  dockerfile = "Dockerfile"
  target = "base"
  platforms = ["linux/amd64"]
  args = {
    BASE_IMAGE = "${BASE_IMAGE}"
    COMFYUI_VERSION = "${COMFYUI_VERSION}"
    CUDA_VERSION_FOR_COMFY = "${CUDA_VERSION_FOR_COMFY}"
    ENABLE_PYTORCH_UPGRADE = "${ENABLE_PYTORCH_UPGRADE}"
    PYTORCH_INDEX_URL = "${PYTORCH_INDEX_URL}"
    PYTORCH_PACKAGES = "${PYTORCH_PACKAGES}"
    EXTRA_PYTHON_PACKAGES = "${EXTRA_PYTHON_PACKAGES}"
    EXTRA_PYTHON_INDEX_URL = "${EXTRA_PYTHON_INDEX_URL}"
    INSTALL_LTX_VIDEO_NODES = "${INSTALL_LTX_VIDEO_NODES}"
    LTX_VIDEO_REF = "${LTX_VIDEO_REF}"
    LTX23_PRELOAD_VARIANT = "${LTX23_PRELOAD_VARIANT}"
    LTX23_PRELOAD_UPSCALERS = "${LTX23_PRELOAD_UPSCALERS}"
  }
  tags = ["${DOCKERHUB_REPO}/${DOCKERHUB_IMG}:${RELEASE_VERSION}-base"]
}

target "base-cuda12-8-1" {
  context = "."
  dockerfile = "Dockerfile"
  target = "base"
  platforms = ["linux/amd64"]
  args = {
    BASE_IMAGE = "nvidia/cuda:12.8.1-cudnn-runtime-ubuntu24.04"
    COMFYUI_VERSION = "${COMFYUI_VERSION}"
    CUDA_VERSION_FOR_COMFY = ""
    ENABLE_PYTORCH_UPGRADE = "true"
    PYTORCH_INDEX_URL = "https://download.pytorch.org/whl/cu128"
    PYTORCH_PACKAGES = "${PYTORCH_PACKAGES}"
    EXTRA_PYTHON_PACKAGES = "${EXTRA_PYTHON_PACKAGES}"
    EXTRA_PYTHON_INDEX_URL = "${EXTRA_PYTHON_INDEX_URL}"
    INSTALL_LTX_VIDEO_NODES = "${INSTALL_LTX_VIDEO_NODES}"
    LTX_VIDEO_REF = "${LTX_VIDEO_REF}"
    LTX23_PRELOAD_VARIANT = "${LTX23_PRELOAD_VARIANT}"
    LTX23_PRELOAD_UPSCALERS = "${LTX23_PRELOAD_UPSCALERS}"
  }
  tags = ["${DOCKERHUB_REPO}/${DOCKERHUB_IMG}:${RELEASE_VERSION}-base-cuda12.8.1"]
}

target "base-cuda13-0" {
  context = "."
  dockerfile = "Dockerfile"
  target = "base"
  platforms = ["linux/amd64"]
  args = {
    BASE_IMAGE = "nvidia/cuda:13.0.2-cudnn-runtime-ubuntu24.04"
    COMFYUI_VERSION = "${COMFYUI_VERSION}"
    CUDA_VERSION_FOR_COMFY = ""
    ENABLE_PYTORCH_UPGRADE = "true"
    PYTORCH_INDEX_URL = "https://download.pytorch.org/whl/cu130"
    PYTORCH_PACKAGES = "${PYTORCH_PACKAGES}"
    EXTRA_PYTHON_PACKAGES = "${EXTRA_PYTHON_PACKAGES}"
    EXTRA_PYTHON_INDEX_URL = "${EXTRA_PYTHON_INDEX_URL}"
    INSTALL_LTX_VIDEO_NODES = "${INSTALL_LTX_VIDEO_NODES}"
    LTX_VIDEO_REF = "${LTX_VIDEO_REF}"
    LTX23_PRELOAD_VARIANT = "${LTX23_PRELOAD_VARIANT}"
    LTX23_PRELOAD_UPSCALERS = "${LTX23_PRELOAD_UPSCALERS}"
  }
  tags = ["${DOCKERHUB_REPO}/${DOCKERHUB_IMG}:${RELEASE_VERSION}-base-cuda13.0"]
}

target "ltx2-3-distilled" {
  context = "."
  dockerfile = "Dockerfile"
  target = "base"
  platforms = ["linux/amd64"]
  args = {
    BASE_IMAGE = "nvidia/cuda:12.8.1-cudnn-runtime-ubuntu24.04"
    COMFYUI_VERSION = "${COMFYUI_VERSION}"
    CUDA_VERSION_FOR_COMFY = ""
    ENABLE_PYTORCH_UPGRADE = "true"
    PYTORCH_INDEX_URL = "https://download.pytorch.org/whl/cu128"
    PYTORCH_PACKAGES = "${PYTORCH_PACKAGES}"
    EXTRA_PYTHON_PACKAGES = "${EXTRA_PYTHON_PACKAGES}"
    EXTRA_PYTHON_INDEX_URL = "${EXTRA_PYTHON_INDEX_URL}"
    INSTALL_LTX_VIDEO_NODES = "true"
    LTX_VIDEO_REF = "${LTX_VIDEO_REF}"
    LTX23_PRELOAD_VARIANT = "distilled"
    LTX23_PRELOAD_UPSCALERS = "${LTX23_PRELOAD_UPSCALERS}"
  }
  tags = ["${DOCKERHUB_REPO}/${DOCKERHUB_IMG}:${RELEASE_VERSION}-ltx2.3-distilled-cu128"]
}

target "ltx2-3-distilled-fp8" {
  context = "."
  dockerfile = "Dockerfile"
  target = "base"
  platforms = ["linux/amd64"]
  args = {
    BASE_IMAGE = "nvidia/cuda:12.8.1-cudnn-runtime-ubuntu24.04"
    COMFYUI_VERSION = "${COMFYUI_VERSION}"
    CUDA_VERSION_FOR_COMFY = ""
    ENABLE_PYTORCH_UPGRADE = "true"
    PYTORCH_INDEX_URL = "https://download.pytorch.org/whl/cu128"
    PYTORCH_PACKAGES = "${PYTORCH_PACKAGES}"
    EXTRA_PYTHON_PACKAGES = "${EXTRA_PYTHON_PACKAGES}"
    EXTRA_PYTHON_INDEX_URL = "${EXTRA_PYTHON_INDEX_URL}"
    INSTALL_LTX_VIDEO_NODES = "true"
    LTX_VIDEO_REF = "${LTX_VIDEO_REF}"
    LTX23_PRELOAD_VARIANT = "distilled-fp8"
    LTX23_PRELOAD_UPSCALERS = "${LTX23_PRELOAD_UPSCALERS}"
  }
  tags = ["${DOCKERHUB_REPO}/${DOCKERHUB_IMG}:${RELEASE_VERSION}-ltx2.3-distilled-fp8-cu128"]
}

target "ltx2-3-distilled-cuda13" {
  context = "."
  dockerfile = "Dockerfile"
  target = "base"
  platforms = ["linux/amd64"]
  args = {
    BASE_IMAGE = "nvidia/cuda:13.0.2-cudnn-runtime-ubuntu24.04"
    COMFYUI_VERSION = "${COMFYUI_VERSION}"
    CUDA_VERSION_FOR_COMFY = ""
    ENABLE_PYTORCH_UPGRADE = "true"
    PYTORCH_INDEX_URL = "https://download.pytorch.org/whl/cu130"
    PYTORCH_PACKAGES = "${PYTORCH_PACKAGES}"
    EXTRA_PYTHON_PACKAGES = "${EXTRA_PYTHON_PACKAGES}"
    EXTRA_PYTHON_INDEX_URL = "${EXTRA_PYTHON_INDEX_URL}"
    INSTALL_LTX_VIDEO_NODES = "true"
    LTX_VIDEO_REF = "${LTX_VIDEO_REF}"
    LTX23_PRELOAD_VARIANT = "distilled"
    LTX23_PRELOAD_UPSCALERS = "${LTX23_PRELOAD_UPSCALERS}"
  }
  tags = ["${DOCKERHUB_REPO}/${DOCKERHUB_IMG}:${RELEASE_VERSION}-ltx2.3-distilled-cu130"]
}
