import os
import json
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ==================== WORKFLOW ANALYSIS PROMPT ====================

analysis_prompt = """
Analyze this metabolomics workflow and extract the following information:

1. **has_untargeted_metabolomics**: Does the paper have an untargeted metabolomics workflow? (boolean)
2. **uses_ms**: Does the workflow use mass spectrometry (MS)? (boolean)
3. **uses_lcms**: Does the workflow use LC-MS or UPLC-MS? (boolean)
4. **uses_gcms**: Does the workflow use GC-MS? (boolean)
5. **uses_msms**: Does the workflow use MS/MS or tandem MS? (boolean)
6. **sample_type**: What type of samples were analyzed? (e.g., "zebrafish larvae", "mouse liver", "human aqueous humor", "unspecified")
7. **has_sample_prep**: Is sample preparation explicitly described? (boolean)
8. **has_extraction**: Is metabolite/lipid extraction explicitly described? (boolean)
9. **has_normalization**: Is data normalization explicitly described? (boolean)
10. **uses_pca**: Does the workflow use PCA? (boolean)
11. **uses_plsda**: Does the workflow use PLS-DA? (boolean)
12. **has_statistical_analysis**: Does the workflow include statistical analysis? (boolean)
13. **has_pathway_analysis**: Does the workflow include pathway analysis? (boolean)
14. **uses_kegg**: Does the workflow use KEGG database? (boolean)
15. **num_workflow_steps**: How many workflow steps are described? (integer)
16. **num_tools_mentioned**: How many tools/software are explicitly mentioned? (integer)
17. **num_databases_mentioned**: How many databases/APIs are explicitly mentioned? (integer)
18. **has_annotation**: Does the workflow include metabolite identification/annotation? (boolean)
19. **workflow_completeness**: Rate completeness on scale 1-5 (1=very incomplete, 5=very complete)
20. **main_analytical_platform**: Primary analytical platform (e.g., "UPLC-Q Exactive/MS", "LC-MS", "GC-MS", "unspecified")

Return as JSON with these exact keys.
"""

response_format = {
    "type": "json_schema",
    "json_schema": {
        "name": "workflow_analysis",
        "schema": {
            "type": "object",
            "properties": {
                "has_untargeted_metabolomics": {"type": "boolean"},
                "uses_ms": {"type": "boolean"},
                "uses_lcms": {"type": "boolean"},
                "uses_gcms": {"type": "boolean"},
                "uses_msms": {"type": "boolean"},
                "sample_type": {"type": "string"},
                "has_sample_prep": {"type": "boolean"},
                "has_extraction": {"type": "boolean"},
                "has_normalization": {"type": "boolean"},
                "uses_pca": {"type": "boolean"},
                "uses_plsda": {"type": "boolean"},
                "has_statistical_analysis": {"type": "boolean"},
                "has_pathway_analysis": {"type": "boolean"},
                "uses_kegg": {"type": "boolean"},
                "num_workflow_steps": {"type": "integer"},
                "num_tools_mentioned": {"type": "integer"},
                "num_databases_mentioned": {"type": "integer"},
                "has_annotation": {"type": "boolean"},
                "workflow_completeness": {"type": "integer", "minimum": 1, "maximum": 5},
                "main_analytical_platform": {"type": "string"}
            },
            "required": [
                "has_untargeted_metabolomics",
                "uses_ms",
                "uses_lcms",
                "uses_gcms",
                "uses_msms",
                "sample_type",
                "has_sample_prep",
                "has_extraction",
                "has_normalization",
                "uses_pca",
                "uses_plsda",
                "has_statistical_analysis",
                "has_pathway_analysis",
                "uses_kegg",
                "num_workflow_steps",
                "num_tools_mentioned",
                "num_databases_mentioned",
                "has_annotation",
                "workflow_completeness",
                "main_analytical_platform"
            ]
        }
    }
}

# ==================== ANALYSIS FUNCTIONS ====================

