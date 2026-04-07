# metaboflow-xml

A containerized pipeline for executing untargeted LC-MS/MS metabolomics workflows defined in XML. Given a workflow XML file, the pipeline automatically pulls raw data from MassIVE, converts files to mzXML, generates a MZmine 2.33 batch file, and runs feature detection and alignment.

Built around the [Haffner et al. 2022](https://github.com/jhaffner09/core_metabolome_2021) fecal metabolomics pipeline (dataset [MSV000084794](https://massive.ucsd.edu/ProteoSAFe/dataset.jsp?task=MSV000084794)), but designed to work with any compatible workflow XML.

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- **File sharing enabled** in Docker Desktop for the directory where you clone this repo:
  `Docker Desktop → Settings → Resources → File Sharing → add your directory → Apply & Restart`

---

## Quickstart

```bash
# 1. Clone the repo
git clone https://github.com/your-username/metaboflow-xml.git
cd metaboflow-xml

# 2. Copy the example workflow XML (or bring your own)
cp examples/haffner_2022/metabolomics_workflow.xml workflow.xml

# 3. Create the output directory
mkdir -p data

# 4. Build the Docker image
docker compose build

# 5. Run the pipeline
docker compose up
```

Outputs will appear in `./data/` on your machine:

```
data/
├── raw/          # raw MS files from MassIVE
├── mzxml/        # centroided mzXML files
├── output/
│   ├── output.mgf            # MS2 spectra for GNPS FBMN
│   └── feature_table.csv     # aligned, gap-filled feature table
└── mzmine_batch.xml          # generated MZmine batch file
```

---

## Using your own workflow XML

Replace `workflow.xml` in the repo root with your own workflow XML before running. The file must follow the [metaboflow-xml schema](examples/haffner_2022/metabolomics_workflow.xml) and include a MassIVE repository entry:

```xml
<data_availability>
  <repository name="MassIVE" id="YOUR_DATASET_ID"/>
  ...
</data_availability>
```

The pipeline reads the dataset ID directly from the XML — no manual configuration needed.

---

## Running without Docker Compose

```bash
docker run --rm \
  -v "$(pwd)/data":/data \
  -v "$(pwd)/workflow.xml":/usr/local/share/metabolomics_workflow.xml:ro \
  metaboflow-xml
```

---

## Overriding directories

All paths are configurable via environment variables:

| Variable            | Default                                          | Description                        |
|---------------------|--------------------------------------------------|------------------------------------|
| `RAW_DIR`           | `/data/raw`                                      | Where raw MS files are downloaded  |
| `MZXML_DIR`         | `/data/mzxml`                                    | Where mzXML files are written      |
| `OUTPUT_DIR`        | `/data/output`                                   | Where MGF and CSV are written      |
| `BATCH_XML`         | `/data/mzmine_batch.xml`                         | Generated MZmine batch file path   |
| `WORKFLOW_XML_PATH` | `/usr/local/share/metabolomics_workflow.xml`     | Workflow XML path inside container |

Set these in `docker-compose.yml` or pass with `-e` in `docker run`.

---

## Project structure

```
metaboflow-xml/
├── Dockerfile
├── docker-compose.yml
├── pipeline.sh                  # main entrypoint
├── pull_data.sh                 # downloads raw data from MassIVE
├── get_massive_id.py            # extracts dataset ID from workflow XML
├── generate_mzmine_batch.py     # generates MZmine 2.33 batch XML from workflow XML
├── examples/
│   └── haffner_2022/
│       └── metabolomics_workflow.xml
└── README.md
```

---

## Pipeline stages

| Stage | Script | Description |
|---|---|---|
| `stage_parse` | `get_massive_id.py` | Reads MassIVE dataset ID from workflow XML |
| `stage_ingest` | `pull_data.sh` | Downloads raw MS files from MassIVE via wget |
| `stage_convert` | MSConvert (ProteoWizard) | Converts raw files to centroided mzXML |
| `stage_generate_batch` | `generate_mzmine_batch.py` | Builds MZmine 2.33 batch XML from workflow parameters |
| `stage_features` | MZmine 2.33 | Runs feature detection, alignment, gap filling, and export |

---

## Requirements satisfied by the Docker image

| Tool | Version | Source |
|---|---|---|
| ProteoWizard (MSConvert) | latest | base image |
| MZmine | 2.33 | github.com/mzmine/mzmine2 |
| OpenJDK | 8 | apt |
| Python | 3 | apt |
| wget / curl / rsync | system | apt |