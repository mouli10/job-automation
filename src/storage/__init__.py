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

def get_drive_service():
    """Authenticates and returns the Google Drive v3 service resource."""
    if not GDRIVE_CREDENTIALS_PATH or not Path(GDRIVE_CREDENTIALS_PATH).exists():
        return None
        
    try:
        from googleapiclient.discovery import build
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        import os

        # Full drive scope required to read manually dropped files in Original folder
        SCOPES = ["https://www.googleapis.com/auth/drive"]
        token_path = Path(GDRIVE_CREDENTIALS_PATH).parent / "token.json"
        creds = None

        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

        if not creds or not creds.valid or not creds.has_scopes(SCOPES):
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(GDRIVE_CREDENTIALS_PATH, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(token_path, "w") as token:
                token.write(creds.to_json())

        return build("drive", "v3", credentials=creds)
    except Exception as e:
        logger.error(f"Google Drive Auth Failed. Is credentials.json valid? Error: {e}")
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
