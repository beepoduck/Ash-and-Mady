#!/usr/bin/env python3
"""
generate_mzmine_batch.py

Generates a MZmine 2.33 batch XML from a metabolomics workflow XML.

Step order is derived from the L1 controlflow graph (topological sort).
Step construction is driven by a registry keyed on MZmine module name,
so any combination of supported steps in any order is handled correctly —
including workflows without gap filling, with alternate aligners, etc.

Usage:
    python3 generate_mzmine_batch.py \
        --workflow metabolomics_workflow.xml \
        --mzxml-dir /data/mzxml \
        --output-dir /data/output \
        --out /data/mzmine_batch.xml
"""

import argparse
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
from pathlib import Path


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_params(root, param_set_id):
    """Return {key: value} for a given <parameter_set id="...">.
    Returns empty dict if the id is 'MISSING' or absent.
    """
    if not param_set_id or param_set_id == "MISSING":
        return {}
    ps = root.find(f".//parameter_set[@id='{param_set_id}']")
    if ps is None:
        return {}
    return {p.get("key"): p.get("value") for p in ps.findall("param")}


def sub(parent, tag, text=None, **attribs):
    el = ET.SubElement(parent, tag, **attribs)
    if text is not None:
        el.text = str(text)
    return el

def param(parent, name, text=None, **attribs):
    return sub(parent, "parameter", text, name=name, **attribs)

def all_files(parent):
    """Raw data files — ALL_FILES selector used by mass detection + chrom builder."""
    param(parent, "Raw data files", type="ALL_FILES")

def last_peaklists(parent):
    param(parent, "Peak lists", type="BATCH_LAST_PEAKLISTS")

def scan_selection(parent, ms_level):
    """MZmine 2.33 scan selector format from reference batch XML."""
    scans = param(parent, "Scans")
    sub(scans, "ms_level", str(ms_level))
    sub(scans, "scan_definition")

def mz_tol(parent, ppm, abs_da=0.0001):
    mzt = param(parent, "m/z tolerance")
    sub(mzt, "absolutetolerance", str(abs_da))
    sub(mzt, "ppmtolerance",      str(ppm))
    return mzt

def rt_tol(parent, name, value):
    """RT tolerance with type='absolute' attribute as in reference."""
    param(parent, name, str(value), type="absolute")

def batchstep(batch, method):
    return sub(batch, "batchstep", method=method)


# ── Step builders ─────────────────────────────────────────────────────────────

def build_import(batch, p, ctx):
    step = batchstep(batch,
        "net.sf.mzmine.modules.rawdatamethods.rawdataimport.RawDataImportModule")
    files = param(step, "Raw data file names")
    mzxml_dir = Path(ctx["mzxml_dir"])
    mzxml_files = sorted(mzxml_dir.glob("*.mzXML"))
    if not mzxml_files:
        print(f"[generate] WARNING: no .mzXML files found in {mzxml_dir}.")
        print(f"[generate]          Ensure MSConvert ran before batch generation.")
        sub(files, "file", str(mzxml_dir / "PLACEHOLDER_run_msconvert_first.mzXML"))
    else:
        for f in mzxml_files:
            sub(files, "file", str(f))
        print(f"[generate] Found {len(mzxml_files)} mzXML files for import")


def build_mass_detect(batch, p, ctx):
    step = batchstep(batch,
        "net.sf.mzmine.modules.rawdatamethods.peakpicking.massdetection.MassDetectionModule")
    all_files(step)
    scan_selection(step, ctx.get("ms_level", 1))

    noise    = p.get("noise_level", "0")
    detector = param(step, "Mass detector", selected="Centroid")
    module   = sub(detector, "module", name="Centroid")
    sub(module, "parameter", noise, name="Noise level")

    param(step, "Mass list name", "masses")
    param(step, "CDF Filename (optional)", selected="false")


