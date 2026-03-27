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
    Returns empty dict (not an error) if the id is 'MISSING' or absent —
    some steps have no parameters defined in the workflow XML.
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

def last_files(parent):
    param(parent, "Raw data files", type="BATCH_LAST_FILES")

def last_peaklists(parent):
    param(parent, "Peak lists", type="BATCH_LAST_PEAKLISTS")

def scan_selection(parent, ms_level):
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


# ── Step builders ─────────────────────────────────────────────────────────────
# Each builder receives (batch_el, params_dict, context_dict) and appends
# one <batchstep> element to batch_el.
#
# context keys available to every builder:
#   mzxml_dir   str   directory of input mzXML files
#   output_dir  str   directory for pipeline outputs
#   ms_level    int   set by dispatcher for mass detection steps only

def build_import(batch, p, ctx):
    step = batchstep(batch,
        "net.sf.mzmine.modules.rawdatamethods.rawdataimport.RawDataImportModule")
    files = param(step, "Raw data file names")
    sub(files, "file", str(Path(ctx["mzxml_dir"]) / "*.mzXML"))


def build_mass_detect(batch, p, ctx):
    """Handles both MS1 and MS2 mass detection.
    The dispatcher sets ctx['ms_level'] from the parameter_set id.
    """
    step = batchstep(batch,
        "net.sf.mzmine.modules.rawdatamethods.massdetection.MassDetectionModule")
    last_files(step)
    scan_selection(step, ctx.get("ms_level", 1))

    noise    = p.get("noise_level", "0")
    detector = param(step, "Mass detector", selected="Centroid")
    module   = sub(detector, "module", name="Centroid")
    sub(module, "parameter", noise, name="Noise level")
    param(step, "Mass list name", "masses")


def build_adap_chrom(batch, p, ctx):
    step = batchstep(batch,
        "net.sf.mzmine.modules.rawdatamethods.peakpicking.adap.ADAPChromatogramBuilderModule")
    last_files(step)
    scan_selection(step, 1)

    # min_time_span (minutes) has no direct scan-count equivalent;
    # 3 scans is a safe floor consistent with ~0.01 min at 4 Hz.
    param(step, "Min group size in # of scans", "3")
    param(step, "Group intensity threshold",    p.get("min_height", "0"))
    param(step, "Min highest intensity",        p.get("min_height", "0"))
    ppm = float(p.get("mz_tolerance", "10"))
    mz_tol(step, ppm)
    param(step, "Suffix", "chromatograms")


def build_deconvolution(batch, p, ctx):
    step = batchstep(batch,
        "net.sf.mzmine.modules.peaklistmethods.peakpicking.deconvolution.DeconvolutionModule")
    last_peaklists(step)
    scan_selection(step, 1)

    algo   = param(step, "Algorithm", selected="Local minimum search")
    module = sub(algo, "module", name="Local minimum search")
    sub(module, "parameter", p.get("chromatographic_threshold", "5"),
        name="Chromatographic threshold (%)")
    sub(module, "parameter", p.get("search_min_rt_range", "0.1"),
        name="Search minimum in RT range (min)")
    sub(module, "parameter", p.get("min_relative_height", "15"),
        name="Minimum relative height (%)")
    sub(module, "parameter", p.get("min_absolute_height", "0"),
        name="Minimum absolute height")
    sub(module, "parameter", p.get("min_ratio_peak_top_edge", "2"),
        name="Min ratio of peak top/edge")

    dur = sub(module, "parameter", name="Peak duration range (min)")
    sub(dur, "min", p.get("peak_duration_min", "0.0"))
    sub(dur, "max", p.get("peak_duration_max", "1.0"))

    # MS2 pairing — 0.01 Da is the tight Haffner window; widen in workflow
    # XML if MS2 spectra are not pairing correctly downstream.
    ms2_mz = param(step, "m/z tolerance (MS2 pairing)")
    sub(ms2_mz, "absolutetolerance", p.get("ms2_pairing_mz_range", "0.01"))
    sub(ms2_mz, "ppmtolerance", "10.0")
    param(step, "RT tolerance (MS2 pairing)", p.get("ms2_pairing_rt_range", "0.1"))
    param(step, "Suffix", "deconvolved")


