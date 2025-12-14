import os
from openai import OpenAI
from pathlib import Path
import pandas as pd
import json
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ==================== PDF EXTRACTION ====================

def extract_pdf_content(pdf_path, client):
    """Extract content from a PDF using OpenAI API"""
    
    try:
        # Upload PDF to OpenAI
        with open(pdf_path, "rb") as f:
            file = client.files.create(
                file=f,
                purpose="assistants"
            )
        
        print(f"Uploaded file ID: {file.id}")
        
        # Create extraction prompt
        prompt = """
        Extract the following information from this PDF:
        1. Title
        2. Authors (semicolon-separated)
        3. Abstract
        4. Full text content
        5. All figure captions (each separated by double newlines)
        6. All table captions (each separated by double newlines)
        
        Return as json with keys: title, authors, abstract, full_text, figure_captions, table_captions
        Return nothing else.
        """
        
        # Use the Assistants API for file processing
        assistant = client.beta.assistants.create(
            name="PDF Extractor",
            instructions="You extract structured information from academic PDFs.",
            model="gpt-4o",
            tools=[{"type": "file_search"}]
        )
        
        # Create a thread with the file
        thread = client.beta.threads.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                    "attachments": [
                        {
                            "file_id": file.id,
                            "tools": [{"type": "file_search"}]
                        }
                    ]
                }
            ]
        )
        
        # Run the assistant
        run = client.beta.threads.runs.create_and_poll(
            thread_id=thread.id,
            assistant_id=assistant.id
        )
        
        # Get the response
        if run.status == 'completed':
            messages = client.beta.threads.messages.list(thread_id=thread.id)
            response_content = messages.data[0].content[0].text.value
            
            # Try to parse as JSON
            try:
                result = json.loads(response_content)
            except:
                # If not valid JSON, create structured response
                result = {
                    'title': '',
                    'authors': '',
                    'abstract': '',
                    'full_text': response_content,
                    'figure_captions': '',
                    'table_captions': ''
                }
            
            result['filename'] = pdf_path.name
        else:
            raise Exception(f"Run failed with status: {run.status}")
        
        # Cleanup
        client.files.delete(file.id)
        client.beta.assistants.delete(assistant.id)
        
        return result
        
    except Exception as e:
        print(f"Error processing {pdf_path.name}: {e}")
        return {'filename': pdf_path.name, 'error': str(e)}

# ==================== WORKFLOW EXTRACTION ====================

# Prompt for extracting workflow
workflow_prompt_instructions = """
You are an expert in untargeted metabolomics and workflow design.

Given the full text of a metabolomics paper, extract ONLY the untargeted metabolomics workflow
used in the study. Focus on the main experimental and computational steps, in execution order.
The workflow you extract should be detailed enough for a researcher to read and carry out.
Do not omit any details directly relevant to the workflow. Include any relevant tools/APIs/databases
used in the workflow.

Guidelines:
- Include only steps that are explicitly described or clearly implied from the text.
- Do NOT invent tools, databases, or steps that are not supported by the paper.
- Use concise, technical language suitable for a computational systems biology researcher.
- If something is missing or unclear in the paper, mark it as "unspecified" rather than guessing.

Return your answer as JSON following the provided schema exactly.
"""

# JSON Schema for workflow extraction
response_format = {
    "type": "json_schema",
    "json_schema": {
        "name": "metabolomics_workflow_extraction",
        "schema": {
            "type": "object",
            "properties": {
                "paper_has_untargeted_metabolomics": {"type": "boolean"},
                "workflow_steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "step_number": {"type": "integer"},
                            "step_name": {"type": "string"},
                            "description": {"type": "string"},
                            "category": {
                                "type": "string",
                                "description": "High-level category (e.g., sample prep, LC-MS acquisition, preprocessing, feature extraction, normalization, statistics, annotation, pathway analysis)"
                            },
                            "tools_software": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "databases_apis": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "inputs": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "outputs": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "is_explicit_in_paper": {
                                "type": "boolean",
                                "description": "True if this step is explicitly described; false if strongly implied."
                            }
                        },
                        "required": [
                            "step_number",
                            "step_name",
                            "description",
                            "category",
                            "tools_software",
                            "databases_apis",
                            "inputs",
                            "outputs",
                            "is_explicit_in_paper"
                        ]
                    }
                },
                "unspecified_or_omitted_steps": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Important steps that seem missing or under-specified."
                },
                "notes_on_ambiguity": {
                    "type": "string",
                    "description": "Short explanation of any ambiguities or uncertainties in the extracted workflow."
                }
            },
            "required": [
                "paper_has_untargeted_metabolomics",
                "workflow_steps",
                "unspecified_or_omitted_steps",
                "notes_on_ambiguity"
            ]
        }
    }
}

