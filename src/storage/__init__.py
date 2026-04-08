"""
Google Drive storage module.
Currently uses local file paths as fallback (no credentials.json yet).
When credentials.json is placed in the project root and GDRIVE_FOLDER_ID is set,
this module will switch to real Drive uploads and downloads.
"""
import logging
import shutil
import io
from pathlib import Path
from src.config import GDRIVE_CREDENTIALS_PATH, GDRIVE_FOLDER_ID, OPTIMIZED_RESUMES_DIR, ORIGINAL_RESUMES_DIR

logger = logging.getLogger(__name__)

# ── Cloud Teleport Constants ────────────────────────────────────────────────
DB_FILE_NAME = "jobs.db"
CONFIG_FILE_NAME = "config.json"
DATABASE_FOLDER_NAME = "database"
CONFIG_FOLDER_NAME = "config"
SCREENSHOTS_FOLDER_NAME = "debug_screenshots"

def get_drive_service():
    """
    Authenticates and returns the Google Drive v3 service resource.
    Works in two modes:
      1. Local (Mac): reads credentials.json + token.json from disk
      2. Cloud (Streamlit Cloud): reads GDRIVE_CREDENTIALS_JSON + GDRIVE_TOKEN_JSON from env vars
    """
    import os, tempfile

    creds_path = GDRIVE_CREDENTIALS_PATH
    token_path = str(Path(GDRIVE_CREDENTIALS_PATH).parent / "token.json")

    # ── CLOUD MODE: Write env var secrets to temp files ──────────────────────
    creds_json_env = os.getenv("GDRIVE_CREDENTIALS_JSON", "").strip()
    token_json_env = os.getenv("GDRIVE_TOKEN_JSON", "").strip()

    if not Path(creds_path).exists() and creds_json_env:
        try:
            _tmp_dir = tempfile.mkdtemp()
            creds_path = os.path.join(_tmp_dir, "credentials.json")
            token_path = os.path.join(_tmp_dir, "token.json")
            with open(creds_path, "w") as f:
                f.write(creds_json_env)
            if token_json_env:
                with open(token_path, "w") as f:
                    f.write(token_json_env)
            logger.info("🌐 Cloud Mode: Loaded Drive credentials from environment secrets.")
        except Exception as e:
            logger.error(f"Failed to write Drive credentials from env vars: {e}")
            return None

    if not creds_path or not Path(creds_path).exists():
        return None

    try:
        from googleapiclient.discovery import build
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request

        SCOPES = ["https://www.googleapis.com/auth/drive"]
        creds = None

        if Path(token_path).exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

        if not creds or not creds.valid or not creds.has_scopes(SCOPES):
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                with open(token_path, "w") as token:
                    token.write(creds.to_json())
            else:
                logger.error("Drive token is invalid and cannot be refreshed interactively in cloud mode.")
                return None

        return build("drive", "v3", credentials=creds)
    except Exception as e:
        logger.error(f"Google Drive Auth Failed: {e}")
        return None

