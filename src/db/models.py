from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, ForeignKey
from datetime import datetime
from src.db.database import Base

class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    company = Column(String, index=True)
    location = Column(String)
    description = Column(Text)
    skills = Column(String)
    experience_required = Column(String)
    salary = Column(String)
    link = Column(String, index=True)           # not unique — dedup handled in main.py
    posting_date = Column(String)
    extracted_at = Column(DateTime, default=datetime.utcnow)
    scraped_date = Column(String, default=lambda: datetime.utcnow().strftime('%Y-%m-%d'))

class Resume(Base):
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, unique=True, index=True)
    filepath = Column(String)
    file_type = Column(String)                  # pdf, docx
    role_tags = Column(String)                  # comma-separated
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Score(Base):
    __tablename__ = "scores"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"))
    resume_id = Column(Integer, ForeignKey("resumes.id"))
    ats_score = Column(Float)
    match_level = Column(String)                # Good, Moderate, Low
    missing_keywords = Column(Text)             # comma-separated
    review = Column(Text)                       # general review of the resume
    resume_type = Column(String, default="Original")   # Original or Optimized
    gdrive_link = Column(String, default="")            # Drive link or local path
    created_at = Column(DateTime, default=datetime.utcnow)

class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    report_date = Column(DateTime, default=datetime.utcnow)
    filepath = Column(String)
    jobs_processed = Column(Integer)

class AppSetting(Base):
    __tablename__ = "app_settings"
    
    key = Column(String, primary_key=True, index=True)  # e.g., 'search_roles', 'time_filter'
    value = Column(Text)                                # JSON serialized string
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
