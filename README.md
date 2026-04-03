# AI Job Search & Resume Optimization System

A fully automated, production-grade AI pipeline to scrape job listings, score resumes based on Job Descriptions (ATS match), intelligently rewrite bullets, and email a daily Excel report.

## Architecture

* **Scraper**: Playwright-based module to extract job postings.
* **Database**: SQLite (SQLAlchemy) to store Jobs, Resumes, and Scores.
* **Matcher**: Extract parsed text (`python-docx`, `PyMuPDF`) and score (0-10) using an LLM.
* **Optimizer**: Rewrite resume bullets using `python-docx` while maintaining layout.
* **Orchestrator**: `apscheduler` daily runner + `pandas` Excel generator.

## Setup Instructions

1. **Virtual Environment**:
```bash
python3 -m venv venv
source venv/bin/activate
```

2. **Install Dependencies**:
```bash
pip install -r requirements.txt
playwright install chromium
```

3. **Environment Setup**:
Copy `.env.example` to `.env` and configure it:
```bash
cp .env.example .env
```
- `GEMINI_API_KEY` or `OPENAI_API_KEY`
- `GMAIL_USER` and `GMAIL_PASSWORD` (App Password)
- `SEARCH_ROLES`, `SEARCH_LOCATIONS`

4. **Add Initial Resumes**:
- Place `.docx` or `.pdf` resumes in `data/resumes/original/`.
- Important: The Optimizer module strictly requires `.docx` formats to rewrite bullets while preserving styles.

## Running Locally

To trigger a manual run right now without waiting for the schedule:
```bash
PYTHONPATH=. python -m src.main --run-now
```

To start the scheduler (runs daily at 7 AM):
```bash
PYTHONPATH=. python -m src.main
```

## Docker (Future)
The modular codebase is highly container-friendly. A `Dockerfile` can be added to package this structure for a cloud run environment.