def build_chrom_builder(batch, p, ctx):
    """
    Standard MZmine 2.33 Chromatogram Builder (not ADAP).
    Module: masslistmethods.chromatogrambuilder.ChromatogramBuilderModule
    Key differences from ADAP:
      - uses Min time span (min) directly (not scan count)
      - uses Min height (single threshold)
      - references Mass list by name
    """
    step = batchstep(batch,
        "net.sf.mzmine.modules.masslistmethods.chromatogrambuilder.ChromatogramBuilderModule")
    all_files(step)
    scan_selection(step, 1)

    param(step, "Mass list",          "masses")
    param(step, "Min time span (min)", p.get("min_time_span", "0.01"))
    param(step, "Min height",          p.get("min_height", "0"))
    ppm = float(p.get("mz_tolerance", "10"))
    mz_tol(step, ppm)
    param(step, "Suffix", "chromatograms")


def build_deconvolution(batch, p, ctx):
    step = batchstep(batch,
        "net.sf.mzmine.modules.peaklistmethods.peakpicking.deconvolution.DeconvolutionModule")
    last_peaklists(step)
    param(step, "Suffix", "deconvoluted")

    # Workflow XML stores these as percentages (5, 15) but MZmine 2.33
    # expects fractions (0.05, 0.15) — divide by 100.
    chrom_thresh = float(p.get("chromatographic_threshold", "5")) / 100
    min_rel_h    = float(p.get("min_relative_height", "15"))      / 100

    algo   = param(step, "Algorithm", selected="Local minimum search")

    # MZmine 2.33 batch XML includes all algorithm modules even when only
    # one is selected — include stubs for the others to match expected format.
    for name in ["Baseline cut-off", "Noise amplitude", "Savitzky-Golay"]:
        m = sub(algo, "module", name=name)
        sub(m, "parameter", name="Min peak height")
        dur = sub(m, "parameter", name="Peak duration range (min)")
        sub(dur, "min", "0.0")
        sub(dur, "max", "10.0")
        if name == "Baseline cut-off":
            sub(m, "parameter", name="Baseline level")
        elif name == "Noise amplitude":
            sub(m, "parameter", name="Amplitude of noise")
        elif name == "Savitzky-Golay":
            sub(m, "parameter", name="Derivative threshold level")

    lms = sub(algo, "module", name="Local minimum search")
    sub(lms, "parameter", str(chrom_thresh),
        name="Chromatographic threshold")
    sub(lms, "parameter", p.get("search_min_rt_range", "0.1"),
        name="Search minimum in RT range (min)")
    sub(lms, "parameter", str(min_rel_h),
        name="Minimum relative height")
    sub(lms, "parameter", p.get("min_absolute_height", "0"),
        name="Minimum absolute height")
    sub(lms, "parameter", p.get("min_ratio_peak_top_edge", "2"),
        name="Min ratio of peak top/edge")
    dur = sub(lms, "parameter", name="Peak duration range (min)")
    sub(dur, "min", p.get("peak_duration_min", "0.0"))
    sub(dur, "max", p.get("peak_duration_max", "1.0"))

    # Wavelets stubs
    xcms = sub(algo, "module", name="Wavelets (XCMS)")
    sub(xcms, "parameter", "10.0", name="S/N threshold")
    ws = sub(xcms, "parameter", name="Wavelet scales")
    sub(ws, "min", "0.25"); sub(ws, "max", "5.0")
    pdr = sub(xcms, "parameter", name="Peak duration range")
    sub(pdr, "min", "0.0"); sub(pdr, "max", "10.0")
    sub(xcms, "parameter", "Use smoothed data", name="Peak integration method")
    sub(xcms, "parameter", "RCaller", name="R engine")

    adap = sub(algo, "module", name="Wavelets (ADAP)")
    sub(adap, "parameter", "10.0", name="S/N threshold")
    sne = sub(adap, "parameter", name="S/N estimator")
    sub(sne, "module", name="Intensity window SN")
    wcsn = sub(sne, "module", name="Wavelet Coeff. SN")
    sub(wcsn, "parameter", "3.0", name="Peak width mult.")
    sub(wcsn, "parameter", "true", name="abs(wavelet coeffs.)")
    sub(adap, "parameter", "10.0", name="min feature height")
    sub(adap, "parameter", "110.0", name="coefficient/area threshold")
    pdr2 = sub(adap, "parameter", name="Peak duration range")
    sub(pdr2, "min", "0.0"); sub(pdr2, "max", "10.0")
    rtwr = sub(adap, "parameter", name="RT wavelet range")
    sub(rtwr, "min", "0.001"); sub(rtwr, "max", "0.1")

    # MS2 scan pairing — use selected="true" as in reference
    param(step, "m/z range for MS2 scan pairing (Da)",
          p.get("ms2_pairing_mz_range", "0.01"), selected="true")
    param(step, "RT range for MS2 scan pairing (min)",
          p.get("ms2_pairing_rt_range", "0.1"), selected="true")
    param(step, "Remove original peak list", "false")


