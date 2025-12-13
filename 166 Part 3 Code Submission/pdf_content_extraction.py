import os
import papermage as pm
from papermage.recipes import CoreRecipe
from pathlib import Path
import pandas as pd
from tqdm import tqdm
import logging
import json
import time

# Setup logging
logging.basicConfig(
    filename='pdf_content_extraction.log',
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)
def extract(pdf, recipe):
    start_time = time.time()
    try:
        doc = recipe.run(str(pdf))

        # Create directory if it doesn't exist
        output_dir = Path("extracted_test_json")
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save full doc to .json
        with open(f"extracted_test_json/{pdf.stem}.json", 'w') as f_out:
            json.dump(doc.to_json(with_images=True), f_out, indent=4)
        
        # Extract full text
        full_text = doc.symbols if hasattr(doc, 'symbols') else ""
        
        # Basic metadata
        title = doc.title if hasattr(doc, 'title') and doc.title else pdf.stem
        
        # Authors
        authors = []
        if hasattr(doc, 'authors') and doc.authors:
            for author in doc.authors:
                if hasattr(author, 'text'):
                    authors.append(author.text)
                elif isinstance(author, str):
                    authors.append(author)
        author_str = "; ".join(authors) if authors else ""
        
        # Abstract
        abstract = ""
        if hasattr(doc, 'abstracts') and doc.abstracts:
            abstract = doc.abstracts[0].text if hasattr(doc.abstracts[0], 'text') else str(doc.abstracts[0])
        elif hasattr(doc, 'abstract') and doc.abstract:
            abstract = doc.abstract.text if hasattr(doc.abstract, 'text') else str(doc.abstract)
        
        # # Extract sections with their headers and text
        # section_data = {}
        # if hasattr(doc, 'sections') and doc.sections:
        #     for i, section in enumerate(doc.sections):
        #         # Try to get section header
        #         header = f"Section_{i+1}"
        #         if hasattr(section, 'header') and section.header:
        #             header = section.header.text if hasattr(section.header, 'text') else str(section.header)
                
        #         # Get section text
        #         text = ""
        #         if hasattr(section, 'text'):
        #             text = section.text
                
        #         section_data[header] = text
        
        # Figure captions
        figure_captions = []
        if hasattr(doc, 'figures') and doc.figures:
            for fig in doc.figures:
                if hasattr(fig, 'text') and fig.text:
                    figure_captions.append(fig.text.strip())
        captions_text = "\n\n".join(figure_captions)
        
        # Table captions
        table_captions = []
        if hasattr(doc, 'tables') and doc.tables:
            for table in doc.tables:
                if hasattr(table, 'text') and table.text:
                    table_captions.append(table.text.strip())
        tables_text = "\n\n".join(table_captions)

        # Calculate processing time
        processing_time = time.time() - start_time
        logging.info(f"✓ Successfully processed {pdf.name} in {processing_time:.2f}s")
        print(f"  Processed in {processing_time:.2f} seconds")

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
        logging.error(f"✗ Failed on {pdf.name}: {str(e)}")
        print(f"Error processing {pdf.name}: {str(e)}")
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

def main(path_to_pdfs, output_name, output_dir_name):
    recipe = CoreRecipe()
    pdf_dir = Path(path_to_pdfs)
    results = []
    failed = []

    # Just do first 1
    pdf_paths = list(pdf_dir.glob("*/*.pdf"))[:500]

    successful_count = 0
    failed_count = 0

    # Process each pdf
    for pdf_path in pdf_paths:
        result = extract(pdf_path, recipe)
        if 'error' not in result:
            results.append(result)
            successful_count += 1
            print(f"Successfully processed: {successful_count} papers")         
        else:
            failed.append(result)
            failed_count +=1
            print(f"Failed to process: {failed_count} papers")         

    # Save all papers to csv
    save_extracted_papers(results, failed, output_name, output_dir_name)

    print(f"Successfully processed: {len(results)} papers")
    print(f"Failed: {len(failed)} papers")
    print(f"Output saved to: {output_name}.csv")

if __name__ == '__main__':
    # Test Run
    main("PDF", "test500", "extracted_test_pdfs")