def build_isotope_grouper(batch, p, ctx):
    step = batchstep(batch,
        "net.sf.mzmine.modules.peaklistmethods.isotopes.deisotoper.IsotopeGrouperModule")
    last_peaklists(step)

    ppm = float(p.get("mz_tolerance", "5"))
    mz_tol(step, ppm, abs_da=0.002)
    param(step, "Retention time tolerance", p.get("rt_tolerance", "0.05"))
    param(step, "Maximum charge",           p.get("max_charge", "2"))

    rep = p.get("representative_isotope", "lowest_mz")
    param(step, "Representative isotope",
          "Lowest m/z" if rep == "lowest_mz" else "Most intense")
    param(step, "Monotonic shape",                    p.get("monotonic_shape", "true"))
    param(step, "Never remove feature with MS2 scan", "true")
    param(step, "Suffix", "deisotoped")


def build_join_aligner(batch, p, ctx):
    step = batchstep(batch,
        "net.sf.mzmine.modules.peaklistmethods.alignment.join.JoinAlignerModule")
    last_peaklists(step)

    ppm = float(p.get("mz_tolerance", "10"))
    mz_tol(step, ppm)
    param(step, "Weight for m/z",           p.get("weight_mz", "5"))
    param(step, "Weight for RT",            p.get("weight_rt", "1"))
    param(step, "Retention time tolerance", p.get("rt_tolerance", "0.5"))
    param(step, "Require same charge state","false")
    param(step, "Require same ID",          "false")
    param(step, "Result peak list name",    "Aligned peaks")


def build_ransac_aligner(batch, p, ctx):
    step = batchstep(batch,
        "net.sf.mzmine.modules.peaklistmethods.alignment.ransac.RansacAlignerModule")
    last_peaklists(step)

    ppm = float(p.get("mz_tolerance", "10"))
    mz_tol(step, ppm)
    param(step, "Retention time tolerance",          p.get("rt_tolerance", "0.5"))
    param(step, "Retention time tolerance after correction",
          p.get("rt_tolerance_after_correction", "0.2"))
    param(step, "RANSAC iterations",                 p.get("ransac_iterations", "1000"))
    param(step, "Minimum number of points",          p.get("min_points", "0.5"))
    param(step, "Threshold value",                   p.get("threshold", "1.0"))
    param(step, "Linear model",                      p.get("linear_model", "false"))
    param(step, "Result peak list name", "Aligned peaks")


def build_row_filter(batch, p, ctx):
    step = batchstep(batch,
        "net.sf.mzmine.modules.peaklistmethods.filtering.rowsfilter.RowsFilterModule")
    last_peaklists(step)

    min_peaks = p.get("min_peaks_per_row") or "1"
    param(step, "Minimum peaks in a row",              min_peaks)
    param(step, "Minimum peaks in an isotope pattern", "1")

    rt_min = p.get("rt_min")
    rt_max = p.get("rt_max")
    if rt_min and rt_max:
        rt_range(step, "Retention time", rt_min, rt_max)

    require_ms2 = p.get("require_ms2_gnps", "false").lower() == "true"
    param(step,
          "Validate 86 annotation by MS2 fragmentation (GNPS)",
          str(require_ms2).lower())
    param(step, "Suffix",                   "filtered")
    param(step, "Reset the peak number ID", "false")


