"""
PDF to Markdown converter using pymupdf4llm.
This library is specifically designed for LLM/RAG use cases.
"""

import pymupdf4llm
import re
import sys


def clean_markdown(md_text: str) -> str:
    """Clean up the extracted markdown for better RAG usage."""
    
    # Add a proper header
    header = """# EMU STATUTE
## Statute Establishing the North Cyprus Education Foundation and Eastern Mediterranean University

*Combining statutes: 18/1986, 39/1992, 58/1992, 37/1997, 37/2011*

---

"""
    
    # Clean up excessive whitespace
    md_text = re.sub(r'\n{3,}', '\n\n', md_text)
    
    # Remove page markers if any
    md_text = re.sub(r'---\s*Page \d+\s*---', '', md_text)
    
    return header + md_text


def convert_pdf_to_markdown(pdf_path: str, output_md: str):
    """
    Convert PDF to RAG-optimized markdown using pymupdf4llm.
    This library properly handles:
    - Tables
    - Text structure
    - Headers
    - Lists
    """
    print(f"Converting: {pdf_path}")
    
    # Extract to markdown - this handles tables and structure automatically
    md_text = pymupdf4llm.to_markdown(pdf_path)
    
    # Optional: clean up the output
    md_text = clean_markdown(md_text)
    
    # Write output
    with open(output_md, "w", encoding="utf-8") as f:
        f.write(md_text)
    
    # Stats
    lines = md_text.count('\n')
    tables = md_text.count('|---|')
    
    print(f"\n[OK] Converted to: {output_md}")
    print(f"  - Lines: {lines}")
    print(f"  - Tables detected: {tables}")


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        pdf_path = sys.argv[1]
        output_md = sys.argv[2]
    else:
        pdf_path = "emu_rag_data/1-Statute-EmuStatute.pdf"
        output_md = "emu_rag_data/EMU_Statute.md"
    
    convert_pdf_to_markdown(pdf_path, output_md)
