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
        Copies a resume from source to the system directory and adds it to the DB.
        """
        source_path = Path(source_filepath)
        if not source_path.exists():
            raise FileNotFoundError(f"Source resume not found: {source_filepath}")
            
        filename = source_path.name
        file_ext = source_path.suffix.lower().replace(".", "")
        
        if file_ext not in ["pdf", "docx"]:
            raise ValueError("Only pdf and docx formats are supported.")
            
        dest_path = ORIGINAL_RESUMES_DIR / filename
        
        # Avoid overwriting directly if name conflicts unless desired, for now we just overwrite
        shutil.copy2(source_path, dest_path)
        
        # Check if already in DB to update, or create new
        existing_resume = self.db.query(Resume).filter(Resume.filename == filename).first()
        if existing_resume:
            existing_resume.filepath = str(dest_path)
            existing_resume.role_tags = role_tags
            existing_resume.is_active = True
            resume = existing_resume
        else:
            resume = Resume(
                filename=filename,
                filepath=str(dest_path),
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
