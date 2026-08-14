#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT_TO_TEST="${REPO_ROOT}/src/bootstrap_ltx25.sh"

TEST_DIR="$(mktemp -d)"
trap 'rm -rf "${TEST_DIR}"' EXIT

BIN_DIR="${TEST_DIR}/bin"
WGET_LOG_FILE="${TEST_DIR}/wget.log"
MODEL_ROOT="${TEST_DIR}/models"
mkdir -p "${BIN_DIR}"

cat > "${BIN_DIR}/wget" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
output_path=""
url=""
while [ "$#" -gt 0 ]; do
    case "$1" in
        -O) output_path="$2"; shift 2 ;;
        --header=*) printf 'header:%s\n' "${1#--header=}" >> "${WGET_LOG_FILE}"; shift ;;
        -nv|-c|-q) shift ;;
        *) url="$1"; shift ;;
    esac
done
[ -n "${output_path}" ] && [ -n "${url}" ]
mkdir -p "$(dirname "${output_path}")"
printf 'url:%s\nout:%s\n' "${url}" "${output_path}" >> "${WGET_LOG_FILE}"
printf 'downloaded:%s\n' "${url}" > "${output_path}"
EOF
chmod +x "${BIN_DIR}/wget"

(
    export PATH="${BIN_DIR}:${PATH}"
    export WGET_LOG_FILE
    export COMFY_MODEL_ROOT="${MODEL_ROOT}"
    export LTX25_DOWNLOAD_BACKEND="wget"
    export HUGGINGFACE_ACCESS_TOKEN="hf-test-token"
    export LTX25_PRELOAD_VARIANT="distilled-int8"
    export LTX25_PRELOAD_PROMPT_ENHANCER=true
    source "${SCRIPT_TO_TEST}"
    bootstrap_ltx25
    bootstrap_ltx25
)

for expected_file in \
    "diffusion_models/ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors" \
    "text_encoders/gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors" \
    "text_encoders/gemma4_e2b_it_bf16.safetensors" \
    "vae/ltx-2.5-video-vae-bf16.safetensors" \
    "vae/ltx-2.5-audio-vae-bf16.safetensors" \
    "latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors"; do
    [ -f "${MODEL_ROOT}/${expected_file}" ] || {
        echo "Expected ${MODEL_ROOT}/${expected_file} to exist"
        exit 1
    }
done

[ "$(grep -c '^url:' "${WGET_LOG_FILE}")" -eq 6 ]
[ "$(grep -c '^header:Authorization: Bearer hf-test-token$' "${WGET_LOG_FILE}")" -eq 6 ]

if (
    export LTX25_PRELOAD_VARIANT="made-up-variant"
    source "${SCRIPT_TO_TEST}"
    bootstrap_ltx25 >/dev/null 2>&1
); then
    echo "Expected unsupported LTX variant to fail"
    exit 1
fi

echo "✅ bootstrap_ltx25 preload behavior verified"
