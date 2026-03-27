#!/usr/bin/env python3
"""
get_massive_id.py

Extracts the MassIVE dataset ID from a metabolomics workflow XML file.
Prints the ID to stdout so it can be captured by shell scripts.

Usage:
    python3 get_massive_id.py <workflow_xml_path>

Example:
    DATASET_ID=$(python3 /usr/local/bin/get_massive_id.py /usr/local/share/metabolomics_workflow.xml)
"""

import sys
import xml.etree.ElementTree as ET

def get_massive_id(workflow_xml):
    root = ET.parse(workflow_xml).getroot()
    repo = root.find(".//repository[@name='MassIVE']")
    if repo is None:
        print("ERROR: No <repository name='MassIVE'> found in workflow XML", file=sys.stderr)
        sys.exit(1)
    dataset_id = repo.get("id")
    if not dataset_id:
        print("ERROR: MassIVE repository element has no 'id' attribute", file=sys.stderr)
        sys.exit(1)
    print(dataset_id)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <workflow_xml_path>", file=sys.stderr)
        sys.exit(1)
    get_massive_id(sys.argv[1])