def build_isotope_grouper(batch, p, ctx):
    step = batchstep(batch,
        "net.sf.mzmine.modules.peaklistmethods.isotopes.deisotoper.IsotopeGrouperModule")
    last_peaklists(step)
    param(step, "Name suffix", "deisotoped")

    ppm = float(p.get("mz_tolerance", "10"))
    mz_tol(step, ppm, abs_da=0.0001)
    rt_tol(step, "Retention time tolerance", p.get("rt_tolerance", "0.05"))

    param(step, "Monotonic shape",      p.get("monotonic_shape", "true"))
    param(step, "Maximum charge",       p.get("max_charge", "2"))

    rep = p.get("representative_isotope", "lowest_mz")
    param(step, "Representative isotope",
          "Lowest m/z" if rep == "lowest_mz" else "Most intense")
    param(step, "Remove original peaklist", "false")


def build_join_aligner(batch, p, ctx):
    step = batchstep(batch,
        "net.sf.mzmine.modules.peaklistmethods.alignment.join.JoinAlignerModule")
    last_peaklists(step)
    param(step, "Peak list name", "Aligned peak list")

    ppm = float(p.get("mz_tolerance", "10"))
    mz_tol(step, ppm)
    param(step, "Weight for m/z",   str(float(p.get("weight_mz", "5"))))
    rt_tol(step, "Retention time tolerance", p.get("rt_tolerance", "0.5"))
    param(step, "Weight for RT",    str(float(p.get("weight_rt", "1"))))
    param(step, "Require same charge state", "false")
    param(step, "Require same ID",           "false")

    cip = param(step, "Compare isotope pattern", selected="false")
    mzt2 = param(cip, "Isotope m/z tolerance")
    sub(mzt2, "absolutetolerance", "0.0001")
    sub(mzt2, "ppmtolerance", "5.0")
    param(cip, "Minimum absolute intensity")
    param(cip, "Minimum score")


def build_ransac_aligner(batch, p, ctx):
    step = batchstep(batch,
        "net.sf.mzmine.modules.peaklistmethods.alignment.ransac.RansacAlignerModule")
    last_peaklists(step)
    param(step, "Peak list name", "Aligned peak list")

    ppm = float(p.get("mz_tolerance", "10"))
    mz_tol(step, ppm)
    rt_tol(step, "Retention time tolerance",
           p.get("rt_tolerance", "0.5"))
    rt_tol(step, "Retention time tolerance after correction",
           p.get("rt_tolerance_after_correction", "0.2"))
    param(step, "RANSAC iterations",        p.get("ransac_iterations", "1000"))
    param(step, "Minimum number of points", p.get("min_points", "0.5"))
    param(step, "Threshold value",          p.get("threshold", "1.0"))
    param(step, "Linear model",             p.get("linear_model", "false"))


def build_row_filter(batch, p, ctx):
    step = batchstep(batch,
        "net.sf.mzmine.modules.peaklistmethods.filtering.rowsfilter.RowsFilterModule")
    last_peaklists(step)
    param(step, "Name suffix", "filtered")

    # Parameters with selected attribute — match reference XML structure
    min_peaks = p.get("min_peaks_per_row") or ""
    param(step, "Minimum peaks in a row",
          min_peaks if min_peaks else None,
          selected="true" if min_peaks else "false")
    param(step, "Minimum peaks in an isotope pattern", selected="false")
    param(step, "m/z",                                 selected="false")

    rt_min = p.get("rt_min")
    rt_max = p.get("rt_max")
    rt_el  = param(step, "Retention time",
                   selected="true" if (rt_min and rt_max) else "false")
    if rt_min and rt_max:
        sub(rt_el, "min", rt_min)
        sub(rt_el, "max", rt_max)

    pdr = param(step, "Peak duration range", selected="false")
    sub(pdr, "min", "0.0"); sub(pdr, "max", "10.0")
    fwhm = param(step, "Chromatographic FWHM", selected="false")
    sub(fwhm, "min", "0.0"); sub(fwhm, "max", "1.0")
    param(step, "Parameter", "No parameters defined")
    param(step, "Only identified?", "false")
    param(step, "Text in identity",  selected="false")
    param(step, "Text in comment",   selected="false")
    param(step, "Keep or remove rows", "Keep rows that match all criteria")

    require_ms2 = p.get("require_ms2_gnps", "false").lower() == "true"
    param(step, "Keep only peaks with MS2 scan (GNPS)",
          str(require_ms2).lower())
    param(step, "Reset the peak number ID",             "false")
    param(step, "Remove source peak list after filtering", "false")


