import os
import shutil
from pathlib import Path
from sqlalchemy.orm import Session
from src.db.models import Resume
from src.config import ORIGINAL_RESUMES_DIR


class ResumeManager:
    def __init__(self, db: Session):
        self.db = db

    def ingest_resume(self, source_filepath: str, role_tags: str = "") -> Resume:
        """
        Copies a resume from a local source path into ORIGINAL_RESUMES_DIR
        and registers it in the DB. Skips copy if already in the right folder.
        """
        source_path = Path(source_filepath)
        if not source_path.exists():
            raise FileNotFoundError(f"Source resume not found: {source_filepath}")

        filename = source_path.name
        file_ext = source_path.suffix.lower().replace(".", "")
        if file_ext not in ["pdf", "docx"]:
            raise ValueError("Only pdf and docx formats are supported.")

        dest_path = ORIGINAL_RESUMES_DIR / filename

        # Skip copy if source == destination (e.g., already in the right folder)
        if source_path.resolve() != dest_path.resolve():
            shutil.copy2(source_path, dest_path)

        return self._upsert_resume(filename, str(dest_path), file_ext, role_tags)

    def ingest_resume_from_storage(self, filename: str, storage_path: str, role_tags: str = "") -> Resume:
        """
        Registers a resume that has been uploaded to Supabase Storage.
        Stores the supabase-storage:// URL as the filepath.
        """
        file_ext = Path(filename).suffix.lower().replace(".", "")
        if file_ext not in ["pdf", "docx"]:
            raise ValueError("Only pdf and docx formats are supported.")
        return self._upsert_resume(filename, storage_path, file_ext, role_tags)

    def _upsert_resume(self, filename: str, filepath: str, file_ext: str, role_tags: str) -> Resume:
        """Creates or updates a resume record in the DB."""
        existing = self.db.query(Resume).filter(Resume.filename == filename).first()
        if existing:
            existing.filepath = filepath
            existing.role_tags = role_tags
            existing.is_active = True
            resume = existing
        else:
            resume = Resume(
                filename=filename,
                filepath=filepath,
                file_type=file_ext,
                role_tags=role_tags,
                is_active=True
            )
            self.db.add(resume)
        self.db.commit()
        self.db.refresh(resume)
        return resume

    def get_all_active_resumes(self):
        """Returns all active resumes."""
        return self.db.query(Resume).filter(Resume.is_active == True).all()

    def deactivate_resume(self, resume_id: int):
        """Marks a resume as inactive so it won't be scored."""
        resume = self.db.query(Resume).filter(Resume.id == resume_id).first()
        if resume:
            resume.is_active = False
            self.db.commit()
