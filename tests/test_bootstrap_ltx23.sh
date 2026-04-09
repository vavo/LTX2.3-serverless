#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT_TO_TEST="${REPO_ROOT}/src/bootstrap_ltx23.sh"

if [ ! -f "${SCRIPT_TO_TEST}" ]; then
    echo "Error: Script not found at ${SCRIPT_TO_TEST}"
    exit 1
fi

TEST_DIR="$(mktemp -d)"
trap 'rm -rf "${TEST_DIR}"' EXIT

BIN_DIR="${TEST_DIR}/bin"
WGET_LOG_FILE="${TEST_DIR}/wget.log"
CHECKPOINT_DIR="${TEST_DIR}/models/checkpoints/LTX-Video"
UPSCALER_DIR="${TEST_DIR}/models/latent_upscale_models/LTX-Video"
LORA_DIR="${TEST_DIR}/models/loras/LTX-Video"

mkdir -p "${BIN_DIR}"

cat > "${BIN_DIR}/wget" <<'EOF'
#!/usr/bin/env bash

set -euo pipefail

output_path=""
url=""

while [ "$#" -gt 0 ]; do
    case "$1" in
        -O)
            output_path="$2"
            shift 2
            ;;
        --header=*)
            printf 'header:%s\n' "${1#--header=}" >> "${WGET_LOG_FILE}"
            shift
            ;;
        -nv|-c|-q)
            shift
            ;;
        *)
            url="$1"
            shift
            ;;
    esac
done

[ -n "${output_path}" ] || { echo "wget mock did not receive -O" >&2; exit 1; }
[ -n "${url}" ] || { echo "wget mock did not receive a URL" >&2; exit 1; }

mkdir -p "$(dirname "${output_path}")"
printf 'url:%s\nout:%s\n' "${url}" "${output_path}" >> "${WGET_LOG_FILE}"
printf 'downloaded:%s\n' "${url}" > "${output_path}"
EOF

chmod +x "${BIN_DIR}/wget"

(
    export PATH="${BIN_DIR}:${PATH}"
    export WGET_LOG_FILE="${WGET_LOG_FILE}"
    export HUGGINGFACE_ACCESS_TOKEN="hf-test-token"
    export LTX23_PRELOAD_VARIANT="distilled"
    export LTX23_PRELOAD_UPSCALERS=true
    export LTX23_CHECKPOINT_DIR="${CHECKPOINT_DIR}"
    export LTX23_UPSCALER_DIR="${UPSCALER_DIR}"
    export LTX23_LORA_DIR="${LORA_DIR}"

    source "${SCRIPT_TO_TEST}"
    bootstrap_ltx23
    bootstrap_ltx23
)

for expected_file in \
    "${CHECKPOINT_DIR}/ltx-2.3-22b-distilled.safetensors" \
    "${UPSCALER_DIR}/ltx-2.3-spatial-upscaler-x1.5-1.0.safetensors" \
    "${UPSCALER_DIR}/ltx-2.3-spatial-upscaler-x2-1.1.safetensors" \
    "${UPSCALER_DIR}/ltx-2.3-temporal-upscaler-x2-1.0.safetensors" \
    "${LORA_DIR}/ltx-2.3-22b-distilled-lora-384.safetensors"; do
    [ -f "${expected_file}" ] || {
        echo "Expected ${expected_file} to exist"
        exit 1
    }
done

[ "$(grep -c '^url:' "${WGET_LOG_FILE}")" -eq 5 ] || {
    echo "Expected exactly 5 downloads on first preload run"
    exit 1
}

[ "$(grep -c '^header:Authorization: Bearer hf-test-token$' "${WGET_LOG_FILE}")" -eq 5 ] || {
    echo "Expected auth header to be forwarded to each download"
    exit 1
}

if (
    export PATH="${BIN_DIR}:${PATH}"
    export WGET_LOG_FILE="${WGET_LOG_FILE}"
    export LTX23_PRELOAD_VARIANT="made-up-variant"
    source "${SCRIPT_TO_TEST}"
    bootstrap_ltx23 >/dev/null 2>&1
); then
    echo "Expected unsupported LTX variant to fail"
    exit 1
fi

echo "✅ bootstrap_ltx23 preload behavior verified"
