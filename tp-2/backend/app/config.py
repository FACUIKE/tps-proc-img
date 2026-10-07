"""
Application settings. DO NOT MODIFY.

The acceptance tests redirect the storage folder with the TP_STORAGE_DIR
environment variable, so always read paths and limits from here.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
FRONTEND_DIR = BASE_DIR.parent / "frontend"

# Folder where the scans (result, original photo and metadata) are stored.
STORAGE_DIR = Path(os.environ.get("TP_STORAGE_DIR", BASE_DIR / "storage"))

# Public URL under which STORAGE_DIR is served.
MEDIA_URL = "/media"

# Accepted photo formats (detected by content, not by extension).
ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP", "BMP"}

# Maximum size of an uploaded photo.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