def analyze_workflow_with_gpt(workflow_data, filename):
    """
    Use GPT to analyze a workflow and extract structured information
    """
    try:
        # Convert workflow to JSON string for analysis
        workflow_json = json.dumps(workflow_data, indent=2)
        
        prompt = f"{analysis_prompt}\n\nWorkflow to analyze:\n{workflow_json}"
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert in metabolomics workflows. Analyze the provided workflow data and extract the requested information accurately."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.0,
            response_format=response_format
        )
        
        result = json.loads(response.choices[0].message.content)
        result['filename'] = filename
        
        return result
        
    except Exception as e:
        print(f"  ✗ Error analyzing {filename}: {e}")
        # Return default values on error
        return {
            'filename': filename,
            'has_untargeted_metabolomics': False,
            'uses_ms': False,
            'uses_lcms': False,
            'uses_gcms': False,
            'uses_msms': False,
            'sample_type': 'error',
            'has_sample_prep': False,
            'has_extraction': False,
            'has_normalization': False,
            'uses_pca': False,
            'uses_plsda': False,
            'has_statistical_analysis': False,
            'has_pathway_analysis': False,
            'uses_kegg': False,
            'num_workflow_steps': 0,
            'num_tools_mentioned': 0,
            'num_databases_mentioned': 0,
            'has_annotation': False,
            'workflow_completeness': 0,
            'main_analytical_platform': 'error',
            'error': str(e)
        }

def analyze_workflows_from_json(json_file_path, output_csv_path):
    """
    Load workflows from JSON and create a CSV with structured analysis
    """
    
    print(f"Loading workflows from: {json_file_path}")
    
    # Load the JSON file
    with open(json_file_path, 'r') as f:
        workflows = json.load(f)
    
    print(f"Found {len(workflows)} workflows to analyze")
    print("=" * 80)
    
    results = []
    
    for i, item in enumerate(workflows):
        filename = item.get('filename', f'unknown_{i}')
        workflow = item.get('workflow', {})
        
        print(f"\n[{i+1}/{len(workflows)}] Analyzing: {filename}")
        
        result = analyze_workflow_with_gpt(workflow, filename)
        results.append(result)
        
        if 'error' not in result:
            print(f"  ✓ Analysis complete")
        else:
            print(f"  ✗ Analysis failed: {result['error']}")
    
    # Create DataFrame
    df = pd.DataFrame(results)
    
    # Reorder columns for better readability
    column_order = [
        'filename',
        'has_untargeted_metabolomics',
        'uses_ms',
        'uses_lcms',
        'uses_gcms',
        'uses_msms',
        'main_analytical_platform',
        'sample_type',
        'has_sample_prep',
        'has_extraction',
        'has_normalization',
        'uses_pca',
        'uses_plsda',
        'has_statistical_analysis',
        'has_pathway_analysis',
        'uses_kegg',
        'has_annotation',
        'num_workflow_steps',
        'num_tools_mentioned',
        'num_databases_mentioned',
        'workflow_completeness'
    ]
    
    # Add error column if it exists
    if 'error' in df.columns:
        column_order.append('error')
    
    df = df[column_order]
    
    # Save to CSV
    df.to_csv(output_csv_path, index=False)
    
    print("\n" + "=" * 80)
    print("=== SUMMARY ===")
    print(f"Total workflows analyzed: {len(results)}")
    print(f"\nKey Statistics:")
    print(f"  - Has untargeted metabolomics: {df['has_untargeted_metabolomics'].sum()}/{len(df)}")
    print(f"  - Uses LC-MS: {df['uses_lcms'].sum()}/{len(df)}")
    print(f"  - Uses GC-MS: {df['uses_gcms'].sum()}/{len(df)}")
    print(f"  - Uses MS/MS: {df['uses_msms'].sum()}/{len(df)}")
    print(f"  - Has pathway analysis: {df['has_pathway_analysis'].sum()}/{len(df)}")
    print(f"  - Uses KEGG: {df['uses_kegg'].sum()}/{len(df)}")
    print(f"\nAverage workflow completeness: {df['workflow_completeness'].mean():.2f}/5")
    print(f"\nOutput saved to: {output_csv_path}")
    
    return df

# ==================== MAIN ====================

if __name__ == '__main__':
    # Analyze the workflows from your JSON file
    input_json = "openai_outputs/50_metabolomics_complete_workflows.json"
    output_csv = "50_llm_extracted_pdfs_extracted_workflow_analysis.csv"
    
    df = analyze_workflows_from_json(input_json, output_csv)
    
    # Optional: Print the results
    print("\n" + "=" * 80)
    print("RESULTS PREVIEW:")
    print(df.to_string())