import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR.parent

load_dotenv(BACKEND_DIR / ".env")
load_dotenv(BASE_DIR / ".env", override=True)

os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "true")

credentials = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
if credentials:
    credentials_path = Path(credentials)
    if not credentials_path.is_absolute():
        candidates = [
            BACKEND_DIR / credentials_path,
            BACKEND_DIR.parent / credentials_path,
            BASE_DIR / credentials_path,
        ]
        for candidate in candidates:
            if candidate.exists():
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(candidate.resolve())
                break

VERTEX_AI_MODEL = os.getenv("VERTEX_AI_MODEL", "gemini-2.5-flash-lite")
