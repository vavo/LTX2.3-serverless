variable "DOCKERHUB_REPO" {
  default = "runpod"
}

variable "DOCKERHUB_IMG" {
  default = "ltx25-worker"
}

variable "RELEASE_VERSION" {
  default = "latest"
}

variable "COMFYUI_VERSION" {
  default = "v0.33.1"
}

variable "COMFY_CLI_VERSION" {
  default = "1.16.0"
}

variable "LTX_VIDEO_REF" {
  default = "ac4d99839020b983e956a8ab67ec38aec1b6e65a"
}

variable "COMFYUI_DOWNLOADER_REF" {
  default = "03146df738191004a8aad8264dca5c3530907f56"
}

variable "EXTRA_PYTHON_PACKAGES" {
  default = ""
}

variable "EXTRA_PYTHON_INDEX_URL" {
  default = ""
}

group "default" {
  targets = [
    "base",
    "base-cuda12-8-1",
    "ltx2-5-distilled-int8",
    "ltx2-5-distilled-int8-cu128",
  ]
}

target "common" {
  context = "."
  dockerfile = "Dockerfile"
  target = "base"
  platforms = ["linux/amd64"]
  args = {
    COMFYUI_VERSION = "${COMFYUI_VERSION}"
    COMFY_CLI_VERSION = "${COMFY_CLI_VERSION}"
    PYTORCH_PACKAGES = "torch==2.11.0 torchvision==0.26.0 torchaudio==2.11.0"
    INSTALL_LTX_VIDEO_NODES = "true"
    LTX_VIDEO_REF = "${LTX_VIDEO_REF}"
    INSTALL_COMFYUI_DOWNLOADER = "true"
    COMFYUI_DOWNLOADER_REF = "${COMFYUI_DOWNLOADER_REF}"
    EXTRA_PYTHON_PACKAGES = "${EXTRA_PYTHON_PACKAGES}"
    EXTRA_PYTHON_INDEX_URL = "${EXTRA_PYTHON_INDEX_URL}"
  }
}

target "cuda130" {
  inherits = ["common"]
  args = {
    BASE_IMAGE = "ubuntu:24.04"
    PYTORCH_INDEX_URL = "https://download.pytorch.org/whl/cu130"
  }
}

target "cuda128" {
  inherits = ["common"]
  args = {
    BASE_IMAGE = "ubuntu:24.04"
    PYTORCH_INDEX_URL = "https://download.pytorch.org/whl/cu128"
  }
}

target "base" {
  inherits = ["cuda130"]
  tags = ["${DOCKERHUB_REPO}/${DOCKERHUB_IMG}:${RELEASE_VERSION}-base"]
}

target "base-cuda12-8-1" {
  inherits = ["cuda128"]
  tags = ["${DOCKERHUB_REPO}/${DOCKERHUB_IMG}:${RELEASE_VERSION}-base-cuda12.8.1"]
}

target "ltx2-5-distilled-int8" {
  inherits = ["cuda130"]
  args = {
    LTX25_PRELOAD_VARIANT = "distilled-int8"
    LTX25_PRELOAD_PROMPT_ENHANCER = "true"
  }
  tags = ["${DOCKERHUB_REPO}/${DOCKERHUB_IMG}:${RELEASE_VERSION}-ltx2.5-distilled-int8-cu130"]
}

target "ltx2-5-distilled-int8-cu128" {
  inherits = ["cuda128"]
  args = {
    LTX25_PRELOAD_VARIANT = "distilled-int8"
    LTX25_PRELOAD_PROMPT_ENHANCER = "true"
  }
  tags = ["${DOCKERHUB_REPO}/${DOCKERHUB_IMG}:${RELEASE_VERSION}-ltx2.5-distilled-int8-cu128"]
}
