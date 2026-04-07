#!/usr/bin/env bash
# pull_data.sh
# Downloads raw .raw files from MassIVE via wget over FTP.
# Run this on your Mac (not inside Docker) before running the pipeline.
#
# Usage:
#   bash pull_data.sh <workflow_xml> <output_dir>
#
# Example:
#   bash pull_data.sh workflow.xml ./data/raw

set -euo pipefail

WORKFLOW_XML="${1:-workflow.xml}"
OUTDIR="${2:-./data/raw}"

# Read dataset ID from workflow XML
DATASET_ID=$(python3 get_massive_id.py "${WORKFLOW_XML}")
SOURCE="ftp://massive-ftp.ucsd.edu/v02/${DATASET_ID}/raw/Raw_data/pos/"

echo "[pull_data] Dataset:     ${DATASET_ID}"
echo "[pull_data] Source:      ${SOURCE}"
echo "[pull_data] Destination: ${OUTDIR}"
mkdir -p "${OUTDIR}"

# Check if data already present
if [ -n "$(ls -A "${OUTDIR}" 2>/dev/null)" ]; then
    echo "[pull_data] Data already present in ${OUTDIR}, skipping download"
    exit 0
fi

wget   -r   -np   -nH   --cut-dirs=6   --tries=5   --waitretry=5   --timeout=30   --directory-prefix="${OUTDIR}"   --progress=dot:giga   "${SOURCE}"

echo "[pull_data] Done. Raw files written to ${OUTDIR}"