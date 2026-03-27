#!/usr/bin/env python3
"""
generate_mzmine_batch.py

Parses metabolomics_workflow.xml and emits a MZmine 2.33 batch XML
by reading each <parameter_set> and mapping keys to the correct
batchstep module + parameter names.

Usage:
    python generate_mzmine_batch.py \
        --workflow metabolomics_workflow.xml \
        --mzxml-dir /data/mzxml \
        --output-dir /data/output \
        --out /data/mzmine_batch.xml
"""

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path


# ── Parameter extraction ───────────────────────────────────────────────────────

def get_params(root, param_set_id):
    """Return {key: value} for a given <parameter_set id="...">."""
    ps = root.find(f".//parameter_set[@id='{param_set_id}']")
    if ps is None:
        raise ValueError(f"parameter_set '{param_set_id}' not found in workflow XML")
    return {p.get("key"): p.get("value") for p in ps.findall("param")}


# ── XML construction helpers ───────────────────────────────────────────────────

def sub(parent, tag, text=None, **attribs):
    el = ET.SubElement(parent, tag, **attribs)
    if text is not None:
        el.text = str(text)
    return el

def param(parent, name, text=None, **attribs):
    return sub(parent, "parameter", text, name=name, **attribs)

def last_files(parent):
    param(parent, "Raw data files", type="BATCH_LAST_FILES")

def last_peaklists(parent):
    param(parent, "Peak lists", type="BATCH_LAST_PEAKLISTS")

def scan_selection(parent, ms_level):
    """Minimal scan selector block used by several modules."""
    scans = param(parent, "Scans")
    param(scans, "MS level filter", str(ms_level))
    param(scans, "Polarity", "Any")
    param(scans, "Spectrum type", "ANY")
    return scans

def mz_tol(parent, ppm, abs_da=0.002):
    mzt = param(parent, "m/z tolerance")
    sub(mzt, "absolutetolerance", str(abs_da))
    sub(mzt, "ppmtolerance",      str(ppm))
    return mzt

def rt_range(parent, name, lo, hi):
    rng = param(parent, name)
    sub(rng, "min", str(lo))
    sub(rng, "max", str(hi))
    return rng

def batchstep(batch, method):
    return sub(batch, "batchstep", method=method)


# ── Individual step builders ───────────────────────────────────────────────────

def step_import(batch, mzxml_dir):
    step = batchstep(batch,
        "net.sf.mzmine.modules.rawdatamethods.rawdataimport.RawDataImportModule")
    files = param(step, "Raw data file names")
    # At batch-generation time we write a glob sentinel; the caller should
    # expand actual file paths before handing the XML to MZmine, or replace
    # this element with one <file> entry per mzXML.
    sub(files, "file", str(Path(mzxml_dir) / "*.mzXML"))
    return step


def step_mass_detect(batch, p, ms_level):
    """
    MZmine module: Mass Detection
    Workflow params: params_ms1_detection | params_ms2_detection
    Key mapping:
      noise_level  →  Noise level (Centroid detector)
    """
    step = batchstep(batch,
        "net.sf.mzmine.modules.rawdatamethods.massdetection.MassDetectionModule")
    last_files(step)
    scan_selection(step, ms_level)

    detector = param(step, "Mass detector", selected="Centroid")
    module   = sub(detector, "module", name="Centroid")
    sub(module, "parameter", p["noise_level"], name="Noise level")

    param(step, "Mass list name", "masses")
    return step


def step_adap_chrom(batch, p):
    """
    MZmine module: ADAP Chromatogram Builder
    Workflow params: params_chrom_builder
    Key mapping:
      min_time_span  →  Min group size in # of scans
                        (0.01 min @ ~600 ms/scan ≈ 1 scan; use 3 as safe floor)
      min_height     →  Group intensity threshold  AND  Min highest intensity
      mz_tolerance   →  m/z tolerance (ppm)
    """
    step = batchstep(batch,
        "net.sf.mzmine.modules.rawdatamethods.peakpicking.adap.ADAPChromatogramBuilderModule")
    last_files(step)
    scan_selection(step, 1)   # ADAP builder operates on MS1

    # min_time_span (0.01 min) has no direct scan-count equivalent in the XML;
    # 3 scans is a conservative safe minimum consistent with 0.01 min @ ~4 Hz.
    param(step, "Min group size in # of scans", "3")
    param(step, "Group intensity threshold",    p["min_height"])
    param(step, "Min highest intensity",        p["min_height"])
    mz_tol(step, float(p["mz_tolerance"]))
    param(step, "Suffix", "chromatograms")
    return step


