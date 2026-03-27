#!/usr/bin/env bash
# pipeline.sh
# Entrypoint for metabolomics workflow pipeline.
# Driven by a user-supplied metabolomics_workflow.xml mounted at WORKFLOW_XML_PATH.

set -euo pipefail

RAW_DIR="${RAW_DIR:-/data/raw}"
MZXML_DIR="${MZXML_DIR:-/data/mzxml}"
OUTPUT_DIR="${OUTPUT_DIR:-/data/output}"
BATCH_XML="${BATCH_XML:-/data/mzmine_batch.xml}"
WORKFLOW_XML_PATH="${WORKFLOW_XML_PATH:-/usr/local/share/metabolomics_workflow.xml}"

# ── Validate workflow XML is present ──────────────────────────────
if [ ! -f "${WORKFLOW_XML_PATH}" ]; then
    echo "ERROR: Workflow XML not found at ${WORKFLOW_XML_PATH}" >&2
    echo "       Mount your workflow XML with:" >&2
    echo "       -v /path/to/your_workflow.xml:${WORKFLOW_XML_PATH}" >&2
    exit 1
fi

# ── Extract MassIVE dataset ID from workflow XML ───────────────────
echo "=== [stage_parse] Reading dataset ID from workflow XML ==="
DATASET_ID=$(python3 /usr/local/bin/get_massive_id.py "${WORKFLOW_XML_PATH}")
echo "[stage_parse] Dataset ID: ${DATASET_ID}"

# ── Stage: Access Raw Data ─────────────────────────────────────────
echo "=== [stage_ingest] Pulling raw data from MassIVE ==="
bash /usr/local/bin/pull_data.sh "${RAW_DIR}" "${DATASET_ID}"

# ── Stage: Process Raw MS Files ────────────────────────────────────
echo "=== [stage_convert] Converting to centroided mzXML ==="
mkdir -p "${MZXML_DIR}"
wine msconvert "${RAW_DIR}"/*.raw \
  --mzXML \
  --filter "peakPicking centroid ms1-2" \
  --outdir "${MZXML_DIR}"

# ── Stage: Generate MZmine batch XML ──────────────────────────────
echo "=== [stage_generate_batch] Generating MZmine 2.33 batch XML ==="
mkdir -p "${OUTPUT_DIR}"
python3 /usr/local/bin/generate_mzmine_batch.py \
  --workflow   "${WORKFLOW_XML_PATH}" \
  --mzxml-dir  "${MZXML_DIR}" \
  --output-dir "${OUTPUT_DIR}" \
  --out        "${BATCH_XML}"

# ── Stage: Generate Feature Table (MZmine 2.33 batch) ─────────────
echo "=== [stage_features] Running MZmine batch ==="
/opt/MZmine-2.33/startMZmine_Linux.sh "${BATCH_XML}"

echo "=== Pipeline complete. Outputs written to ${OUTPUT_DIR} ==="