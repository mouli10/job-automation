import io
import fitz          # PyMuPDF
from docx import Document
from pathlib import Path


def extract_text_from_file(filepath: str) -> str:
    """
    Extracts text from a resume file.
    Handles two modes:
      1. supabase-storage://resumes/<filename>  →  downloads from Supabase Storage
      2. /local/path/to/file.pdf               →  reads from local filesystem
    """
    if filepath.startswith("supabase-storage://"):
        filename = filepath.split("/")[-1]
        from src.storage import download_resume_from_storage
        file_bytes = download_resume_from_storage(filename)
        ext = Path(filename).suffix.lower()
        return _extract_from_bytes(file_bytes, ext)

    # Local file fallback
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    with open(str(path), "rb") as f:
        file_bytes = f.read()
    return _extract_from_bytes(file_bytes, path.suffix.lower())


def _extract_from_bytes(file_bytes: bytes, ext: str) -> str:
    """Parse resume content directly from bytes — no temp file needed."""
    if ext == ".pdf":
        text = ""
        with fitz.open(stream=io.BytesIO(file_bytes), filetype="pdf") as doc:
            for page in doc:
                text += page.get_text() + "\n"
        return text
    elif ext == ".docx":
        doc = Document(io.BytesIO(file_bytes))
        return "\n".join([para.text for para in doc.paragraphs])
    else:
        raise ValueError(f"Unsupported file format: {ext}. Use .pdf or .docx")


# ── Backwards-compatible helpers (kept for any direct callers) ────────────────
def extract_text_from_pdf(filepath: str) -> str:
    with open(filepath, "rb") as f:
        return _extract_from_bytes(f.read(), ".pdf")

def extract_text_from_docx(filepath: str) -> str:
    with open(filepath, "rb") as f:
        return _extract_from_bytes(f.read(), ".docx")