def step_deconvolution(batch, p):
    """
    MZmine module: Chromatogram Deconvolution → Local Minimum Search
    Workflow params: params_deconvolution
    Key mapping:
      chromatographic_threshold  →  Chromatographic threshold (%)
      search_min_rt_range        →  Search minimum in RT range (min)
      min_relative_height        →  Minimum relative height (%)
      min_absolute_height        →  Minimum absolute height
      min_ratio_peak_top_edge    →  Min ratio of peak top/edge
      peak_duration_min/max      →  Peak duration range (min)
      ms2_pairing_mz_range       →  m/z tolerance (MS2 pairing) — absolute Da
      ms2_pairing_rt_range       →  RT tolerance (MS2 pairing)
    """
    step = batchstep(batch,
        "net.sf.mzmine.modules.peaklistmethods.peakpicking.deconvolution.DeconvolutionModule")
    last_peaklists(step)
    scan_selection(step, 1)

    algo   = param(step, "Algorithm", selected="Local minimum search")
    module = sub(algo, "module", name="Local minimum search")
    sub(module, "parameter", p["chromatographic_threshold"],
        name="Chromatographic threshold (%)")
    sub(module, "parameter", p["search_min_rt_range"],
        name="Search minimum in RT range (min)")
    sub(module, "parameter", p["min_relative_height"],
        name="Minimum relative height (%)")
    sub(module, "parameter", p["min_absolute_height"],
        name="Minimum absolute height")
    sub(module, "parameter", p["min_ratio_peak_top_edge"],
        name="Min ratio of peak top/edge")

    dur = sub(module, "parameter", name="Peak duration range (min)")
    sub(dur, "min", p["peak_duration_min"])
    sub(dur, "max", p["peak_duration_max"])

    # MS2 scan pairing (0.01 Da — note this is the narrow window flagged in
    # your FBMN troubleshooting; widen to 0.05 Da if MS2 pairing is poor)
    ms2_mz = param(step, "m/z tolerance (MS2 pairing)")
    sub(ms2_mz, "absolutetolerance", p["ms2_pairing_mz_range"])
    sub(ms2_mz, "ppmtolerance",      "10.0")
    param(step, "RT tolerance (MS2 pairing)", p["ms2_pairing_rt_range"])

    param(step, "Suffix", "deconvolved")
    return step


def step_isotope_grouper(batch, p):
    """
    MZmine module: Isotopic Peak Grouper (Deisotoper)
    Workflow params: params_isotope_grouper
    Key mapping:
      mz_tolerance           →  m/z tolerance (ppm + abs)
      rt_tolerance           →  Retention time tolerance
      max_charge             →  Maximum charge
      representative_isotope →  Representative isotope
      monotonic_shape        →  Monotonic shape
    """
    step = batchstep(batch,
        "net.sf.mzmine.modules.peaklistmethods.isotopes.deisotoper.IsotopeGrouperModule")
    last_peaklists(step)
    mz_tol(step, float(p["mz_tolerance"]), abs_da=0.002)
    param(step, "Retention time tolerance", p["rt_tolerance"])
    param(step, "Maximum charge",           p["max_charge"])

    rep = p.get("representative_isotope", "lowest_mz")
    param(step, "Representative isotope",
          "Lowest m/z" if rep == "lowest_mz" else "Most intense")
    param(step, "Monotonic shape",                p.get("monotonic_shape", "true"))
    param(step, "Never remove feature with MS2 scan", "true")
    param(step, "Suffix", "deisotoped")
    return step


def step_join_aligner(batch, p):
    """
    MZmine module: Join Aligner
    Workflow params: params_join_aligner
    Key mapping:
      mz_tolerance  →  m/z tolerance (ppm)
      weight_mz     →  Weight for m/z
      weight_rt     →  Weight for RT
      rt_tolerance  →  Retention time tolerance
    """
    step = batchstep(batch,
        "net.sf.mzmine.modules.peaklistmethods.alignment.join.JoinAlignerModule")
    last_peaklists(step)
    mz_tol(step, float(p["mz_tolerance"]))
    param(step, "Weight for m/z",           p["weight_mz"])
    param(step, "Weight for RT",            p["weight_rt"])
    param(step, "Retention time tolerance", p["rt_tolerance"])
    param(step, "Require same charge state","false")
    param(step, "Require same ID",          "false")
    param(step, "Result peak list name",    "Aligned peaks")
    return step