def sync_original_resumes(resume_manager):
    """
    Two-phase resume sync:
    Phase 1 (Always): Scan ORIGINAL_RESUMES_DIR and re-register any local files 
                      with the correct current-machine path. This fixes stale 
                      paths stored in cloud DB from a different machine.
    Phase 2 (If Drive connected): Download any new/updated files from Google Drive.
    """

    # ── PHASE 1: Re-register existing local files with correct path ──────────
    valid_extensions = [".pdf", ".docx"]
    local_files = [
        f for f in ORIGINAL_RESUMES_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in valid_extensions
    ]
    if local_files:
        logger.info(f"📁 Re-registering {len(local_files)} local resume(s) with current machine path...")
        for local_file in local_files:
            try:
                resume_manager.ingest_resume(str(local_file))
                logger.info(f"  ✅ Registered: {local_file.name} → {local_file}")
            except Exception as e:
                logger.warning(f"  ⚠️ Could not register {local_file.name}: {e}")

    # ── PHASE 2: Sync from Google Drive ────────────────────────────────────
    service = get_drive_service()
    if not service or not GDRIVE_FOLDER_ID:
        logger.warning("No Drive credentials active. Using local files only.")
        return

    logger.info("🔄 Initiating Google Drive Origin Sync...")
    try:
        from googleapiclient.http import MediaIoBaseDownload

        # Find the 'Original' folder inside the user's main Drive folder
        query = f"'{GDRIVE_FOLDER_ID}' in parents and name='Original' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        folders = results.get('files', [])

        if not folders:
            logger.warning(f"No 'Original' folder found in Drive ID '{GDRIVE_FOLDER_ID}'. Skipping Drive sync.")
            return

        original_folder_id = folders[0]['id']

        doc_query = f"'{original_folder_id}' in parents and trashed=false"
        files_results = service.files().list(q=doc_query, fields="files(id, name, mimeType)").execute()
        files = files_results.get('files', [])

        if not files:
            logger.info("No files found in Drive 'Original' folder.")
            return

        synced_count = 0
        for file in files:
            file_name = file.get("name")
            file_id = file.get("id")
            ext = Path(file_name).suffix.lower()

            if ext not in valid_extensions:
                continue

            # Save directly to ORIGINAL_RESUMES_DIR (persistent, correct path stored in DB)
            local_dest = ORIGINAL_RESUMES_DIR / file_name

            request = service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
            fh.seek(0)

            with open(local_dest, "wb") as f:
                f.write(fh.read())

            resume_manager.ingest_resume(str(local_dest))
            synced_count += 1

        logger.info(f"✅ Drive Sync complete. {synced_count} resume(s) downloaded to {ORIGINAL_RESUMES_DIR}")

    except Exception as e:
        logger.error(f"Google Drive Sync Failed: {e}", exc_info=False)



def upload_resume(filepath: str, filename: str) -> str:
    """
    Uploads a resume file to Google Drive and returns a shareable link.
    Falls back to a local file path if credentials are not configured.
    """
    service = get_drive_service()
    if service and GDRIVE_FOLDER_ID:
        try:
            from googleapiclient.http import MediaFileUpload
            file_metadata = {
                "name": filename,
                "parents": [GDRIVE_FOLDER_ID]
            }
            media = MediaFileUpload(filepath, mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            uploaded = service.files().create(body=file_metadata, media_body=media, fields="id").execute()
            file_id = uploaded.get("id")

            # Make it publicly viewable via link
            service.permissions().create(
                fileId=file_id,
                body={"type": "anyone", "role": "reader"}
            ).execute()

            link = f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"
            logger.info(f"Uploaded to Google Drive: {link}")
            return link
        except Exception as e:
            logger.warning(f"Google Drive upload failed, using local fallback: {e}")

    # --- LOCAL FALLBACK ---
    logger.info(f"Document retained locally (Drive skipped): {filepath}")
    return str(filepath)

# ── Cloud Sync Logic ────────────────────────────────────────────────────────

def _get_or_create_folder(service, parent_id, folder_name):
    query = f"'{parent_id}' in parents and name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    folders = results.get('files', [])
    if folders:
        return folders[0]['id']
    
    file_metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_id]
    }
    folder = service.files().create(body=file_metadata, fields='id').execute()
    return folder.get('id')

def _download_file(service, folder_id, filename, local_path):
    query = f"'{folder_id}' in parents and name='{filename}' and trashed=false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get('files', [])
    if not files:
        return False
    
    file_id = files[0]['id']
    from googleapiclient.http import MediaIoBaseDownload
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    
    fh.seek(0)
    with open(local_path, "wb") as f:
        f.write(fh.read())
    return True

def _upload_file(service, folder_id, filename, local_path):
    # Delete existing version first to avoid duplicates
    query = f"'{folder_id}' in parents and name='{filename}' and trashed=false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    for f in results.get('files', []):
        service.files().delete(fileId=f['id']).execute()
    
    from googleapiclient.http import MediaFileUpload
    file_metadata = {'name': filename, 'parents': [folder_id]}
    media = MediaFileUpload(local_path, resumable=True)
    service.files().create(body=file_metadata, media_body=media, fields='id').execute()

