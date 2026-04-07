# metaboflow-xml

A containerized pipeline for executing untargeted LC-MS/MS metabolomics workflows defined in XML. Given a workflow XML file, the pipeline downloads raw MS data from MassIVE, converts files to mzXML, generates a MZmine 2.33 batch file, and runs feature detection and alignment.

Built around the [Haffner et al. 2022](https://github.com/jhaffner09/core_metabolome_2021) fecal metabolomics pipeline (dataset [MSV000084794](https://massive.ucsd.edu/ProteoSAFe/dataset.jsp?task=MSV000084794)), but designed to work with any compatible workflow XML.

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- `wget` — install with `brew install wget`
- **File sharing enabled** in Docker Desktop for your repo directory:
  `Docker Desktop → Settings → Resources → File Sharing → add your directory → Apply & Restart`

---

## Quickstart

```bash
# 1. Clone the repo
git clone https://github.com/your-username/metaboflow-xml.git
cd metaboflow-xml

# 2. Copy the example workflow XML (or bring your own)
cp examples/haffner_2022/metabolomics_workflow.xml workflow.xml

# 3. Run setup — downloads data, builds Docker image, runs pipeline
bash setup.sh
```

That's it. `setup.sh` handles everything in sequence.

Outputs will appear in `./data/` on your machine:

```
data/
├── raw/                  # raw .raw MS files (downloaded from MassIVE)
├── mzxml/                # centroided mzXML files (from MSConvert)
└── output/
    ├── feature_table.csv # aligned, gap-filled feature table
    ├── output.mgf        # MS2 spectra for GNPS FBMN
    ├── output_gnps       # GNPS export files
    └── mzmine_batch.xml  # generated MZmine batch file
```

---

## What setup.sh does

1. Checks that `wget` is installed
2. Creates `./data/raw`, `./data/mzxml`, `./data/output`
3. Reads the dataset ID from `workflow.xml`
4. Downloads raw `.raw` files from MassIVE via FTP into `./data/raw`
5. Builds the Docker image
6. Runs the pipeline inside Docker

Data is downloaded to your Mac natively (not inside Docker), then shared into the container via a volume mount.

---

## Re-running the pipeline

If raw data is already downloaded, `pull_data.sh` skips the download automatically. If mzXML files already exist, MSConvert is skipped too. You can re-run just the pipeline with:

```bash
docker compose up
```

---

## Using your own workflow XML

Replace `workflow.xml` with your own. It must include a MassIVE repository entry:

```xml
<data_availability>
  <repository name="MassIVE" id="YOUR_DATASET_ID"/>
</data_availability>
```

The dataset ID is read automatically — no manual configuration needed.

---

## Overriding directories

All paths are configurable via environment variables in `docker-compose.yml`:

| Variable            | Default                                      | Description                           |
|---------------------|----------------------------------------------|---------------------------------------|
| `RAW_DIR`           | `/data/raw`                                  | Where raw MS files are read from      |
| `MZXML_DIR`         | `/data/mzxml`                                | Where mzXML files are written         |
| `OUTPUT_DIR`        | `/data/output`                               | Where MGF, CSV, batch XML are written |
| `BATCH_XML`         | `/data/output/mzmine_batch.xml`              | Generated MZmine batch file path      |
| `WORKFLOW_XML_PATH` | `/usr/local/share/metabolomics_workflow.xml` | Workflow XML path inside container    |

---

## Project structure

```
metaboflow-xml/
├── Dockerfile
├── docker-compose.yml
├── setup.sh                     # one-command setup: download + pipeline
├── pull_data.sh                 # downloads raw .raw files from MassIVE via wget
├── get_massive_id.py            # reads dataset ID from workflow XML
├── generate_mzmine_batch.py     # generates MZmine 2.33 batch XML from workflow XML
├── pipeline.sh                  # Docker entrypoint: MSConvert → MZmine
├── workflow.xml                 # your workflow XML (bring your own)
├── data/
│   ├── raw/                     # raw MS files (gitignored)
│   ├── mzxml/                   # MSConvert output (gitignored)
│   └── output/                  # MZmine output (gitignored)
└── examples/
    └── haffner_2022/
        └── metabolomics_workflow.xml
```

---

## Pipeline stages

| Stage | Tool | Description |
|---|---|---|
| `stage_ingest` | `pull_data.sh` (wget, runs on Mac) | Downloads raw `.raw` files from MassIVE |
| `stage_convert` | MSConvert (ProteoWizard, runs in Docker) | Converts raw files to centroided mzXML |
| `stage_generate_batch` | `generate_mzmine_batch.py` (runs in Docker) | Builds MZmine 2.33 batch XML from workflow parameters |
| `stage_features` | MZmine 2.33 (runs in Docker) | Runs feature detection, alignment, gap filling, and export |

---

## Requirements

| Tool | Version | Source |
|---|---|---|
| ProteoWizard (MSConvert) | latest | Docker base image |
| MZmine | 2.33 | github.com/mzmine/mzmine2 |
| OpenJDK | 8 | apt |
| Python | 3 | apt |
| wget | system | brew |