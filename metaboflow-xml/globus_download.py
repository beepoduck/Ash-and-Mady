#!/usr/bin/env python3
"""
globus_download.py

Downloads a MassIVE dataset from the Globus endpoint directly over HTTPS.
No Globus Connect Personal required — authentication is browser-based (one-time).
All transfers use port 443.

Usage:
    python3 globus_download.py \
        --workflow /usr/local/share/metabolomics_workflow.xml \
        --output-dir /data/raw

Prerequisites (installed in downloader container):
    pip install globus-sdk requests
"""

import argparse
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests
import globus_sdk


# ── MassIVE Globus endpoint ───────────────────────────────────────────────────
MASSIVE_ENDPOINT_ID = "a17d7fac-ce06-11e6-9d11-22000a1e3b52"
MASSIVE_HTTPS_BASE  = f"https://g-{MASSIVE_ENDPOINT_ID}.data.globus.org"

# ── Globus native app client ID (public, for CLI-style apps) ─────────────────
# This is the Globus CLI's own client ID — safe to use for scripted access.
CLIENT_ID = "1dec35bd-6517-4e76-b6fc-f92d500636ef"


def get_massive_id(workflow_xml):
    root = ET.parse(workflow_xml).getroot()
    repo = root.find(".//repository[@name='MassIVE']")
    if repo is None:
        print("ERROR: No <repository name='MassIVE'> found in workflow XML",
              file=sys.stderr)
        sys.exit(1)
    dataset_id = repo.get("id")
    if not dataset_id:
        print("ERROR: MassIVE repository element has no 'id' attribute",
              file=sys.stderr)
        sys.exit(1)
    return dataset_id


def authenticate():
    """Browser-based Globus authentication. Returns an authorizer."""
    client = globus_sdk.NativeAppAuthClient(CLIENT_ID)
    client.oauth2_start_flow(
        requested_scopes=[globus_sdk.TransferClient.scopes.all],
        redirect_uri="https://auth.globus.org/v2/web/auth-code",
        prefill_named_grant="metaboflow-xml download"
    )

    auth_url = client.oauth2_get_authorize_url()
    print("\n=== Globus Authentication Required ===")
    print(f"Open this URL in your browser:\n\n  {auth_url}\n")
    auth_code = input("Paste the authorization code here: ").strip()

    tokens = client.oauth2_exchange_code_for_tokens(auth_code)
    transfer_data = tokens.by_resource_server.get("transfer.api.globus.org", {})
    https_token = transfer_data.get("access_token")

    if not https_token:
        print("ERROR: Could not retrieve transfer token", file=sys.stderr)
        sys.exit(1)

    return https_token


def list_files(token, dataset_id, subpath="peak"):
    """List all files under /DATASET_ID/subpath/ on the MassIVE endpoint."""
    url = f"{MASSIVE_HTTPS_BASE}/{dataset_id}/{subpath}/"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers, timeout=30)

    if resp.status_code == 401:
        print("ERROR: Authentication failed — token may have expired", file=sys.stderr)
        sys.exit(1)
    if resp.status_code == 404:
        print(f"ERROR: Path not found: {url}", file=sys.stderr)
        sys.exit(1)
    resp.raise_for_status()

    # Parse directory listing — Globus HTTPS returns an HTML or JSON listing
    # Try JSON first, fall back to parsing hrefs from HTML
    try:
        data = resp.json()
        return [f["name"] for f in data.get("DATA", []) if f.get("type") == "file"]
    except Exception:
        # HTML listing — extract hrefs
        import re
        files = re.findall(r'href="([^"]+\.raw)"', resp.text, re.IGNORECASE)
        return files


def download_file(token, url, dest_path):
    """Download a single file from a Globus HTTPS endpoint."""
    headers = {"Authorization": f"Bearer {token}"}
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    with requests.get(url, headers=headers, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded / total * 100
                    print(f"\r  {dest_path.name}: {pct:.1f}%", end="", flush=True)
    print()


def download_dataset(token, dataset_id, output_dir, subpath="peak"):
    """Download all files in /dataset_id/subpath/ to output_dir."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Check if data already exists — skip download if files are present
    existing = list(output_dir.iterdir())
    if existing:
        print(f"[download] Found {len(existing)} existing files in {output_dir}")
        print(f"[download] Skipping download — delete {output_dir} to re-download")
        return

    print(f"\n[download] Listing files at /{dataset_id}/{subpath}/")
    files = list_files(token, dataset_id, subpath)

    if not files:
        print(f"[download] WARNING: no files found under /{dataset_id}/{subpath}/")
        print("[download] Check the dataset path on app.globus.org")
        return

    print(f"[download] Found {len(files)} files")

    for i, filename in enumerate(files, 1):
        dest = output_dir / filename
        if dest.exists():
            print(f"[download] [{i}/{len(files)}] Skipping {filename} (already exists)")
            continue
        url = f"{MASSIVE_HTTPS_BASE}/{dataset_id}/{subpath}/{filename}"
        print(f"[download] [{i}/{len(files)}] Downloading {filename}")
        try:
            download_file(token, url, dest)
        except Exception as e:
            print(f"\n[download] WARNING: Failed to download {filename}: {e}")
            if dest.exists():
                dest.unlink()   # remove partial file

    print(f"\n[download] Done. Files written to {output_dir}")


def main():
    ap = argparse.ArgumentParser(
        description="Download a MassIVE dataset via Globus HTTPS")
    ap.add_argument("--workflow",    required=True,
                    help="Path to the workflow XML")
    ap.add_argument("--output-dir",  default="/data/raw",
                    help="Directory to write downloaded files")
    ap.add_argument("--subpath",     default="peak",
                    help="Subdirectory on the MassIVE endpoint (default: peak)")
    args = ap.parse_args()

    dataset_id = get_massive_id(args.workflow)
    print(f"[download] Dataset ID: {dataset_id}")

    token = authenticate()
    download_dataset(token, dataset_id, args.output_dir, args.subpath)


if __name__ == "__main__":
    main()