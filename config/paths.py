import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

DB_PATH = Path(
    os.environ.get("LIBRARY_ASSISTANT_DB_PATH", REPO_ROOT / "library_assistant.db")
).expanduser()

STUDENT_PHOTOS_DIR = Path(
    os.environ.get("LIBRARY_ASSISTANT_PHOTOS_DIR", REPO_ROOT / "student_photos")
).expanduser()

# Set LIBRARY_ASSISTANT_REMOTE_URL to enable cloud database sync (e.g. "https://jaychoudhary.pythonanywhere.com")
REMOTE_URL = os.environ.get("LIBRARY_ASSISTANT_REMOTE_URL", "")
# API Key for authenticating remote requests
API_KEY = os.environ.get("LIBRARY_ASSISTANT_API_KEY", "jay-library-secret-key-2026")