def build_gap_fill(batch, p, ctx):
    step = batchstep(batch,
        "net.sf.mzmine.modules.peaklistmethods.gapfilling.peakfinder.PeakFinderModule")
    last_peaklists(step)
    param(step, "Name suffix", "gap-filled")

    # Workflow XML stores intensity_tolerance as integer percent (75);
    # MZmine 2.33 expects a fraction (0.75) — divide by 100.
    intensity_tol = float(p.get("intensity_tolerance", "75")) / 100
    param(step, "Intensity tolerance", str(intensity_tol))

    ppm    = float(p.get("mz_tolerance_ppm", "10"))
    abs_da = float(p.get("mz_tolerance_abs", "0.000001"))
    mz_tol(step, ppm, abs_da=abs_da)

    rt_tol(step, "Retention time tolerance", p.get("rt_tolerance", "0.3"))
    param(step, "RT correction",            p.get("rt_correction", "false"))
    param(step, "Remove original peak list","false")


def build_export_csv(batch, p, ctx):
    step = batchstep(batch,
        "net.sf.mzmine.modules.peaklistmethods.io.csvexport.CSVExportModule")
    last_peaklists(step)
    param(step, "Filename",
          str(Path(ctx["output_dir"]) / "feature_table.csv"))
    param(step, "Field separator", ",")

    common = param(step, "Export common elements")
    for item in [
        "Export row ID",
        "Export row m/z",
        "Export row retention time",
        "Export row identity (main ID)",
        "Export row identity (all IDs)",
        "Export row identity (main ID + details)",
        "Export row comment",
        "Export row number of detected peaks",
    ]:
        sub(common, "item", item)

    data = param(step, "Export data file elements")
    for item in [
        "Peak status",
        "Peak m/z",
        "Peak RT",
        "Peak RT start",
        "Peak RT end",
        "Peak duration time",
        "Peak height",
        "Peak area",
        "Peak charge",
        "Peak # data points",
        "Peak FWHM",
        "Peak tailing factor",
        "Peak asymmetry factor",
        "Peak m/z min",
        "Peak m/z max",
    ]:
        sub(data, "item", item)

    param(step, "Export quantitation results and other information", "false")
    param(step, "Identification separator", ";")


def build_gnps_export(batch, p, ctx):
    step = batchstep(batch,
        "net.sf.mzmine.modules.peaklistmethods.io.gnpsexport.GNPSExportModule")
    last_peaklists(step)
    param(step, "Filename",
          str(Path(ctx["output_dir"]) / "output_gnps"))
    param(step, "Mass list", "masses")


def build_export_mgf(batch, p, ctx):
    step = batchstep(batch,
        "net.sf.mzmine.modules.peaklistmethods.io.mgfexport.MGFExportModule")
    last_peaklists(step)
    param(step, "Filename",
          str(Path(ctx["output_dir"]) / "output.mgf"))
    param(step, "Fractional m/z values", "false")
    param(step, "Merging Mode",          "Maximum")


def build_export_mztab(batch, p, ctx):
    step = batchstep(batch,
        "net.sf.mzmine.modules.peaklistmethods.io.mztabexport.MzTabExportModule")
    last_peaklists(step)
    param(step, "Filename",
          str(Path(ctx["output_dir"]) / "output.mzTab"))


# ── Module registry ───────────────────────────────────────────────────────────
# Ordered list of (lowercase keyword, builder). More specific keys first.

