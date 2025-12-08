import os
import papermage as pm
from papermage.recipes import CoreRecipe
from pathlib import Path
import pandas as pd
from tqdm import tqdm
import logging
import json

# Setup logging
logging.basicConfig(
    filename='pdf_content_extraction.log',
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)
def extract(pdf, recipe):
    try:
        doc = recipe.run(str(pdf))

        # Save full doc to .json
        with open(f"extracted_test_json/{pdf.stem}.json", 'w') as f_out:
            json.dump(doc.to_json(with_images=True), f_out, indent=4)
        
        # Extract desired attributes
        # Basic metadata
        title = doc.title if hasattr(doc, 'title') and doc.title else pdf.stem
        
        # Authors
        authors = []
        if hasattr(doc, 'authors') and doc.authors:
            authors = [author.text for author in doc.authors]
        author_str = "; ".join(authors) if authors else ""
        
        # Abstract
        abstract = ""
        if hasattr(doc, 'abstract') and doc.abstract:
            abstract = doc.abstract.text if hasattr(doc.abstract, 'text') else str(doc.abstract)
        
        # Sections
        sections = []
        if doc.sections:
            sections = [section.text for section in doc.sections]
        sections_text = "\n\n".join(sections) if sections else doc.symbols
        
        # Figure captions
        figure_captions = []
        if hasattr(doc, 'figures') and doc.figures:
            for fig in doc.figures:
                if hasattr(fig, 'text') and fig.text:
                    figure_captions.append(fig.text.strip())
        captions_text = "\n\n".join(figure_captions) if figure_captions else ""
        
        # Table captions
        table_captions = []
        if hasattr(doc, 'tables') and doc.tables:
            for table in doc.tables:
                if hasattr(table, 'text') and table.text:
                    table_captions.append(table.text.strip())
        tables_text = "\n\n".join(table_captions) if table_captions else ""
        
        # References
        references = []
        if hasattr(doc, 'references') and doc.references:
            references = [ref.text for ref in doc.references if hasattr(ref, 'text')]
        references_text = "\n\n".join(references) if references else ""
        
        return {
            'filename': pdf.name,
            'title': title,
            'authors': author_str,
            'abstract': abstract,
            'sections': sections_text,
            'figure_captions': captions_text,
            'table_captions': tables_text,
            'references': references_text
        }
    except Exception as e:
        logging.error(f"✗ Failed on {pdf.name}: {str(e)}")
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

    # Process each pdf
    for pdf_path in tqdm(list(pdf_dir.glob("*.pdf"))):
        result = extract(pdf_path, recipe)
        if 'error' not in result:
            results.append(result)
        else:
            failed.append(result)
    # Save all papers to csv
    save_extracted_papers(results, failed, output_name, output_dir_name)

    print(f"Successfully processed: {len(results)} papers")
    print(f"Failed: {len(failed)} papers")
    print(f"Output saved to: {output_name}.csv")

if __name__ == '__main__':
    # Test Run
    main("test_pdfs_1", "test00", "extracted_test_pdfs")