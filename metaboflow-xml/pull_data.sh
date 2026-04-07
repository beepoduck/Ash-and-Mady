#!/usr/bin/env bash
# pull_data.sh
# Pulls a MassIVE dataset over HTTPS via the ccms-ftp mirror.
# Args:
#   $1  output directory   (default: /data/raw)
#   $2  MassIVE dataset ID (default: MSV000084794)

set -euo pipefail

OUTDIR="${1:-/data/raw}"
DATASET_ID="${2:-MSV000084794}"
SOURCE="https://ccms-ftp.ucsd.edu/${DATASET_ID}/"

echo "[pull_data] Destination: ${OUTDIR}"
echo "[pull_data] Dataset:     ${DATASET_ID}"
echo "[pull_data] Source:      ${SOURCE}"
mkdir -p "${OUTDIR}"

wget   -r   -np   -nH   --cut-dirs=1   --tries=5   --waitretry=5   --timeout=30   --directory-prefix="${OUTDIR}"   --progress=dot:giga   "${SOURCE}"

echo "[pull_data] Done. Raw files written to ${OUTDIR}"