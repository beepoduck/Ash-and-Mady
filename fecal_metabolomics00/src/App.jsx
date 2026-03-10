import { useState } from "react";

const workflowData = [
  {
    id: "l0_ingest",
    label: "Access Raw Data",
    level: "L0",
    icon: "⬇",
    color: "#00d4aa",
    children: [
      {
        id: "l1_db",
        label: "Pull from Database",
        level: "L1",
        tool: "MassIVE",
        children: [
          {
            id: "l2_wget",
            label: "wget Download",
            level: "L2",
            tool: "CLI",
            params: [
              { key: "command", value: "wget -r -np -nH --cut-dirs=3" },
              { key: "source", value: "ftp://massive.ucsd.edu/v02/MSV000084794/" },
            ],
            inputs: [],
            outputs: ["raw_files"],
          },
        ],
      },
    ],
  },
  {
    id: "l0_convert",
    label: "Process Raw MS Files",
    level: "L0",
    icon: "⚙",
    color: "#4fc3f7",
    children: [
      {
        id: "l1_convert",
        label: "Convert to mzXML",
        level: "L1",
        tool: "MSConvert",
        children: [
          {
            id: "l2_msconvert",
            label: "MSConvert",
            level: "L2",
            tool: "MSConvert v3.019014",
            params: [
              { key: "output_format", value: "mzXML" },
              { key: "filter", value: "Peak Picking (centroid)" },
            ],
            inputs: ["raw_files"],
            outputs: ["mzxml_files"],
          },
        ],
      },
    ],
  },
  {
    id: "l0_features",
    label: "Generate Feature Table",
    level: "L0",
    icon: "🔬",
    color: "#ab47bc",
    children: [
      {
        id: "l1_ms1detect",
        label: "Mass Detection (MS1)",
        level: "L1",
        tool: "MZmine 2.33",
        children: [
          {
            id: "l2_ms1",
            label: "MS1 Mass Detection",
            level: "L2",
            tool: "MZmine v2.33",
            params: [{ key: "MS1 Noise Level", value: "180,000.0" }],
            inputs: ["mzxml_files"],
            outputs: ["ms1_list"],
          },
        ],
      },
      {
        id: "l1_ms2detect",
        label: "Mass Detection (MS2)",
        level: "L1",
        tool: "MZmine 2.33",
        children: [
          {
            id: "l2_ms2",
            label: "MS2 Mass Detection",
            level: "L2",
            tool: "MZmine v2.33",
            params: [{ key: "MS2 Noise Level", value: "1,000.0" }],
            inputs: ["mzxml_files"],
            outputs: ["ms2_list"],
          },
        ],
      },
      {
        id: "l1_chrom",
        label: "Chromatogram Builder",
        level: "L1",
        tool: "MZmine 2.33",
        children: [
          {
            id: "l2_chrom",
            label: "ADAP Chromatogram Builder",
            level: "L2",
            tool: "MZmine v2.33",
            params: [
              { key: "Min time span (min)", value: "0.01" },
              { key: "Min height", value: "5.40E+05" },
              { key: "m/z tolerance (ppm)", value: "10" },
              { key: "Filter", value: "MS1" },
            ],
            inputs: ["ms1_list", "mzxml_files"],
            outputs: ["chromatograms"],
          },
        ],
      },
      {
        id: "l1_deconv",
        label: "Chromatogram Deconvolution",
        level: "L1",
        tool: "MZmine 2.33",
        children: [
          {
            id: "l2_deconv",
            label: "Local Minimum Search",
            level: "L2",
            tool: "MZmine v2.33",
            params: [
              { key: "Chromatographic Threshold", value: "5%" },
              { key: "Search min RT range", value: "0.10 min" },
              { key: "Min relative height", value: "15%" },
              { key: "Min absolute height", value: "3.00E+05" },
              { key: "Peak duration range", value: "0.01–1.5 min" },
              { key: "MS2 pairing RT range", value: "0.1 min" },
            ],
            inputs: ["chromatograms"],
            outputs: ["deconvolved_peaks"],
          },
        ],
      },
      {
        id: "l1_isotope",
        label: "Isotopic Peak Grouper",
        level: "L1",
        tool: "MZmine 2.33",
        children: [
          {
            id: "l2_isotope",
            label: "Isotopic Peak Grouper",
            level: "L2",
            tool: "MZmine v2.33",
            params: [
              { key: "m/z tolerance (ppm)", value: "0.01" },
              { key: "RT tolerance (min)", value: "0.05" },
              { key: "Max charge", value: "3" },
              { key: "Representative isotope", value: "Lowest m/z" },
            ],
            inputs: ["deconvolved_peaks"],
            outputs: ["grouped_peaks"],
          },
        ],
      },
      {
        id: "l1_align",
        label: "Join Aligner",
        level: "L1",
        tool: "MZmine 2.33",
        children: [
          {
            id: "l2_align",
            label: "Join Aligner",
            level: "L2",
            tool: "MZmine v2.33",
            params: [
              { key: "m/z tolerance (ppm)", value: "10" },
              { key: "Weight for m/z", value: "5" },
              { key: "Weight for RT", value: "1" },
              { key: "RT tolerance (min)", value: "0.5" },
            ],
            inputs: ["grouped_peaks"],
            outputs: ["aligned_table"],
          },
        ],
      },
      {
        id: "l1_rowfilter",
        label: "Peak List Row Filter",
        level: "L1",
        tool: "MZmine 2.33",
        children: [
          {
            id: "l2_rowfilter",
            label: "Row Filter",
            level: "L2",
            tool: "MZmine v2.33",
            params: [
              { key: "RT range (min)", value: "0.2–12.51" },
              { key: "Keep only peaks with MS2 (GNPS)", value: "Yes" },
            ],
            inputs: ["aligned_table"],
            outputs: ["filtered_table"],
          },
        ],
      },
      {
        id: "l1_gapfill",
        label: "Gap Filling",
        level: "L1",
        tool: "MZmine 2.33",
        children: [
          {
            id: "l2_gapfill",
            label: "Peak Finder (Gap Fill)",
            level: "L2",
            tool: "MZmine v2.33",
            params: [
              { key: "Intensity tolerance (%)", value: "75" },
              { key: "m/z tolerance (ppm)", value: "10" },
              { key: "RT tolerance (min)", value: "0.3" },
              { key: "RT correction", value: "Yes" },
            ],
            inputs: ["filtered_table"],
            outputs: ["gapfilled_table"],
          },
        ],
      },
      {
        id: "l1_output",
        label: "Export Features",
        level: "L1",
        tool: "MZmine 2.33",
        children: [
          {
            id: "l2_mgf",
            label: "Export MGF",
            level: "L2",
            tool: "MZmine v2.33",
            params: [{ key: "Format", value: ".mgf" }],
            inputs: ["gapfilled_table"],
            outputs: ["mgf_file"],
          },
          {
            id: "l2_csv",
            label: "Export CSV",
            level: "L2",
            tool: "MZmine v2.33",
            params: [{ key: "Format", value: ".csv" }],
            inputs: ["gapfilled_table"],
            outputs: ["csv_feature_table"],
          },
        ],
      },
    ],
  },
  {
    id: "l0_process",
    label: "Process Feature Table",
    level: "L0",
    icon: "📊",
    color: "#ffb74d",
    children: [
      {
        id: "l1_blank",
        label: "Blank Filtering",
        level: "L1",
        tool: "R / Jupyter",
        children: [
          {
            id: "l2_blank",
            label: "Blank Filter Script",
            level: "L2",
            tool: "R Script (Jupyter Notebook)",
            params: [{ key: "Parameters", value: "See R script" }],
            inputs: ["csv_feature_table"],
            outputs: ["blank_filtered_csv"],
          },
        ],
      },
      {
        id: "l1_featfilter",
        label: "Feature Filtering",
        level: "L1",
        tool: "R / Jupyter",
        children: [
          {
            id: "l2_featfilter",
            label: "6-Sample Filter",
            level: "L2",
            tool: "R Script (Jupyter Notebook)",
            params: [
              {
                key: "Script",
                value: "CoreMetabolome_6SampleFiltering_R_Processing.ipynb",
              },
            ],
            inputs: ["blank_filtered_csv"],
            outputs: ["feature_filtered_csv"],
          },
        ],
      },
      {
        id: "l1_norm",
        label: "TIC Normalization",
        level: "L1",
        tool: "R / Jupyter",
        children: [
          {
            id: "l2_norm",
            label: "Total Ion Current Norm.",
            level: "L2",
            tool: "R Script (Jupyter Notebook)",
            params: [
              {
                key: "Script",
                value: "CoreMetabolome_Data_Normalization_code.ipynb",
              },
            ],
            inputs: ["feature_filtered_csv"],
            outputs: ["normalized_csv"],
          },
        ],
      },
    ],
  },
  {
    id: "l0_annotate",
    label: "Annotate Features",
    level: "L0",
    icon: "🏷",
    color: "#ef5350",
    children: [
      {
        id: "l1_fbmn",
        label: "Spectral DB Search (FBMN)",
        level: "L1",
        tool: "GNPS FBMN",
        children: [
          {
            id: "l2_fbmn",
            label: "Feature-Based Molecular Networking",
            level: "L2",
            tool: "GNPS FBMN",
            params: [
              { key: "Precursor mass tolerance", value: "0.02 Da" },
              { key: "Fragment tolerance", value: "0.02 Da" },
              { key: "Min cosine score", value: "0.7" },
              { key: "Min matched MS2 fragments", value: "4" },
              { key: "Network topK", value: "50" },
              { key: "Max component size", value: "100" },
              { key: "Analog search", value: "Enabled" },
              { key: "Normalization", value: "Row sum per file" },
            ],
            inputs: ["mgf_file", "normalized_csv"],
            outputs: ["network_results", "library_hits"],
          },
        ],
      },
    ],
  },
  {
    id: "l0_evaluate",
    label: "Evaluate Annotations",
    level: "L0",
    icon: "✓",
    color: "#26c6da",
    children: [
      {
        id: "l1_visual",
        label: "Visual Evaluation",
        level: "L1",
        tool: "Manual / Cytoscape",
        children: [
          {
            id: "l2_mirror",
            label: "Mirror Plot / Cosine Score",
            level: "L2",
            tool: "Cytoscape v3.7.1",
            params: [
              { key: "Method", value: "Mirror plot similarity" },
              { key: "Metric", value: "Cosine score + match likelihood" },
            ],
            inputs: ["network_results"],
            outputs: ["evaluated_annotations"],
          },
        ],
      },
      {
        id: "l1_classif",
        label: "Molecular Classification",
        level: "L1",
        tool: "MolNetEnhancer / ClassyFire",
        children: [
          {
            id: "l2_classif",
            label: "MolNetEnhancer + ClassyFire",
            level: "L2",
            tool: "MolNetEnhancer / ClassyFire",
            params: [{ key: "Input", value: "Shared metabolites from network" }],
            inputs: ["network_results"],
            outputs: ["class_annotations"],
          },
        ],
      },
      {
        id: "l1_masst",
        label: "Dataset Matching (MASST)",
        level: "L1",
        tool: "MASST",
        children: [
          {
            id: "l2_masst",
            label: "MASST Search",
            level: "L2",
            tool: "MASST",
            params: [
              { key: "Parent mass tolerance", value: "0.02 Da" },
              { key: "Min matched peaks", value: "4" },
              { key: "Score threshold", value: "0.7" },
              { key: "Databases", value: "GNPS, Metabolomics Workbench, MetaboLights, Foodomics" },
            ],
            inputs: ["library_hits"],
            outputs: ["masst_results"],
          },
        ],
      },
    ],
  },
  {
    id: "l0_stats",
    label: "Statistical Analysis",
    level: "L0",
    icon: "📈",
    color: "#66bb6a",
    children: [
      {
        id: "l1_mmvec",
        label: "Microbe–Metabolite Vectors",
        level: "L1",
        tool: "QIIME2 mmvec",
        children: [
          {
            id: "l2_mmvec",
            label: "mmvec + PCA",
            level: "L2",
            tool: "QIIME2 / R (Jupyter)",
            params: [{ key: "Script", value: "R_code_for_mmvec_PCA_plots.ipynb" }],
            inputs: ["normalized_csv"],
            outputs: ["pca_plots"],
          },
        ],
      },
      {
        id: "l1_diversity",
        label: "Beta Diversity (PCoA)",
        level: "L1",
        tool: "QIIME2 / EMPeror",
        children: [
          {
            id: "l2_pcoa",
            label: "PCoA + PERMANOVA",
            level: "L2",
            tool: "QIIME2 EMPeror",
            params: [{ key: "Test", value: "PERMANOVA (beta diversity)" }],
            inputs: ["normalized_csv"],
            outputs: ["pcoa_plots"],
          },
        ],
      },
      {
        id: "l1_rf",
        label: "Random Forest",
        level: "L1",
        tool: "R",
        children: [
          {
            id: "l2_rf",
            label: "Random Forest Classifier",
            level: "L2",
            tool: "R",
            params: [
              { key: "Trees", value: "200 (plateau from OOB error)" },
              { key: "Downstream", value: "SIRIUS v4.4.26 + CANOPUS" },
            ],
            inputs: ["class_annotations"],
            outputs: ["rf_features", "class_level_annotations"],
          },
        ],
      },
      {
        id: "l1_plots",
        label: "Plots & Stats",
        level: "L1",
        tool: "R / Python",
        children: [
          {
            id: "l2_plots",
            label: "Boxplots, UpSet, ANOVA",
            level: "L2",
            tool: "R (ggplot2), Python (UpSetPlot, matplotlib)",
            params: [
              { key: "Boxplot stats", value: "Median, IQR, 1.5×IQR whiskers" },
              { key: "Significance", value: "Kruskal-Wallis, ANOVA (effect size)" },
              { key: "UpSet plots", value: "Python 3, pandas, UpSetPlot" },
            ],
            inputs: ["normalized_csv"],
            outputs: ["figures"],
          },
        ],
      },
    ],
  },
];