def sync_db_from_drive():
    service = get_drive_service()
    if not service or not GDRIVE_FOLDER_ID: return False
    
    folder_id = _get_or_create_folder(service, GDRIVE_FOLDER_ID, DATABASE_FOLDER_NAME)
    from src.config import DATA_DIR
    local_path = DATA_DIR / DB_FILE_NAME
    if _download_file(service, folder_id, DB_FILE_NAME, local_path):
        logger.info(f"💾 Database synced from Cloud (Google Drive)")
        return True
    return False

def sync_db_to_drive():
    service = get_drive_service()
    if not service or not GDRIVE_FOLDER_ID: return
    
    folder_id = _get_or_create_folder(service, GDRIVE_FOLDER_ID, DATABASE_FOLDER_NAME)
    from src.config import DATA_DIR
    local_path = DATA_DIR / DB_FILE_NAME
    if local_path.exists():
        _upload_file(service, folder_id, DB_FILE_NAME, str(local_path))
        logger.info(f"💾 Database backed up to Cloud (Google Drive)")

def sync_config_from_drive():
    service = get_drive_service()
    if not service or not GDRIVE_FOLDER_ID: return False
    
    folder_id = _get_or_create_folder(service, GDRIVE_FOLDER_ID, CONFIG_FOLDER_NAME)
    from src.config import DATA_DIR
    local_path = DATA_DIR / CONFIG_FILE_NAME
    if _download_file(service, folder_id, CONFIG_FILE_NAME, local_path):
        logger.info(f"⚙️ Configuration synced from Cloud (Google Drive)")
        return True
    return False

def sync_config_to_drive():
    service = get_drive_service()
    if not service or not GDRIVE_FOLDER_ID: return
    
    folder_id = _get_or_create_folder(service, GDRIVE_FOLDER_ID, CONFIG_FOLDER_NAME)
    from src.config import DATA_DIR
    local_path = DATA_DIR / CONFIG_FILE_NAME
    if local_path.exists():
        _upload_file(service, folder_id, CONFIG_FILE_NAME, str(local_path))
        logger.info(f"⚙️ Configuration backed up to Cloud (Google Drive)")

def cleanup_debug_screenshots():
    """Wipes the debug screenshots folder on Google Drive entirely."""
    service = get_drive_service()
    if not service or not GDRIVE_FOLDER_ID: return
    
    try:
        query = f"'{GDRIVE_FOLDER_ID}' in parents and name='{SCREENSHOTS_FOLDER_NAME}' and trashed=false"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        for f in results.get('files', []):
            service.files().delete(fileId=f['id']).execute()
            logger.info(f"🧹 Cleaned up old evidence: {SCREENSHOTS_FOLDER_NAME}")
    except Exception as e:
        logger.debug(f"Cloud cleanup failed (folder might not exist yet): {e}")

def sync_screenshots_to_drive():
    """Uploads all fresh .png screenshots captured during this run to Google Drive."""
    service = get_drive_service()
    if not service or not GDRIVE_FOLDER_ID: return
    
    from src.config import DATA_DIR
    screenshot_dir = DATA_DIR / "screenshots"
    if not screenshot_dir.exists(): return
    
    screenshot_files = list(screenshot_dir.glob("*.png"))
    if not screenshot_files: return
    
    logger.info(f"📸 Syncing {len(screenshot_files)} 'Evidence Photos' to Google Drive...")
    try:
        folder_id = _get_or_create_folder(service, GDRIVE_FOLDER_ID, SCREENSHOTS_FOLDER_NAME)
        for path in screenshot_files:
            from googleapiclient.http import MediaFileUpload
            file_metadata = {'name': path.name, 'parents': [folder_id]}
            media = MediaFileUpload(str(path), mimetype='image/png')
            service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            
        logger.info(f"✅ 'Cloud Vision' synced successfully to {SCREENSHOTS_FOLDER_NAME} folder!")
    except Exception as e:
        logger.error(f"❌ Failed to sync cloud vision: {e}")



# ══════════════════════════════════════════════════════════════════════════════
# ── Supabase Storage — Resume Management ─────────────────────────────────────
# Resumes are uploaded via the Admin Portal and stored in Supabase Storage.
# Google Drive is NOT used for resumes. Drive is only for cover letters and
# optimized resumes.
# ══════════════════════════════════════════════════════════════════════════════

