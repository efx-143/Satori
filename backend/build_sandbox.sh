#!/usr/bin/env bash
# build_sandbox.sh
# ─────────────────────────────────────────────────────────────────────────────
# Builds the Debug Dojo sandbox Docker image.
# Run once before using the test runner service.
#
# Usage:
#   cd backend
#   chmod +x build_sandbox.sh
#   ./build_sandbox.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

IMAGE_NAME="debug-dojo-sandbox"
IMAGE_TAG="latest"
SANDBOX_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/sandbox" && pwd)"

echo "╔══════════════════════════════════════════════════════╗"
echo "║   Debug Dojo – Building Sandbox Image                ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "  Sandbox dir : $SANDBOX_DIR"
echo "  Image       : $IMAGE_NAME:$IMAGE_TAG"
echo ""

docker build \
    --no-cache \
    --pull \
    --tag "${IMAGE_NAME}:${IMAGE_TAG}" \
    "$SANDBOX_DIR"

echo ""
echo "✅  Build complete: ${IMAGE_NAME}:${IMAGE_TAG}"
echo ""
echo "Quick smoke test (should print JSON results):"
echo '{"code":"def solution(x): return x*2","fn_name":"solution","test_cases":[{"test_id":"t1","input_args":[5],"expected_output":10}],"per_test_timeout":5}' \
    | docker run --rm -i \
        --network none \
        --read-only \
        --tmpfs /tmp:size=16m,noexec,nosuid,nodev \
        --memory 128m --memory-swap 128m \
        --cpus 0.5 \
        --pids-limit 64 \
        --cap-drop ALL \
        --no-new-privileges \
        --user 65534:65534 \
        "${IMAGE_NAME}:${IMAGE_TAG}"
echo ""
echo "✅  Smoke test passed."