const levelColors = {
  L0: { bg: "#0d1117", border: "rgba(255,255,255,0.12)", badge: "#1a2332" },
  L1: { bg: "#0a1628", border: "rgba(255,255,255,0.08)" },
  L2: { bg: "#071020", border: "rgba(255,255,255,0.06)" },
};

const artifactColors = {
  raw_files: "#607d8b",
  mzxml_files: "#546e7a",
  ms1_list: "#5c6bc0",
  ms2_list: "#5c6bc0",
  chromatograms: "#7e57c2",
  deconvolved_peaks: "#8e24aa",
  grouped_peaks: "#9c27b0",
  aligned_table: "#00897b",
  filtered_table: "#00897b",
  gapfilled_table: "#00acc1",
  mgf_file: "#ef5350",
  csv_feature_table: "#ef5350",
  blank_filtered_csv: "#ff7043",
  feature_filtered_csv: "#ff7043",
  normalized_csv: "#ffa726",
  network_results: "#26c6da",
  library_hits: "#26c6da",
  evaluated_annotations: "#26a69a",
  class_annotations: "#26a69a",
  masst_results: "#29b6f6",
  pca_plots: "#66bb6a",
  pcoa_plots: "#66bb6a",
  rf_features: "#81c784",
  class_level_annotations: "#a5d6a7",
  figures: "#aed581",
};

