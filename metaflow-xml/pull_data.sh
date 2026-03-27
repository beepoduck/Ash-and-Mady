#!/usr/bin/env bash
# pull_data.sh
# Pulls a MassIVE dataset via wget.
# Args:
#   $1  output directory   (default: /data/raw)
#   $2  MassIVE dataset ID (default: MSV000084794)
#
# Tool:  wget  (params_wget)
# Flags: -r -np -nH --cut-dirs=3

set -euo pipefail

OUTDIR="${1:-/data/raw}"
DATASET_ID="${2:-MSV000084794}"
SOURCE="ftp://massive.ucsd.edu/v02/${DATASET_ID}/"

echo "[pull_data] Destination: ${OUTDIR}"
mkdir -p "${OUTDIR}"

wget \
  -r \
  -np \
  -nH \
  --cut-dirs=3 \
  --directory-prefix="${OUTDIR}" \
  --progress=dot:giga \
  "${SOURCE}"

echo "[pull_data] Done. Raw files written to ${OUTDIR}"