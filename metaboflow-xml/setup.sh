#!/usr/bin/env bash
# setup.sh
# One-command setup: downloads raw data then runs the pipeline.
#
# Prerequisites:
#   - Docker Desktop (https://www.docker.com/products/docker-desktop)
#   - wget (brew install wget)
#
# Usage:
#   bash setup.sh

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Check wget is available ───────────────────────────────────────
if ! command -v wget &>/dev/null; then
    echo "ERROR: wget not found. Install it with: brew install wget" >&2
    exit 1
fi

# ── Create output directories ─────────────────────────────────────
mkdir -p "${REPO_DIR}/data/raw"          "${REPO_DIR}/data/mzxml"          "${REPO_DIR}/data/output"

# ── Download raw data ─────────────────────────────────────────────
echo "=== Downloading raw data ==="
bash "${REPO_DIR}/pull_data.sh"     "${REPO_DIR}/workflow.xml"     "${REPO_DIR}/data/raw"

# ── Build and run pipeline ────────────────────────────────────────
echo "=== Building Docker image ==="
docker compose -f "${REPO_DIR}/docker-compose.yml" build

echo "=== Running pipeline ==="
docker compose -f "${REPO_DIR}/docker-compose.yml" up