def extract_workflow_from_full_text(full_text: str,
                                    max_retries: int = 3,
                                    retry_delay: float = 5.0):
    """
    Call the GPT model to extract the metabolomics workflow from a paper's full text.
    Returns a Python dict following the response_format JSON schema.
    On failure, returns a dict with error information.
    """

    user_prompt = (
        f"{workflow_prompt_instructions.strip()}\n\n"
        "Full paper text:\n"
        f"{full_text.strip()}\n"
    )

    for attempt in range(1, max_retries + 1):
        try:
            response = client.chat.completions.create(
                model="gpt-4o",  # Changed from gpt-5-nano to gpt-4o
                messages=[
                    {
                        "role": "system",
                        "content": "You are a precise assistant that does not hallucinate or create new information for extracting workflows from scientific papers."
                    },
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.0,
                response_format=response_format
            )
            raw = response.choices[0].message.content.strip()
            # Because response_format enforces JSON, we can parse directly
            result = json.loads(raw)
            return result

        except Exception as e:
            print(f"  [Attempt {attempt}] Error extracting workflow: {e}")
            if attempt == max_retries:
                # Give up and return an error payload
                return {
                    "paper_has_untargeted_metabolomics": False,
                    "workflow_steps": [],
                    "unspecified_or_omitted_steps": [],
                    "notes_on_ambiguity": f"Extraction failed after {max_retries} attempts: {e}"
                }
            time.sleep(retry_delay)

# ==================== COMBINED PIPELINE ====================

def process_pdf_with_workflow(pdf_path, client):
    """
    Complete pipeline: Extract PDF content, then extract workflow
    """
    print(f"\nProcessing: {pdf_path.name}")
    print("=" * 80)
    
    # Step 1: Extract PDF content
    print("Step 1: Extracting PDF content...")
    pdf_content = extract_pdf_content(pdf_path, client)
    
    if 'error' in pdf_content:
        print(f"  ✗ PDF extraction failed: {pdf_content['error']}")
        return pdf_content
    
    print(f"  ✓ PDF extraction successful")
    
    # Step 2: Extract workflow from full text
    print("Step 2: Extracting metabolomics workflow...")
    full_text = pdf_content.get('full_text', '')
    
    if not full_text:
        print("  ✗ No full text available for workflow extraction")
        workflow_result = {
            "paper_has_untargeted_metabolomics": False,
            "workflow_steps": [],
            "unspecified_or_omitted_steps": [],
            "notes_on_ambiguity": "No full text extracted from PDF."
        }
    else:
        workflow_result = extract_workflow_from_full_text(full_text)
        
        if workflow_result.get('paper_has_untargeted_metabolomics', False):
            print(f"  ✓ Workflow extracted ({len(workflow_result.get('workflow_steps', []))} steps)")
        else:
            print("  ⚠ No untargeted metabolomics workflow found")
    
    # Combine results
    combined_result = {
        **pdf_content,
        'workflow_json': json.dumps(workflow_result, ensure_ascii=False)
    }
    
    return combined_result

def batch_process_pdfs_with_workflows(pdf_dir, output_name, output_dir, max_pdfs=5):
    """
    Process multiple PDFs: extract content + workflows
    """
    
    results = []
    failed = []
    
    pdf_paths = list(Path(pdf_dir).glob("*/*.pdf"))[:max_pdfs]
    start_time = time.time()
    print(f"\nProcessing {len(pdf_paths)} PDFs...")
    print("=" * 80)
    
    for i, pdf_path in enumerate(pdf_paths):
        print(f"\n[{i+1}/{len(pdf_paths)}] {pdf_path.name}")
        
        result = process_pdf_with_workflow(pdf_path, client)
        
        if 'error' not in result:
            results.append(result)
            print(f"✓ Successfully processed")
        else:
            failed.append(result)
            print(f"✗ Failed: {result['error']}")
        
        # Rate limiting to avoid API limits
        if i < len(pdf_paths) - 1:  # Don't sleep after last one
            print(f"Sleeping 1s before next PDF...")
            time.sleep(1)
    
    # Save results
    os.makedirs(output_dir, exist_ok=True)
    
    if results:
        df = pd.DataFrame(results)
        df.to_csv(f'{output_dir}/{output_name}.csv', index=False)
        
        # Also save a separate JSON file with just workflows
        workflows_only = []
        for r in results:
            workflows_only.append({
                'filename': r['filename'],
                'title': r.get('title', ''),
                'workflow': json.loads(r['workflow_json'])
            })
        
        with open(f'{output_dir}/{output_name}_workflows.json', 'w') as f:
            json.dump(workflows_only, f, indent=2, ensure_ascii=False)
    
    if failed:
        df_failed = pd.DataFrame(failed)
        df_failed.to_csv(f'{output_dir}/{output_name}_failed.csv', index=False)
    
    processing_time = time.time() - start_time
    print("\n" + "=" * 80)
    print("=== FINAL SUMMARY ===")
    print(f"Successfully processed: {len(results)} papers")
    print(f"Failed: {len(failed)} papers")
    print(f"Runtime for {max_pdfs} papers: {processing_time}")
    print(f"\nOutput files:")
    print(f"  - {output_dir}/{output_name}.csv (all data)")
    print(f"  - {output_dir}/{output_name}_workflows.json (workflows only)")
    if failed:
        print(f"  - {output_dir}/{output_name}_failed.csv (failed papers)")

# ==================== MAIN ====================

if __name__ == '__main__':
    # Process PDFs with both extraction and workflow analysis
    batch_process_pdfs_with_workflows(
        pdf_dir="PDF",
        output_name="50_metabolomics_complete",
        output_dir="openai_outputs",
        max_pdfs=50
    )