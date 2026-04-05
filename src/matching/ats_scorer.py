import json
import logging
from src.config import GEMINI_API_KEY, LLM_PROVIDER
from src.db.models import Job

logger = logging.getLogger(__name__)

# gemini-2.5-flash-lite: has a much higher limit (1500 req limit) and works with API key
GEMINI_MODEL = "gemini-2.5-flash-lite"


def _call_gemini_score(job_desc: str, resume_text: str) -> dict:
    """Calls Gemini to score resume vs job description. Returns ats_score + missing_keywords."""
    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)

        from src.config import admin_config
        active_prompt = admin_config["prompt"]["active_prompt"]
        default_prompt = admin_config["prompt"]["default_prompt"]
        
        try:
            prompt = active_prompt.format(
                job_desc=job_desc[:4000],
                resume_text=resume_text[:4000]
            )
        except KeyError as e:
            logger.error(f"Custom prompt missing variable {e}. Falling back to default prompt.")
            prompt = default_prompt.format(
                job_desc=job_desc[:4000],
                resume_text=resume_text[:4000]
            )

        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        result = _parse_json_response(response.text)
        
        score = result.get("ats_score", 0.0)
        if not isinstance(score, (int, float)) or score < 0 or score > 10:
            logger.warning(f"Invalid score returned: {score}. Defaulting to 0.0")
            result["ats_score"] = 0.0
            
        if "review" not in result:
            result["review"] = "No review provided."
            
        return result

    except Exception as e:
        logger.error(f"Gemini scoring error: {e}")
        return {"ats_score": 0.0, "missing_keywords": [], "review": "Error generating review."}


def _parse_json_response(text: str) -> dict:
    """Robustly parses JSON from Gemini response."""
    try:
        # Strip markdown code blocks if present
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].strip()
        text = text.strip()
        return json.loads(text)
    except Exception as e:
        logger.error(f"JSON parse failed: {e}. Raw response: {text[:300]}")
        return {"ats_score": 0.0, "missing_keywords": []}


def calculate_ats_score(job: Job, resume_text: str) -> dict:
    """
    Calculates ATS Score for a job vs resume text.
    Returns: {ats_score, missing_keywords, match_level}
    """
    if not resume_text or not resume_text.strip():
        logger.warning(f"Empty resume text for job {job.id}. Skipping.")
        return {"ats_score": 0.0, "missing_keywords": [], "match_level": "Low"}

    if not job.description or len(job.description.strip()) < 100:
        logger.warning(f"⚠️ Description too short for accurate AI scoring (Job ID: {job.id}). Skipping.")
        return {
            "ats_score": 0.0, 
            "missing_keywords": [], 
            "match_level": "Low", 
            "review": "DESCRIPTION MISSING: Scraper failed to extract full text."
        }

    if LLM_PROVIDER == "gemini" and GEMINI_API_KEY:
        result = _call_gemini_score(job.description, resume_text)
    else:
        logger.warning(f"No LLM configured for '{LLM_PROVIDER}'.")
        result = {"ats_score": 0.0, "missing_keywords": []}

    score = result.get("ats_score", 0.0)

    if score >= 7.0:
        match_level = "Good"
    elif score >= 5.0:
        match_level = "Moderate"
    else:
        match_level = "Low"

    result["match_level"] = match_level
    logger.info(f"    📊 Score: {score:.1f}/10 ({match_level}) | Missing: {result.get('missing_keywords', [])[:3]}")
    return result
