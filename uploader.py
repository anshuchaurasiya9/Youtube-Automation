"""
uploader.py
-----------
Official YouTube Data API v3 publisher with resumable chunked upload,
token refresh management, and tenacity retry on network interruptions.
"""

import os
import time
import logging
from typing import List, Optional, Dict, Any
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger("YouTubeAutomation")

SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

def authenticate_youtube(
    token_file: str = 'token.json',
    client_secrets_file: str = 'client_secrets.json'
):
    """
    Loads saved OAuth2 credentials from token_file.
    Refreshes automatically if expired.
    """
    creds = None

    if os.path.exists(token_file):
        try:
            creds = Credentials.from_authorized_user_file(token_file, SCOPES)
        except Exception as e:
            logger.warning(f"[YouTube Auth] Could not load {token_file}: {e}")

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("[YouTube Auth] Refreshing expired OAuth credentials...")
            creds.refresh(Request())
        else:
            if not os.path.exists(client_secrets_file):
                raise FileNotFoundError(
                    f"Neither valid {token_file} nor {client_secrets_file} was found."
                )
            logger.info("[YouTube Auth] Initiating OAuth local authorization flow...")
            flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_file, 'w', encoding='utf-8') as token:
            token.write(creds.to_json())
        logger.info(f"[YouTube Auth] Stored updated credentials in {token_file}")

    return build('youtube', 'v3', credentials=creds)

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    reraise=True
)
def upload_video_resumable(
    youtube,
    file_path: str,
    title: str,
    description: str,
    tags: Optional[List[str]] = None,
    category_id: str = '22',
    privacy_status: str = 'private'
) -> Dict[str, Any]:
    """
    Executes a chunked, resumable YouTube upload with automatic retry
    on network drops or 5xx server errors.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Video file does not exist: {file_path}")

    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    logger.info(f"[YouTube Upload] Uploading '{file_path}' ({file_size_mb:.2f} MB)...")
    logger.info(f"[YouTube Upload] Title: {title}")
    logger.info(f"[YouTube Upload] Privacy: {privacy_status}")

    body = {
        'snippet': {
            'title': title[:100],  # YouTube title length limit
            'description': description[:5000],
            'tags': tags or [],
            'categoryId': category_id
        },
        'status': {
            'privacyStatus': privacy_status,
            'selfDeclaredMadeForKids': False
        }
    }

    # 5MB chunks for reliable resumable transfer
    media = MediaFileUpload(file_path, chunksize=1024 * 1024 * 5, resumable=True)

    request = youtube.videos().insert(
        part=','.join(body.keys()),
        body=body,
        media_body=media
    )

    response = None
    last_reported_progress = -1

    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                if progress != last_reported_progress and progress % 10 == 0:
                    logger.info(f"[YouTube Upload] Progress: {progress}%")
                    last_reported_progress = progress
        except HttpError as e:
            if e.resp.status in [500, 502, 503, 504]:
                logger.warning(f"[YouTube Upload] Transient server error {e.resp.status}. Retrying...")
                time.sleep(5)
                continue
            else:
                logger.error(f"[YouTube Upload] Fatal HTTP Error: {e}")
                raise e

    video_id = response.get('id', 'UNKNOWN')
    logger.info(f"[YouTube Upload] SUCCESS! Video ID: {video_id} (https://youtu.be/{video_id})")
    return response

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    yt = authenticate_youtube()
    print("YouTube Client Authenticated:", yt is not None)