def build_gap_fill(batch, p, ctx):
    step = batchstep(batch,
        "net.sf.mzmine.modules.peaklistmethods.gapfilling.peakfinder.PeakFinderModule")
    last_peaklists(step)

    intensity_tol = p.get("intensity_tolerance", "75")
    param(step, "Intensity tolerance", f"{intensity_tol}%")

    ppm    = float(p.get("mz_tolerance_ppm", "10"))
    abs_da = float(p.get("mz_tolerance_abs", "0.002"))
    mz_tol(step, ppm, abs_da=abs_da)

    param(step, "Retention time tolerance", p.get("rt_tolerance", "0.3"))
    param(step, "RT correction",            p.get("rt_correction", "false"))
    param(step, "Retain original peak list","false")
    param(step, "Suffix",                   "gap-filled")


def build_export_mgf(batch, p, ctx):
    step = batchstep(batch,
        "net.sf.mzmine.modules.peaklistmethods.io.mgfexport.MGFExportModule")
    last_peaklists(step)
    param(step, "Filename",               str(Path(ctx["output_dir"]) / "output.mgf"))
    param(step, "Representative isotope", "Highest intensity")


def build_export_csv(batch, p, ctx):
    step = batchstep(batch,
        "net.sf.mzmine.modules.peaklistmethods.io.csvexport.CSVExportModule")
    last_peaklists(step)
    param(step, "Filename",                str(Path(ctx["output_dir"]) / "feature_table.csv"))
    param(step, "Field separator",         ",")
    param(step, "Identification separator",";")


def build_export_mzmine_xml(batch, p, ctx):
    step = batchstep(batch,
        "net.sf.mzmine.modules.peaklistmethods.io.mztabexport.MzTabExportModule")
    last_peaklists(step)
    param(step, "Filename", str(Path(ctx["output_dir"]) / "output.mzTab"))


# ── Module registry ───────────────────────────────────────────────────────────
# Maps a lowercase keyword (substring of the module label) to a builder.
# Keys are matched in order — put more specific strings before broader ones.

REGISTRY = [
    ("adap chromatogram",        build_adap_chrom),
    ("chromatogram builder",     build_adap_chrom),
    ("mass detection",           build_mass_detect),
    ("deconvolution",            build_deconvolution),
    ("isotop",                   build_isotope_grouper),   # isotope / isotopic
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
    ("mztab",                    build_export_mzmine_xml),
]

def lookup_builder(module_label):
    """Return the builder for a module label, or None if unrecognised."""
    label_lower = module_label.lower()
    for key, builder in REGISTRY:
        if key in label_lower:
            return builder
    return None


# ── Graph parsing ─────────────────────────────────────────────────────────────

def build_op_order(root):
    """
    Parse all L1 controlflow edges and return a topologically sorted list
    of L1 operation node ids. Nodes with no incoming edges come first.
    Within each stage, declaration order is preserved.
    """
    all_ops  = []
    cf_edges = []

    for graph in root.findall(".//graph[@level='L1']"):
        for node in graph.findall(".//node[@type='Operation']"):
            all_ops.append(node.get("id"))
        for edge in graph.findall(".//edge[@type='controlflow']"):
            cf_edges.append((edge.get("source"), edge.get("target")))

    # Kahn's topological sort
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

    # Isolated nodes (no edges at all) appended at end
    seen = set(sorted_ops)
    sorted_ops += [op for op in all_ops if op not in seen]

    return sorted_ops


def get_tool_calls_for_op(root, op_id):
    """
    Given an L1 operation id, walk to its L2 graph and return all
    ToolCall nodes as a list of dicts.
    """
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
    """Infer MS level from parameter set id for mass detection steps."""
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

    # Import step is always first — implied by the mzXML artifact existing,
    # not represented as an L1 Operation node in the workflow XML.
    build_import(batch, {}, ctx)
    print("[generate] + Raw data import")

    # Walk L1 operations in controlflow-derived topological order
    op_order = build_op_order(root)
    skipped  = []

    for op_id in op_order:
        for tc in get_tool_calls_for_op(root, op_id):
            module  = tc["module"] or tc["label"]
            builder = lookup_builder(module)

            if builder is None:
                # Non-MZmine step (R, GNPS, Python, etc.) — skip
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