REGISTRY = [
    ("adap chromatogram",        build_chrom_builder),   # fall through to standard builder
    ("chromatogram builder",     build_chrom_builder),
    ("mass detection",           build_mass_detect),
    ("deconvolution",            build_deconvolution),
    ("isotop",                   build_isotope_grouper),
    ("ransac aligner",           build_ransac_aligner),
    ("join aligner",             build_join_aligner),
    ("row filter",               build_row_filter),
    ("peak list row filter",     build_row_filter),
    ("gap fill",                 build_gap_fill),
    ("peak finder",              build_gap_fill),
    ("export — mgf",             build_export_mgf),
    ("export mgf",               build_export_mgf),
    ("export — csv",             build_export_csv),
    ("export csv",               build_export_csv),
    ("mztab",                    build_export_mztab),
]

def lookup_builder(module_label):
    label_lower = module_label.lower()
    for key, builder in REGISTRY:
        if key in label_lower:
            return builder
    return None


# ── Graph parsing ─────────────────────────────────────────────────────────────

def build_op_order(root):
    all_ops  = []
    cf_edges = []

    for graph in root.findall(".//graph[@level='L1']"):
        for node in graph.findall(".//node[@type='Operation']"):
            all_ops.append(node.get("id"))
        for edge in graph.findall(".//edge[@type='controlflow']"):
            cf_edges.append((edge.get("source"), edge.get("target")))

    op_set     = set(all_ops)
    in_degree  = defaultdict(int)
    successors = defaultdict(list)

    for src, tgt in cf_edges:
        if src in op_set and tgt in op_set:
            successors[src].append(tgt)
            in_degree[tgt] += 1

    queue      = deque(op for op in all_ops if in_degree[op] == 0)
    sorted_ops = []
    while queue:
        op = queue.popleft()
        sorted_ops.append(op)
        for nxt in successors[op]:
            in_degree[nxt] -= 1
            if in_degree[nxt] == 0:
                queue.append(nxt)

    seen = set(sorted_ops)
    sorted_ops += [op for op in all_ops if op not in seen]
    return sorted_ops


def get_tool_calls_for_op(root, op_id):
    op_node = root.find(f".//node[@id='{op_id}']")
    if op_node is None:
        return []
    l2_id = op_node.get("refines_to")
    if not l2_id:
        return []
    l2_graph = root.find(f".//graph[@id='{l2_id}']")
    if l2_graph is None:
        return []
    tool_calls = []
    for node in l2_graph.findall(".//node[@type='ToolCall']"):
        tool_calls.append({
            "label"          : node.get("label", ""),
            "tool"           : node.get("tool", ""),
            "module"         : node.get("module") or node.get("label", ""),
            "parameters_ref" : node.get("parameters_ref", ""),
        })
    return tool_calls


def infer_ms_level(parameters_ref):
    if parameters_ref:
        ref = parameters_ref.lower()
        if "ms2" in ref:
            return 2
        if "ms1" in ref:
            return 1
    return 1


# ── Pretty-print indent (Python < 3.9 compatible) ────────────────────────────

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

    ctx = {
        "mzxml_dir"  : mzxml_dir,
        "output_dir" : output_dir,
    }

    batch = ET.Element("batch")

    build_import(batch, {}, ctx)
    print("[generate] + Raw data import")

    op_order = build_op_order(root)
    skipped  = []

    for op_id in op_order:
        for tc in get_tool_calls_for_op(root, op_id):
            module  = tc["module"] or tc["label"]
            builder = lookup_builder(module)

            if builder is None:
                skipped.append(f"{op_id} / {module}")
                continue

            p        = get_params(root, tc["parameters_ref"])
            step_ctx = dict(ctx)

            if builder is build_mass_detect:
                step_ctx["ms_level"] = infer_ms_level(tc["parameters_ref"])

            builder(batch, p, step_ctx)
            print(f"[generate] + {module}")

    if skipped:
        print("[generate] Skipped (non-MZmine steps):")
        for s in skipped:
            print(f"           - {s}")

    # GNPS export always runs after gap fill / last peaklist step,
    # not driven by the workflow graph (it has no L1 controlflow edges).
    build_gnps_export(batch, {}, ctx)
    print("[generate] + GNPS export")

    indent(batch)
    ET.ElementTree(batch).write(out_path, encoding="UTF-8", xml_declaration=True)
    print(f"[generate] Batch XML written → {out_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Generate a MZmine 2.33 batch XML from a metabolomics workflow XML")
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