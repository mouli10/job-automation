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
    Connects to Google Drive, locates the 'Original' folder inside config folder scope, 
    downloads all .docx and .pdf files locally, and ingests them into the SQLite backend.
    """
    service = get_drive_service()
    if not service or not GDRIVE_FOLDER_ID:
        logger.warning("No Drive credentials active. Syncing original resumes from local directory only.")
        return
        
    logger.info("🔄 Initiating Google Drive Origin Sync...")
    try:
        from googleapiclient.http import MediaIoBaseDownload
        
        # 1. Find the 'Original' Folder inside the User's main automation folder
        query = f"'{GDRIVE_FOLDER_ID}' in parents and name='Original' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        folders = results.get('files', [])
        
        if not folders:
            logger.warning(f"Could not find a folder named 'Original' inside Drive ID '{GDRIVE_FOLDER_ID}'. Sync aborted.")
            return
            
        original_folder_id = list(folders)[0]['id']
        
        # 2. Get all Document files inside 'Original'
        doc_query = f"'{original_folder_id}' in parents and trashed=false"
        files_results = service.files().list(q=doc_query, fields="files(id, name, mimeType)").execute()
        files = files_results.get('files', [])
        
        if not files:
            logger.info("No files found strictly in Drive 'Original' folder.")
            return
            
        valid_extensions = [".docx", ".pdf"]
        synced_count = 0
        
        for file in files:
            file_name = file.get("name")
            file_id = file.get("id")
            ext = Path(file_name).suffix.lower()
            
            if ext not in valid_extensions:
                continue
                
            from src.config import DATA_DIR
            temp_cache = DATA_DIR / "tmp_sync"
            temp_cache.mkdir(exist_ok=True)
            local_dest = temp_cache / file_name
            
            # Download file byte stream
            request = service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                
            fh.seek(0)
            
            # Save strictly to local Origin
            with open(local_dest, "wb") as f:
                f.write(fh.read())
                
            # Automatically feed into ResumeManager DB
            resume_manager.ingest_resume(str(local_dest))
            
            # Clean up temp
            local_dest.unlink(missing_ok=True)
            
            synced_count += 1
            
        logger.info(f"✅ Successfully synced {synced_count} baseline resumes from Google Drive!")
        
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
