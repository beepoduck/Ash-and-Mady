To create a conda env with the required packages for PaperMage:
- conda env create -f environment.yml
- conda activate papermage
To run pdf_content_extraction_grobid.py, you will need to run docker and the following commands:
- docker pull grobid/grobid:0.8.0
- docker run --rm --init --ulimit core=0 -p 8070:8070 grobid/grobid:0.8.0

