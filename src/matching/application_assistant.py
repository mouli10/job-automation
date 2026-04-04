import json
import logging
from pathlib import Path
import docx
from google import genai
import re

from src.config import GEMINI_API_KEY, admin_config, DATA_DIR

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-2.5-flash-lite"
COVER_LETTERS_DIR = DATA_DIR / "cover_letters"
COVER_LETTERS_DIR.mkdir(parents=True, exist_ok=True)

WHY_FIT_PROMPT = """You are an elite, highly professional Executive Assistant helping a candidate apply for a job.
Write exactly 3 to 4 concise sentences explaining why the candidate is a strong match for the job.

CRITICAL RULES:
1. ONLY rely on facts present in the Application Resume.
2. DO NOT fabricate or exaggerate experience.
3. AVOID generic AI filler ("thrilled to apply", "unique blend of skills", "supporting data-driven decisions").
4. Make it highly structural, factual, and strictly professional.

Job Title: {job_title}
Job Description:
{job_desc}

Applicant Resume:
{resume_text}

Return ONLY the raw 3-4 sentence text block. No markdown, no prefixes.
"""

WHY_NOT_FIT_PROMPT = """You are an elite, highly professional Executive Assistant helping evaluate a candidate's fit for a job.
Write exactly 3 to 4 concise sentences explaining why the candidate is NOT a strong match for this position, focusing on the critical gaps in their experience relative to the job requirements.

CRITICAL RULES:
1. ONLY rely on facts present in the Application Resume compared against the Job Description.
2. DO NOT be rude or overly negative. Be strictly objective and analytical.
3. Clearly identify the missing primary tools, missing years of experience, or missing required credentials (e.g. Master's degree).
4. Make it highly structural, factual, and strictly professional.

Job Title: {job_title}
Job Description:
{job_desc}

Applicant Resume:
{resume_text}

Return ONLY the raw 3-4 sentence text block explaining the gaps. No markdown, no prefixes.
"""

COVER_LETTER_PROMPT = """You are an elite, highly professional Executive Assistant writing a Cover Letter for a candidate.

CRITICAL RULES:
1. Structure cleanly in 3 to 5 paragraphs maximum.
2. 1 Page Maximum limit.
3. DO NOT fabricate or exaggerate experience. Only rely on the provided resume.
4. DO NOT use cringy, exaggerated, or generic AI language ("I am thrilled", "My unique blend", "I am the perfect fit").
5. Focus straight on how the candidate's specific past workflows answer the job's specific technical pain points.
6. Adopt a direct, factual, confident tone.

Job Title: {job_title}
Job Description:
{job_desc}

Applicant Resume:
{resume_text}

Return ONLY the raw text of the Cover Letter. Do not include markdown formatting or fake addresses.
"""

class ApplicationAssistant:
    def __init__(self):
        try:
            self.client = genai.Client(api_key=GEMINI_API_KEY)
        except Exception as e:
            logger.error(f"Failed to initialize Gemini Client for App Assistant: {e}")
            self.client = None

    def _get_resume_text(self, resume_path: str) -> str:
        try:
            from src.resume.parser import extract_text_from_file
            return extract_text_from_file(resume_path)
        except Exception as e:
            logger.error(f"Failed extracting {resume_path} for App Assistant: {e}")
            return ""

    def _sanitize_filename(self, name: str) -> str:
        name = re.sub(r'[^A-Za-z0-9_-]', '_', name)
        return name[:30]

    def process(self, job_obj, resume_path: str, ats_score: float, min_ats: float) -> dict:
        result = {"why_fit": "", "cover_letter_path": ""}
        if not self.client:
            return result

        resume_text = self._get_resume_text(resume_path)
        if not resume_text:
            return result

        job_desc_capped = (job_obj.description or "")[:3500]
        job_title = job_obj.title or "Position"
        
        is_good_fit = (ats_score >= min_ats)

        # Generate Why Fit / Why Not Fit
        try:
            active_prompt = WHY_FIT_PROMPT if is_good_fit else WHY_NOT_FIT_PROMPT
            prompt1 = active_prompt.format(
                job_title=job_title,
                job_desc=job_desc_capped,
                resume_text=resume_text
            )
            resp1 = self.client.models.generate_content(model=GEMINI_MODEL, contents=prompt1)
            result["why_fit"] = resp1.text.strip()
        except Exception as e:
            logger.error(f"Fit Summary generation failed for {job_title}: {e}")

        # Check Cover Letter Toggle (Only run if it's actually a Good Fit)
        app_config = admin_config.get("application_assistant", {})
        if is_good_fit and app_config.get("generate_cover_letter", False):
            try:
                company_name = job_obj.company or "Company"
                safe_company = self._sanitize_filename(company_name)
                safe_role = self._sanitize_filename(job_title)
                
                prompt2 = COVER_LETTER_PROMPT.format(
                    job_title=job_title,
                    job_desc=job_desc_capped,
                    resume_text=resume_text
                )
                resp2 = self.client.models.generate_content(model=GEMINI_MODEL, contents=prompt2)
                cl_text = resp2.text.strip()
                
                # Write to Docx safely
                cl_doc = docx.Document()
                for pg in cl_text.split("\n\n"):
                    if pg.strip():
                        cl_doc.add_paragraph(pg.strip())
                        
                file_name = f"{safe_company}_{safe_role}_CoverLetter.docx"
                file_path = COVER_LETTERS_DIR / file_name
                cl_doc.save(str(file_path))
                
                # Upload to Google Drive seamlessly
                try:
                    from src.storage import upload_resume
                    final_link = upload_resume(str(file_path), str(file_name))
                    result["cover_letter_path"] = final_link
                except Exception as e:
                    logger.error(f"Failed to upload cover letter to Drive, using local: {e}")
                    result["cover_letter_path"] = str(file_name)
                    
                logger.info(f"   [Assistant] Created Cover Letter: {file_name}")
            except Exception as e:
                logger.error(f"Cover Letter generation failed for {job_title}: {e}")

        return result