RESUME_BUCKET = "resumes"


def _storage_headers() -> dict:
    """Returns auth headers for Supabase Storage REST API calls."""
    import os
    key = os.getenv("SUPABASE_KEY", "")
    return {
        "Authorization": f"Bearer {key}",
        "apikey": key,
    }


def ensure_resume_bucket() -> bool:
    """Creates the 'resumes' bucket in Supabase Storage if it doesn't exist."""
    import requests, os
    url = os.getenv("SUPABASE_URL", "")
    if not url:
        logger.warning("SUPABASE_URL not set — cannot ensure bucket.")
        return False
    try:
        r = requests.post(
            f"{url}/storage/v1/bucket",
            headers={**_storage_headers(), "Content-Type": "application/json"},
            json={"id": RESUME_BUCKET, "name": RESUME_BUCKET, "public": False},
            timeout=10,
        )
        if r.status_code in (200, 201):
            logger.info(f"✅ Supabase Storage bucket '{RESUME_BUCKET}' created.")
        elif r.status_code == 409:
            logger.debug(f"Bucket '{RESUME_BUCKET}' already exists — OK.")
        else:
            logger.warning(f"Bucket creation response: {r.status_code} — {r.text}")
        return True
    except Exception as e:
        logger.error(f"Failed to ensure resume bucket: {e}")
        return False


def upload_resume_to_storage(file_bytes: bytes, filename: str) -> str:
    """
    Uploads resume file bytes to Supabase Storage.
    Returns a supabase-storage:// URI that the pipeline uses to download later.
    """
    import requests, os
    url = os.getenv("SUPABASE_URL", "")
    if not url:
        raise RuntimeError("SUPABASE_URL not configured.")

    ensure_resume_bucket()

    r = requests.post(
        f"{url}/storage/v1/object/{RESUME_BUCKET}/{filename}",
        headers={
            **_storage_headers(),
            "Content-Type": "application/octet-stream",
            "x-upsert": "true",
        },
        data=file_bytes,
        timeout=60,
    )
    if r.status_code in (200, 201):
        storage_path = f"supabase-storage://{RESUME_BUCKET}/{filename}"
        logger.info(f"☁️ Resume uploaded to Supabase Storage: {filename}")
        return storage_path
    raise RuntimeError(f"Upload failed ({r.status_code}): {r.text}")


def download_resume_from_storage(filename: str) -> bytes:
    """Downloads a resume file from Supabase Storage. Returns raw bytes."""
    import requests, os
    url = os.getenv("SUPABASE_URL", "")
    if not url:
        raise RuntimeError("SUPABASE_URL not configured.")

    r = requests.get(
        f"{url}/storage/v1/object/{RESUME_BUCKET}/{filename}",
        headers=_storage_headers(),
        timeout=30,
    )
    if r.status_code == 200:
        return r.content
    raise RuntimeError(f"Download failed for '{filename}' ({r.status_code}): {r.text}")


def list_resumes_in_storage() -> list:
    """Lists all resume filenames in the Supabase Storage bucket."""
    import requests, os
    url = os.getenv("SUPABASE_URL", "")
    if not url:
        return []
    try:
        r = requests.post(
            f"{url}/storage/v1/object/list/{RESUME_BUCKET}",
            headers={**_storage_headers(), "Content-Type": "application/json"},
            json={"prefix": "", "limit": 100},
            timeout=10,
        )
        if r.status_code == 200:
            return [f["name"] for f in r.json() if f.get("name")]
        return []
    except Exception as e:
        logger.error(f"Failed to list storage resumes: {e}")
        return []


def delete_resume_from_storage(filename: str) -> bool:
    """Deletes a resume file from Supabase Storage. Returns True on success."""
    import requests, os
    url = os.getenv("SUPABASE_URL", "")
    if not url:
        return False
    try:
        r = requests.delete(
            f"{url}/storage/v1/object/{RESUME_BUCKET}/{filename}",
            headers=_storage_headers(),
            timeout=10,
        )
        return r.status_code in (200, 204)
    except Exception as e:
        logger.error(f"Failed to delete resume from storage: {e}")
        return False

