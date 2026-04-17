#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT_TO_TEST="${REPO_ROOT}/src/bootstrap_workspace.sh"

if [ ! -f "${SCRIPT_TO_TEST}" ]; then
    echo "Error: Script not found at ${SCRIPT_TO_TEST}"
    exit 1
fi

TEST_DIR="$(mktemp -d)"
trap 'rm -rf "${TEST_DIR}"' EXIT

IMAGE_COMFY="${TEST_DIR}/image-comfy"
IMAGE_VENV="${TEST_DIR}/image-venv"
RUNTIME_COMFY="${TEST_DIR}/runtime-comfy"
RUNTIME_VENV="${TEST_DIR}/runtime-venv"
WORKSPACE_ROOT="${TEST_DIR}/workspace"
EXTRA_MODEL_PATHS_FILE="${TEST_DIR}/extra_model_paths.yaml"

mkdir -p "${IMAGE_COMFY}/models/checkpoints" "${IMAGE_VENV}/bin" "${RUNTIME_COMFY}" "${RUNTIME_VENV}"
printf 'seeded comfy\n' > "${IMAGE_COMFY}/main.py"
printf 'seeded venv\n' > "${IMAGE_VENV}/bin/python"
mkdir -p "${IMAGE_COMFY}/custom_nodes/ComfyUI-Manager"
printf 'manager present\n' > "${IMAGE_COMFY}/custom_nodes/ComfyUI-Manager/README.txt"

run_persistent_bootstrap() {
    (
        export PERSIST_WORKSPACE=true
        export WORKSPACE_ROOT="${WORKSPACE_ROOT}"
        export WORKSPACE_STATE_ROOT="${WORKSPACE_ROOT}/worker-comfyui"
        export COMFY_IMAGE_ROOT="${IMAGE_COMFY}"
        export COMFY_RUNTIME_ROOT="${RUNTIME_COMFY}"
        export VENV_IMAGE_ROOT="${IMAGE_VENV}"
        export VENV_RUNTIME_ROOT="${RUNTIME_VENV}"
        export EXTRA_MODEL_PATHS_FILE="${EXTRA_MODEL_PATHS_FILE}"

        source "${SCRIPT_TO_TEST}"
        bootstrap_workspace
    )
}

assert_file_contains() {
    local path="$1"
    local expected="$2"

    grep -Fq "${expected}" "${path}" || {
        echo "Expected '${expected}' in ${path}"
        exit 1
    }
}

run_persistent_bootstrap

[ -L "${RUNTIME_COMFY}" ] || { echo "Expected ${RUNTIME_COMFY} to be a symlink"; exit 1; }
[ -L "${RUNTIME_VENV}" ] || { echo "Expected ${RUNTIME_VENV} to be a symlink"; exit 1; }
[ "$(readlink "${RUNTIME_COMFY}")" = "${WORKSPACE_ROOT}/worker-comfyui/comfyui" ] || { echo "Unexpected ComfyUI symlink target"; exit 1; }
[ "$(readlink "${RUNTIME_VENV}")" = "${WORKSPACE_ROOT}/worker-comfyui/venv" ] || { echo "Unexpected venv symlink target"; exit 1; }

assert_file_contains "${WORKSPACE_ROOT}/worker-comfyui/comfyui/main.py" "seeded comfy"
assert_file_contains "${WORKSPACE_ROOT}/worker-comfyui/venv/bin/python" "seeded venv"
assert_file_contains "${EXTRA_MODEL_PATHS_FILE}" "base_path: ${WORKSPACE_ROOT}"
assert_file_contains "${WORKSPACE_ROOT}/worker-comfyui/comfyui/custom_nodes/ComfyUI-Manager/README.txt" "manager present"

for cache_dir in huggingface pip torch triton xdg; do
    [ -d "${WORKSPACE_ROOT}/worker-comfyui/cache/${cache_dir}" ] || {
        echo "Missing cache directory ${cache_dir}"
        exit 1
    }
done

printf 'mutated comfy\n' > "${IMAGE_COMFY}/main.py"
printf 'mutated venv\n' > "${IMAGE_VENV}/bin/python"

run_persistent_bootstrap

assert_file_contains "${WORKSPACE_ROOT}/worker-comfyui/comfyui/main.py" "seeded comfy"
assert_file_contains "${WORKSPACE_ROOT}/worker-comfyui/venv/bin/python" "seeded venv"

