from docx import Document
import fitz  # PyMuPDF
from pathlib import Path

def extract_text_from_file(filepath: str) -> str:
    """Extracts text from PDF or DOCX file."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
        
    ext = path.suffix.lower()
    if ext == ".pdf":
        return extract_text_from_pdf(filepath)
    elif ext == ".docx":
        return extract_text_from_docx(filepath)
    else:
        raise ValueError("Unsupported file format. Use .pdf or .docx")

def extract_text_from_pdf(filepath: str) -> str:
    text = ""
    with fitz.open(filepath) as doc:
        for page in doc:
            text += page.get_text() + "\n"
    return text

def extract_text_from_docx(filepath: str) -> str:
    doc = Document(filepath)
    return "\n".join([para.text for para in doc.paragraphs])
