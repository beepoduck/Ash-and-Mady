import os
from pathlib import Path
import pandas as pd
from tqdm import tqdm
import logging
import json
import time
import xml.etree.ElementTree as ET
import requests

# Setup logging
logging.basicConfig(
    filename='grobid_pdf_content_extraction.log',
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)

def extract_with_grobid(pdf, grobid_url="http://localhost:8070"):
    """Extract content using GROBID via direct API calls"""
    start_time = time.time()
    
    try:
        # Call GROBID API
        with open(pdf, 'rb') as f:
            files = {'input': f}
            response = requests.post(
                f'{grobid_url}/api/processFulltextDocument',
                files=files,
                timeout=60
            )
        
        if response.status_code != 200:
            raise Exception(f"GROBID returned status {response.status_code}")
        
        # Parse XML response
        root = ET.fromstring(response.text)
        ns = {'tei': 'http://www.tei-c.org/ns/1.0'}
        
        # Extract title
        title_elem = root.find('.//tei:titleStmt/tei:title', ns)
        title = title_elem.text if title_elem is not None else pdf.stem
        
        # Extract authors
        authors = []
        for author in root.findall('.//tei:sourceDesc//tei:author', ns):
            persName = author.find('.//tei:persName', ns)
            if persName is not None:
                forename = persName.find('tei:forename', ns)
                surname = persName.find('tei:surname', ns)
                name_parts = []
                if forename is not None and forename.text:
                    name_parts.append(forename.text)
                if surname is not None and surname.text:
                    name_parts.append(surname.text)
                if name_parts:
                    authors.append(' '.join(name_parts))
        author_str = "; ".join(authors)
        
        # Extract abstract
        abstract = ""
        abstract_elem = root.find('.//tei:profileDesc/tei:abstract', ns)
        if abstract_elem is not None:
            abstract = ' '.join(abstract_elem.itertext()).strip()
        
        # Extract full text from body
        full_text_parts = []
        body = root.find('.//tei:text/tei:body', ns)
        if body is not None:
            for div in body.findall('.//tei:div', ns):
                text = ' '.join(div.itertext()).strip()
                if text:
                    full_text_parts.append(text)
        full_text = '\n\n'.join(full_text_parts)
        
        # Extract figure captions
        figure_captions = []
        for figure in root.findall('.//tei:figure', ns):
            if figure.get('type') == 'table':
                continue
                
            head = figure.find('tei:head', ns)
            figDesc = figure.find('tei:figDesc', ns)
            
            caption_parts = []
            if head is not None and head.text:
                caption_parts.append(head.text.strip())
            if figDesc is not None:
                desc_text = ' '.join(figDesc.itertext()).strip()
                if desc_text:
                    caption_parts.append(desc_text)
            
            if caption_parts:
                figure_captions.append(' '.join(caption_parts))
        
        captions_text = "\n\n".join(figure_captions)
        
        # Extract table captions
        table_captions = []
        for table in root.findall('.//tei:figure[@type="table"]', ns):
            head = table.find('tei:head', ns)
            figDesc = table.find('tei:figDesc', ns)
            
            caption_parts = []
            if head is not None and head.text:
                caption_parts.append(head.text.strip())
            if figDesc is not None:
                desc_text = ' '.join(figDesc.itertext()).strip()
                if desc_text:
                    caption_parts.append(desc_text)
            
            if caption_parts:
                table_captions.append(' '.join(caption_parts))
        
        tables_text = "\n\n".join(table_captions)
        
        processing_time = time.time() - start_time
        logging.info(f"✓ Successfully processed {pdf.name} with GROBID in {processing_time:.2f}s")
        print(f"  Processed with GROBID in {processing_time:.2f} seconds")
        
        result = {
            'filename': pdf.name,
            'title': title,
            'authors': author_str,
            'abstract': abstract,
            'full_text': full_text,
            'figure_captions': captions_text,
            'table_captions': tables_text
        }
        
        return result
        
    except Exception as e:
        logging.error(f"✗ GROBID failed on {pdf.name}: {str(e)}")
        print(f"GROBID error on {pdf.name}: {str(e)}")
        return {'filename': pdf.name, 'error': str(e)}

def save_extracted_papers(results, failed, output_name, output_dir_name):
    # Create output directory if it doesn't exist
    os.makedirs(output_dir_name, exist_ok=True)
    df = pd.DataFrame(results)
    df.to_csv(f'{output_dir_name}/{output_name}.csv', index=False)

    # Save failed papers
    if failed:
        df_failed = pd.DataFrame(failed)
        df_failed.to_csv(f'{output_dir_name}/{output_name}_failed.csv', index=False)

def main(path_to_pdfs, output_name, output_dir_name, use_grobid=True):
    
    # Test GROBID connection if enabled
    if use_grobid:
        try:
            response = requests.get("http://localhost:8070/api/isalive", timeout=5)
            if response.status_code == 200:
                print("✓ GROBID server is running")
            else:
                print("Warning: GROBID server not responding correctly")
                use_grobid = False
        except Exception as e:
            print(f"Warning: Could not connect to GROBID server: {e}")
            print("Make sure GROBID is running: docker run -t --rm -p 8070:8070 lfoppiano/grobid:0.8.0")
            use_grobid = False
    
    pdf_dir = Path(path_to_pdfs)
    results = []
    failed = []

    # Process PDFs
    pdf_paths = list(pdf_dir.glob("*/*.pdf"))

    successful_count = 0
    failed_count = 0

    # Process each pdf
    for pdf_path in pdf_paths:
        if use_grobid:
            result = extract_with_grobid(pdf_path)
        else:
            result = {'filename': pdf_path.name, 'error': 'GROBID not available'}
            
        if 'error' not in result:
            results.append(result)
            successful_count += 1
            print(f"Successfully processed: {successful_count} papers")         
        else:
            failed.append(result)
            failed_count += 1
            print(f"Failed to process: {failed_count} papers")         

    # Save all papers to csv
    save_extracted_papers(results, failed, output_name, output_dir_name)

    print(f"\n=== Summary ===")
    print(f"Successfully processed: {len(results)} papers")
    print(f"Failed: {len(failed)} papers")
    print(f"Output saved to: {output_dir_name}/{output_name}.csv")

if __name__ == '__main__':
    # Test Run - set use_grobid=False to use PaperMage only
    main("PDF", "test00_grobid", "grobid_extracted_test_pdfs", use_grobid=True)