rm -rf "${WORKSPACE_ROOT}/worker-comfyui/comfyui/custom_nodes/ComfyUI-Manager"
run_persistent_bootstrap
assert_file_contains "${WORKSPACE_ROOT}/worker-comfyui/comfyui/custom_nodes/ComfyUI-Manager/README.txt" "manager present"

rm -f "${WORKSPACE_ROOT}/worker-comfyui/venv/.worker-seeded"
mkdir -p "${WORKSPACE_ROOT}/worker-comfyui/venv/lib/python3.12/site-packages/einops"
printf 'stale partial seed\n' > "${WORKSPACE_ROOT}/worker-comfyui/venv/lib/python3.12/site-packages/einops/__init__.py"
run_persistent_bootstrap
assert_file_contains "${WORKSPACE_ROOT}/worker-comfyui/venv/bin/python" "mutated venv"
[ ! -e "${WORKSPACE_ROOT}/worker-comfyui/venv/lib/python3.12/site-packages/einops/__init__.py" ] || {
    echo "Expected stale partial venv contents to be removed"
    exit 1
}

LOCAL_RUNTIME_COMFY="${TEST_DIR}/local-comfy"
LOCAL_EXTRA_MODEL_PATHS_FILE="${TEST_DIR}/local-extra_model_paths.yaml"
mkdir -p "${LOCAL_RUNTIME_COMFY}/models"

(
    export PERSIST_WORKSPACE=true
    export COMFY_RUNTIME_ROOT="${LOCAL_RUNTIME_COMFY}"
    export EXTRA_MODEL_PATHS_FILE="${LOCAL_EXTRA_MODEL_PATHS_FILE}"

    source "${SCRIPT_TO_TEST}"
    detect_persistent_root() {
        printf '%s\n' ""
    }
    bootstrap_workspace

    [ "${COMFY_MODEL_ROOT}" = "${LOCAL_RUNTIME_COMFY}/models" ] || {
        echo "Unexpected COMFY_MODEL_ROOT=${COMFY_MODEL_ROOT}"
        exit 1
    }
)

assert_file_contains "${LOCAL_EXTRA_MODEL_PATHS_FILE}" "base_path: ${LOCAL_RUNTIME_COMFY}"

LOCK_DIR="${WORKSPACE_ROOT}/worker-comfyui/.bootstrap.lock"
mkdir -p "${WORKSPACE_ROOT}/worker-comfyui"

(
    source "${SCRIPT_TO_TEST}"
    acquire_bootstrap_lock "${LOCK_DIR}"
    sleep 2
    release_bootstrap_lock "${LOCK_DIR}"
) &
LOCK_HOLDER_PID=$!

sleep 1
LOCK_WAIT_START=$(date +%s)
(
    export BOOTSTRAP_LOCK_TIMEOUT_SECONDS=10
    export BOOTSTRAP_LOCK_POLL_SECONDS=1
    source "${SCRIPT_TO_TEST}"
    acquire_bootstrap_lock "${LOCK_DIR}"
    release_bootstrap_lock "${LOCK_DIR}"
)
LOCK_WAIT_ELAPSED=$(( $(date +%s) - LOCK_WAIT_START ))
wait "${LOCK_HOLDER_PID}"

[ "${LOCK_WAIT_ELAPSED}" -ge 1 ] || {
    echo "Expected bootstrap lock acquisition to wait for existing holder"
    exit 1
}

mkdir -p "${LOCK_DIR}"
printf '%s\n' $(( $(date +%s) - 10 )) > "${LOCK_DIR}/timestamp"
STALE_WAIT_START=$(date +%s)
(
    export BOOTSTRAP_LOCK_TIMEOUT_SECONDS=10
    export BOOTSTRAP_LOCK_POLL_SECONDS=1
    export BOOTSTRAP_LOCK_STALE_SECONDS=2
    source "${SCRIPT_TO_TEST}"
    acquire_bootstrap_lock "${LOCK_DIR}"
    release_bootstrap_lock "${LOCK_DIR}"
)
STALE_WAIT_ELAPSED=$(( $(date +%s) - STALE_WAIT_START ))

[ "${STALE_WAIT_ELAPSED}" -lt 5 ] || {
    echo "Expected stale bootstrap lock to be cleared promptly"
    exit 1
}

echo "✅ bootstrap_workspace persistence and fallback behavior verified"
