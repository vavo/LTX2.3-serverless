#!/usr/bin/env bash

set -euo pipefail

bootstrap_log() {
    echo "worker-comfyui: $*"
}

ensure_workspace_alias() {
    if [ ! -e /workspace ] && [ -d /runpod-volume ]; then
        ln -s /runpod-volume /workspace
    fi
}

detect_persistent_root() {
    if [ -n "${WORKSPACE_ROOT:-}" ]; then
        mkdir -p "${WORKSPACE_ROOT}"
        printf '%s\n' "${WORKSPACE_ROOT}"
        return
    fi

    ensure_workspace_alias

    if [ -d /workspace ]; then
        printf '%s\n' "/workspace"
        return
    fi

    if [ -d /runpod-volume ]; then
        printf '%s\n' "/runpod-volume"
        return
    fi

    printf '%s\n' ""
}

seed_directory_if_missing() {
    local source_dir="$1"
    local target_dir="$2"
    local label="$3"
    local marker_file="${target_dir}/.worker-seeded"

    if [ -f "${marker_file}" ]; then
        bootstrap_log "Using persisted ${label} at ${target_dir}"
        return
    fi

    bootstrap_log "Seeding ${label} into ${target_dir}"
    mkdir -p "${target_dir}"
    cp -a "${source_dir}/." "${target_dir}/"
    touch "${marker_file}"
}

replace_with_symlink() {
    local source_path="$1"
    local target_path="$2"

    if [ -L "${source_path}" ] && [ "$(readlink "${source_path}")" = "${target_path}" ]; then
        return
    fi

    rm -rf "${source_path}"
    ln -s "${target_path}" "${source_path}"
}

write_extra_model_paths() {
    local base_path="$1"

    cat > /comfyui/extra_model_paths.yaml <<EOF
runpod_worker_comfy:
  base_path: ${base_path}
  checkpoints: models/checkpoints/
  clip: models/clip/
  clip_vision: models/clip_vision/
  configs: models/configs/
  controlnet: models/controlnet/
  embeddings: models/embeddings/
  latent_upscale_models: models/latent_upscale_models/
  loras: models/loras/
  text_encoders: models/text_encoders/
  diffusion_models: models/diffusion_models/
  upscale_models: models/upscale_models/
  vae: models/vae/
  unet: models/unet/
EOF
}

bootstrap_workspace() {
    if [ "${PERSIST_WORKSPACE:-true}" != "true" ]; then
        bootstrap_log "Workspace persistence disabled"
        return
    fi

    local persistent_root
    persistent_root="$(detect_persistent_root)"

    if [ -z "${persistent_root}" ]; then
        bootstrap_log "No persistent workspace mount detected; using image-local paths"
        write_extra_model_paths "/runpod-volume"
        return
    fi

    export WORKSPACE_ROOT="${persistent_root}"

    local state_root="${WORKSPACE_STATE_ROOT:-${WORKSPACE_ROOT}/worker-comfyui}"
    local comfy_root="${state_root}/comfyui"
    local venv_root="${state_root}/venv"
    local cache_root="${state_root}/cache"

    mkdir -p \
        "${state_root}" \
        "${WORKSPACE_ROOT}/models" \
        "${cache_root}/huggingface" \
        "${cache_root}/pip" \
        "${cache_root}/torch" \
        "${cache_root}/triton" \
        "${cache_root}/uv" \
        "${cache_root}/xdg"

    seed_directory_if_missing /comfyui "${comfy_root}" "ComfyUI root"
    seed_directory_if_missing /opt/venv "${venv_root}" "Python virtualenv"

    replace_with_symlink /comfyui "${comfy_root}"
    replace_with_symlink /opt/venv "${venv_root}"

    export PATH="/opt/venv/bin:${PATH}"
    export HF_HOME="${cache_root}/huggingface"
    export PIP_CACHE_DIR="${cache_root}/pip"
    export TORCH_HOME="${cache_root}/torch"
    export TRITON_CACHE_DIR="${cache_root}/triton"
    export UV_CACHE_DIR="${cache_root}/uv"
    export XDG_CACHE_HOME="${cache_root}/xdg"
    export COMFY_MODEL_ROOT="${WORKSPACE_ROOT}/models"

    write_extra_model_paths "${WORKSPACE_ROOT}"

    bootstrap_log "Using persistent workspace at ${WORKSPACE_ROOT}"
    bootstrap_log "ComfyUI root: ${comfy_root}"
    bootstrap_log "Virtualenv: ${venv_root}"
}