function ArtifactTag({ name, type = "output" }) {
  const color = artifactColors[name] || "#607d8b";
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        background: `${color}22`,
        border: `1px solid ${color}55`,
        color: color,
        borderRadius: 4,
        padding: "2px 7px",
        fontSize: 10,
        fontFamily: "'IBM Plex Mono', monospace",
        letterSpacing: "0.03em",
      }}
    >
      {type === "input" ? "↳" : "→"} {name.replace(/_/g, " ")}
    </span>
  );
}

function ParamRow({ k, v }) {
  return (
    <div style={{ display: "flex", gap: 8, alignItems: "baseline", marginBottom: 3 }}>
      <span
        style={{
          color: "#8899aa",
          fontSize: 10,
          fontFamily: "'IBM Plex Mono', monospace",
          minWidth: 140,
          flexShrink: 0,
        }}
      >
        {k}
      </span>
      <span
        style={{
          color: "#ccd9e8",
          fontSize: 11,
          fontFamily: "'IBM Plex Mono', monospace",
          wordBreak: "break-all",
        }}
      >
        {v}
      </span>
    </div>
  );
}

function L2Node({ node }) {
  const [open, setOpen] = useState(false);
  return (
    <div
      style={{
        background: "#060d18",
        border: "1px solid rgba(255,255,255,0.06)",
        borderRadius: 8,
        marginBottom: 6,
        overflow: "hidden",
      }}
    >
      <div
        onClick={() => setOpen(!open)}
        style={{
          padding: "8px 12px",
          display: "flex",
          alignItems: "center",
          gap: 10,
          cursor: "pointer",
          userSelect: "none",
        }}
      >
        <span style={{ color: "#445566", fontSize: 10, fontFamily: "'IBM Plex Mono', monospace" }}>
          L3
        </span>
        <span
          style={{
            background: "#1a2744",
            color: "#7eb3f5",
            borderRadius: 4,
            padding: "1px 7px",
            fontSize: 10,
            fontFamily: "'IBM Plex Mono', monospace",
          }}
        >
          {node.tool}
        </span>
        <span style={{ color: "#99b0cc", fontSize: 12, flex: 1 }}>{node.label}</span>
        <span style={{ color: "#445566", fontSize: 10 }}>{open ? "▲" : "▼"}</span>
      </div>
      {open && (
        <div style={{ padding: "0 12px 12px 12px", borderTop: "1px solid rgba(255,255,255,0.05)" }}>
          {node.inputs.length > 0 && (
            <div style={{ marginTop: 8, marginBottom: 6 }}>
              <div style={{ color: "#445566", fontSize: 9, fontFamily: "'IBM Plex Mono', monospace", marginBottom: 4, letterSpacing: "0.08em" }}>
                INPUTS
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                {node.inputs.map((a) => (
                  <ArtifactTag key={a} name={a} type="input" />
                ))}
              </div>
            </div>
          )}
          <div style={{ marginBottom: 8 }}>
            <div style={{ color: "#445566", fontSize: 9, fontFamily: "'IBM Plex Mono', monospace", marginBottom: 4, letterSpacing: "0.08em", marginTop: 8 }}>
              PARAMETERS
            </div>
            {node.params.map((p) => (
              <ParamRow key={p.key} k={p.key} v={p.value} />
            ))}
          </div>
          {node.outputs.length > 0 && (
            <div>
              <div style={{ color: "#445566", fontSize: 9, fontFamily: "'IBM Plex Mono', monospace", marginBottom: 4, letterSpacing: "0.08em" }}>
                OUTPUTS
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                {node.outputs.map((a) => (
                  <ArtifactTag key={a} name={a} type="output" />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function L1Node({ node }) {
  const [open, setOpen] = useState(false);
  return (
    <div
      style={{
        background: "#0a1628",
        border: "1px solid rgba(255,255,255,0.07)",
        borderRadius: 10,
        marginBottom: 6,
        overflow: "hidden",
      }}
    >
      <div
        onClick={() => setOpen(!open)}
        style={{
          padding: "10px 14px",
          display: "flex",
          alignItems: "center",
          gap: 10,
          cursor: "pointer",
          userSelect: "none",
        }}
      >
        <span style={{ color: "#334455", fontSize: 10, fontFamily: "'IBM Plex Mono', monospace" }}>
          L2
        </span>
        <div
          style={{
            width: 6,
            height: 6,
            borderRadius: "50%",
            background: "#5577aa",
            flexShrink: 0,
          }}
        />
        <span style={{ color: "#b8ccdd", fontSize: 13, flex: 1 }}>{node.label}</span>
        {node.tool && (
          <span
            style={{
              color: "#556677",
              fontSize: 10,
              fontFamily: "'IBM Plex Mono', monospace",
              background: "rgba(255,255,255,0.04)",
              padding: "1px 6px",
              borderRadius: 3,
            }}
          >
            {node.tool}
          </span>
        )}
        <span style={{ color: "#334455", fontSize: 10, marginLeft: 4 }}>{open ? "▲" : "▼"}</span>
      </div>
      {open && node.children && (
        <div style={{ padding: "4px 14px 12px 14px", borderTop: "1px solid rgba(255,255,255,0.04)" }}>
          {node.children.map((child) => (
            <L2Node key={child.id} node={child} />
          ))}
        </div>
      )}
    </div>
  );
}

function L0Node({ node, index, total }) {
  const [open, setOpen] = useState(false);
  return (
    <div
      style={{
        flex: "1 1 0",
        minWidth: 0,
        position: "relative",
      }}
    >
      {/* connector line */}
      {index < total - 1 && (
        <div
          style={{
            position: "absolute",
            right: -16,
            top: 28,
            width: 32,
            height: 2,
            background: `linear-gradient(90deg, ${node.color}66, ${node.color}22)`,
            zIndex: 10,
          }}
        />
      )}
      <div
        style={{
          background: "#0d1117",
          border: `1px solid ${open ? node.color + "55" : "rgba(255,255,255,0.1)"}`,
          borderRadius: 14,
          overflow: "hidden",
          transition: "border-color 0.2s",
          boxShadow: open ? `0 0 24px ${node.color}18` : "none",
        }}
      >
        {/* Stage header */}
        <div
          onClick={() => setOpen(!open)}
          style={{
            padding: "14px 16px",
            cursor: "pointer",
            userSelect: "none",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
            <span
              style={{
                background: `${node.color}22`,
                border: `1px solid ${node.color}44`,
                color: node.color,
                borderRadius: 5,
                padding: "2px 8px",
                fontSize: 10,
                fontFamily: "'IBM Plex Mono', monospace",
                letterSpacing: "0.05em",
              }}
            >
              L0
            </span>
            <span style={{ color: node.color, fontSize: 18 }}>{node.icon}</span>
          </div>
          <div
            style={{
              color: "#e8f0f8",
              fontSize: 13,
              fontWeight: 600,
              lineHeight: 1.3,
              letterSpacing: "0.01em",
              marginBottom: 8,
            }}
          >
            {node.label}
          </div>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ color: "#334455", fontSize: 10, fontFamily: "'IBM Plex Mono', monospace" }}>
              {node.children?.length || 0} operations
            </span>
            <div
              style={{
                width: 22,
                height: 22,
                borderRadius: "50%",
                border: `1px solid ${node.color}44`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: node.color,
                fontSize: 9,
              }}
            >
              {open ? "▲" : "▼"}
            </div>
          </div>
        </div>

        {/* Expanded content */}
        {open && node.children && (
          <div
            style={{
              padding: "0 12px 12px 12px",
              borderTop: `1px solid ${node.color}22`,
            }}
          >
            <div
              style={{
                paddingTop: 10,
              }}
            >
              {node.children.map((child) => (
                <L1Node key={child.id} node={child} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function App() {
  const [activeLevel, setActiveLevel] = useState("all");

  const levelLabels = [
    { id: "all", label: "All Levels" },
    { id: "L0", label: "L0 — Stages" },
    { id: "L1", label: "L1 — Operations" },
    { id: "L2", label: "L2 — Tools" },
    { id: "L3", label: "L3 — Params" },
  ];

  const nodeTypeLegend = [
    { color: "#00d4aa", label: "Stage (Goal)" },
    { color: "#5577aa", label: "Operation" },
    { color: "#7eb3f5", label: "ToolCall" },
    { color: "#ffa726", label: "Artifact" },
  ];

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#060b13",
        fontFamily: "'IBM Plex Sans', sans-serif",
        color: "#ccd9e8",
        padding: "32px 24px",
      }}
    >
      <link
        href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@300;400;600;700&display=swap"
        rel="stylesheet"
      />

      {/* Header */}
      <div style={{ maxWidth: 1400, margin: "0 auto 32px auto" }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", flexWrap: "wrap", gap: 16 }}>
          <div>
            <div
              style={{
                color: "#445566",
                fontSize: 10,
                fontFamily: "'IBM Plex Mono', monospace",
                letterSpacing: "0.12em",
                marginBottom: 6,
              }}
            >
              WORKFLOW · MSV000084794 · HAFFNER ET AL. 2022
            </div>
            <h1
              style={{
                fontSize: 26,
                fontWeight: 700,
                color: "#e8f4ff",
                margin: 0,
                letterSpacing: "-0.02em",
              }}
            >
              Untargeted Fecal Metabolomics Pipeline
            </h1>
            <p style={{ color: "#556677", fontSize: 13, margin: "6px 0 0 0" }}>
              Hierarchical LC-MS/MS workflow · L0 → L1 → L2 → L3 expansion
            </p>
          </div>

          {/* Legend */}
          <div
            style={{
              background: "#0a1220",
              border: "1px solid rgba(255,255,255,0.07)",
              borderRadius: 10,
              padding: "12px 16px",
              display: "flex",
              gap: 16,
              flexWrap: "wrap",
            }}
          >
            {nodeTypeLegend.map((item) => (
              <div key={item.label} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <div
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: "50%",
                    background: item.color,
                  }}
                />
                <span style={{ color: "#778899", fontSize: 11, fontFamily: "'IBM Plex Mono', monospace" }}>
                  {item.label}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Instruction */}
        <div
          style={{
            marginTop: 20,
            background: "rgba(0,212,170,0.05)",
            border: "1px solid rgba(0,212,170,0.15)",
            borderRadius: 8,
            padding: "10px 16px",
            color: "#5faaa0",
            fontSize: 12,
            fontFamily: "'IBM Plex Mono', monospace",
          }}
        >
          ↓ Click any stage to expand operations · Click operations to reveal tool calls · Click tool calls for parameters &amp; artifacts
        </div>
      </div>

      {/* Main pipeline grid */}
      <div style={{ maxWidth: 1400, margin: "0 auto" }}>
        {/* Top row: first 4 stages */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(4, 1fr)",
            gap: 16,
            marginBottom: 16,
          }}
        >
          {workflowData.slice(0, 4).map((node, i) => (
            <L0Node key={node.id} node={node} index={i} total={4} />
          ))}
        </div>

        {/* Arrow between rows */}
        <div style={{ display: "flex", justifyContent: "center", margin: "4px 0 12px 0" }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              color: "#1e3040",
            }}
          >
            {[...Array(7)].map((_, i) => (
              <span key={i} style={{ fontSize: 8 }}>▶</span>
            ))}
          </div>
        </div>

        {/* Bottom row: last 3 stages */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, 1fr)",
            gap: 16,
          }}
        >
          {workflowData.slice(4).map((node, i) => (
            <L0Node key={node.id} node={node} index={i} total={3} />
          ))}
        </div>
      </div>

      {/* Footer */}
      <div
        style={{
          maxWidth: 1400,
          margin: "32px auto 0 auto",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          borderTop: "1px solid rgba(255,255,255,0.05)",
          paddingTop: 16,
          flexWrap: "wrap",
          gap: 8,
        }}
      >
        <div style={{ color: "#223344", fontSize: 10, fontFamily: "'IBM Plex Mono', monospace" }}>
          MZmine v2.33 · MSConvert v3.019014 · GNPS FBMN · QIIME2 · Cytoscape v3.7.1 · SIRIUS v4.4.26
        </div>
        <div style={{ color: "#223344", fontSize: 10, fontFamily: "'IBM Plex Mono', monospace" }}>
          github.com/jhaffner09/core_metabolome_2021
        </div>
      </div>
    </div>
  );
}