def step_row_filter(batch, p):
    """
    MZmine module: Peak List Row Filter
    Workflow params: params_row_filter
    Key mapping:
      min_peaks_per_row  →  Minimum peaks in a row (blank → 1)
      rt_min / rt_max    →  Retention time range
      require_ms2_gnps   →  Validate 86 annotation by MS2 fragmentation (GNPS)
    """
    step = batchstep(batch,
        "net.sf.mzmine.modules.peaklistmethods.filtering.rowsfilter.RowsFilterModule")
    last_peaklists(step)

    min_peaks = p.get("min_peaks_per_row") or "1"
    param(step, "Minimum peaks in a row",              min_peaks)
    param(step, "Minimum peaks in an isotope pattern", "1")
    rt_range(step, "Retention time", p["rt_min"], p["rt_max"])

    require_ms2 = p.get("require_ms2_gnps", "false").lower() == "true"
    param(step, "Validate 86 annotation by MS2 fragmentation (GNPS)",
          str(require_ms2).lower())
    param(step, "Suffix",                    "filtered")
    param(step, "Reset the peak number ID",  "false")
    return step


def step_gap_fill(batch, p):
    """
    MZmine module: Gap Filling — Peak Finder
    Workflow params: params_gap_fill
    Key mapping:
      intensity_tolerance   →  Intensity tolerance
      mz_tolerance_ppm      →  m/z tolerance (ppm)
      mz_tolerance_abs      →  m/z tolerance (abs Da)
      rt_tolerance          →  Retention time tolerance
      rt_correction         →  RT correction
    """
    step = batchstep(batch,
        "net.sf.mzmine.modules.peaklistmethods.gapfilling.peakfinder.PeakFinderModule")
    last_peaklists(step)
    param(step, "Intensity tolerance", f"{p['intensity_tolerance']}%")
    mz_tol(step,
           float(p["mz_tolerance_ppm"]),
           abs_da=float(p["mz_tolerance_abs"]))
    param(step, "Retention time tolerance", p["rt_tolerance"])
    param(step, "RT correction",            p.get("rt_correction", "false"))
    param(step, "Retain original peak list","false")
    param(step, "Suffix",                   "gap-filled")
    return step


def step_export_mgf(batch, output_dir):
    step = batchstep(batch,
        "net.sf.mzmine.modules.peaklistmethods.io.mgfexport.MGFExportModule")
    last_peaklists(step)
    param(step, "Filename",              str(Path(output_dir) / "output.mgf"))
    param(step, "Representative isotope","Highest intensity")
    return step


def step_export_csv(batch, output_dir):
    step = batchstep(batch,
        "net.sf.mzmine.modules.peaklistmethods.io.csvexport.CSVExportModule")
    last_peaklists(step)
    param(step, "Filename",               str(Path(output_dir) / "feature_table.csv"))
    param(step, "Field separator",        ",")
    param(step, "Identification separator", ";")
    return step


# ── Pretty-print indent (Python < 3.9 fallback) ───────────────────────────────

def indent(elem, level=0):
    pad = "\n" + "  " * level
    if len(elem):
        elem.text = pad + "  "
        for child in elem:
            indent(child, level + 1)
        child.tail = pad
        elem.tail  = pad
    else:
        elem.tail = pad


# ── Main ──────────────────────────────────────────────────────────────────────

def generate(workflow_xml, mzxml_dir, output_dir, out_path):
    root = ET.parse(workflow_xml).getroot()

    def p(ps_id):
        return get_params(root, ps_id)

    batch = ET.Element("batch")

    step_import(batch, mzxml_dir)
    step_mass_detect(batch,  p("params_ms1_detection"), ms_level=1)
    step_mass_detect(batch,  p("params_ms2_detection"), ms_level=2)
    step_adap_chrom(batch,   p("params_chrom_builder"))
    step_deconvolution(batch, p("params_deconvolution"))
    step_isotope_grouper(batch, p("params_isotope_grouper"))
    step_join_aligner(batch, p("params_join_aligner"))
    step_row_filter(batch,   p("params_row_filter"))
    step_gap_fill(batch,     p("params_gap_fill"))
    step_export_mgf(batch,   output_dir)
    step_export_csv(batch,   output_dir)

    indent(batch)
    ET.ElementTree(batch).write(out_path, encoding="UTF-8", xml_declaration=True)
    print(f"[generate_mzmine_batch] Written → {out_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Generate MZmine 2.33 batch XML from metabolomics_workflow.xml")
    ap.add_argument("--workflow",    default="metabolomics_workflow.xml",
                    help="Path to the workflow XML")
    ap.add_argument("--mzxml-dir",   default="/data/mzxml",
                    help="Directory containing input mzXML files")
    ap.add_argument("--output-dir",  default="/data/output",
                    help="Directory for MZmine outputs (MGF, CSV)")
    ap.add_argument("--out",         default="/data/mzmine_batch.xml",
                    help="Path to write the generated batch XML")
    args = ap.parse_args()

    generate(args.workflow, args.mzxml_dir, args.output_dir, args.out)
