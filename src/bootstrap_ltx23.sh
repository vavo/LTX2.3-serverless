#!/usr/bin/env bash

set -euo pipefail

ltx_log() {
    echo "worker-comfyui: $*"
}

ltx_hf_token() {
    if [ -n "${HF_TOKEN:-}" ]; then
        printf '%s\n' "${HF_TOKEN}"
        return
    fi

    if [ -n "${HUGGINGFACE_TOKEN:-}" ]; then
        printf '%s\n' "${HUGGINGFACE_TOKEN}"
        return
    fi

    if [ -n "${HUGGINGFACE_ACCESS_TOKEN:-}" ]; then
        printf '%s\n' "${HUGGINGFACE_ACCESS_TOKEN}"
        return
    fi

    printf '%s\n' ""
}

ltx_download() {
    local url="$1"
    local output_path="$2"
    local token="${3:-}"
    local backend="${LTX23_DOWNLOAD_BACKEND:-auto}"

    mkdir -p "$(dirname "${output_path}")"

    if [ -f "${output_path}" ]; then
        ltx_log "LTX asset already present: ${output_path}"
        return
    fi

    case "${backend}" in
        auto)
            if python -c "import huggingface_hub" >/dev/null 2>&1; then
                ltx_download_with_hf_hub "${url}" "${output_path}" "${token}"
            else
                ltx_download_with_wget "${url}" "${output_path}" "${token}"
            fi
            ;;
        hf_hub)
            ltx_download_with_hf_hub "${url}" "${output_path}" "${token}"
            ;;
        wget)
            ltx_download_with_wget "${url}" "${output_path}" "${token}"
            ;;
        *)
            ltx_log "Unsupported LTX23_DOWNLOAD_BACKEND='${backend}'"
            exit 1
            ;;
    esac
}

ltx_download_with_wget() {
    local url="$1"
    local output_path="$2"
    local token="${3:-}"
    local tmp_path="${output_path}.part"

    ltx_log "Downloading ${url##*/} to ${output_path} via wget"
    if [ -n "${token}" ]; then
        wget -nv -c --header="Authorization: Bearer ${token}" -O "${tmp_path}" "${url}"
    else
        wget -nv -c -O "${tmp_path}" "${url}"
    fi
    mv "${tmp_path}" "${output_path}"
}

ltx_download_with_hf_hub() {
    local url="$1"
    local output_path="$2"
    local token="${3:-}"

    export HF_HUB_ENABLE_HF_TRANSFER="${HF_HUB_ENABLE_HF_TRANSFER:-1}"
    export LTX_DOWNLOAD_URL="${url}"
    export LTX_DOWNLOAD_OUTPUT_PATH="${output_path}"
    export LTX_DOWNLOAD_TOKEN="${token}"

    ltx_log "Downloading ${url##*/} to ${output_path} via huggingface_hub (hf_transfer=${HF_HUB_ENABLE_HF_TRANSFER})"
    python - <<'PY'
import os
import re
from pathlib import Path

from huggingface_hub import hf_hub_download

url = os.environ["LTX_DOWNLOAD_URL"]
output_path = Path(os.environ["LTX_DOWNLOAD_OUTPUT_PATH"])
token = os.environ.get("LTX_DOWNLOAD_TOKEN") or None

match = re.match(r"^https://huggingface\.co/([^/]+/[^/]+)/resolve/([^/]+)/(.+)$", url)
if not match:
    raise SystemExit(f"Unsupported Hugging Face resolve URL: {url}")

repo_id, revision, filename = match.groups()
output_path.parent.mkdir(parents=True, exist_ok=True)

downloaded_path = Path(
    hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        revision=revision,
        token=token,
        local_dir=str(output_path.parent),
    )
)

if downloaded_path.resolve() != output_path.resolve():
    downloaded_path.replace(output_path)
PY

    unset LTX_DOWNLOAD_URL
    unset LTX_DOWNLOAD_OUTPUT_PATH
    unset LTX_DOWNLOAD_TOKEN
}

ltx_checkpoint_url() {
    case "$1" in
        distilled)
            printf '%s\n' "https://huggingface.co/Lightricks/LTX-2.3/resolve/main/ltx-2.3-22b-distilled.safetensors"
            ;;
        dev)
            printf '%s\n' "https://huggingface.co/Lightricks/LTX-2.3/resolve/main/ltx-2.3-22b-dev.safetensors"
            ;;
        distilled-fp8)
            printf '%s\n' "https://huggingface.co/Lightricks/LTX-2.3-fp8/resolve/main/ltx-2.3-22b-distilled-fp8.safetensors"
            ;;
        dev-fp8)
            printf '%s\n' "https://huggingface.co/Lightricks/LTX-2.3-fp8/resolve/main/ltx-2.3-22b-dev-fp8.safetensors"
            ;;
        *)
            return 1
            ;;
    esac
}

ltx_upscaler_urls() {
    cat <<'EOF'
https://huggingface.co/Lightricks/LTX-2.3/resolve/main/ltx-2.3-spatial-upscaler-x1.5-1.0.safetensors
https://huggingface.co/Lightricks/LTX-2.3/resolve/main/ltx-2.3-spatial-upscaler-x2-1.1.safetensors
https://huggingface.co/Lightricks/LTX-2.3/resolve/main/ltx-2.3-temporal-upscaler-x2-1.0.safetensors
EOF
}

ltx_distilled_lora_url() {
    printf '%s\n' "https://huggingface.co/Lightricks/LTX-2.3/resolve/main/ltx-2.3-22b-distilled-lora-384.safetensors"
}

ltx_is_distilled_variant() {
    case "$1" in
        distilled|distilled-fp8)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

bootstrap_ltx23() {
    local variant="${LTX23_PRELOAD_VARIANT:-}"
    local checkpoint_dir="${LTX23_CHECKPOINT_DIR:-${COMFY_MODEL_ROOT:-/comfyui/models}/checkpoints/LTX-Video}"
    local upscale_dir="${LTX23_UPSCALER_DIR:-${COMFY_MODEL_ROOT:-/comfyui/models}/latent_upscale_models/LTX-Video}"
    local lora_dir="${LTX23_LORA_DIR:-${COMFY_MODEL_ROOT:-/comfyui/models}/loras/LTX-Video}"
    local token
    token="$(ltx_hf_token)"

    if [ -z "${variant}" ]; then
        return
    fi

    local checkpoint_url
    checkpoint_url="$(ltx_checkpoint_url "${variant}")" || {
        ltx_log "Unsupported LTX23_PRELOAD_VARIANT='${variant}'"
        exit 1
    }

    ltx_download "${checkpoint_url}" "${checkpoint_dir}/$(basename "${checkpoint_url}")" "${token}"

    if [ "${LTX23_PRELOAD_UPSCALERS:-false}" = "true" ]; then
        while IFS= read -r url; do
            [ -n "${url}" ] || continue
            ltx_download "${url}" "${upscale_dir}/$(basename "${url}")" "${token}"
        done < <(ltx_upscaler_urls)

        if ltx_is_distilled_variant "${variant}"; then
            local distilled_lora_url
            distilled_lora_url="$(ltx_distilled_lora_url)"
            ltx_download "${distilled_lora_url}" "${lora_dir}/$(basename "${distilled_lora_url}")" "${token}"
        fi
    fi

    ltx_log "LTX checkpoint preload finished. Remaining assets such as Gemma/text-encoder weights can still auto-download via ComfyUI-LTXVideo on first run."
}
