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
    local tmp_path="${output_path}.part"

    mkdir -p "$(dirname "${output_path}")"

    if [ -f "${output_path}" ]; then
        ltx_log "LTX asset already present: ${output_path}"
        return
    fi

    ltx_log "Downloading ${url##*/} to ${output_path}"
    if [ -n "${token}" ]; then
        wget -nv -c --header="Authorization: Bearer ${token}" -O "${tmp_path}" "${url}"
    else
        wget -nv -c -O "${tmp_path}" "${url}"
    fi
    mv "${tmp_path}" "${output_path}"
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
