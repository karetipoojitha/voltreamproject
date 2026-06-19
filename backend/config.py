import os
import json
import tempfile
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv(os.path.join(BASE_DIR, ".env"))

os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
VERTEX_AI_MODEL = os.getenv("VERTEX_AI_MODEL", "gemini-2.5-flash")

# ── Credentials resolution ──────────────────────────────────────────────────
# Priority 1: GOOGLE_APPLICATION_CREDENTIALS_JSON (base64 or raw JSON string)
#             — used in Cloud Run / CI where you can't mount a file
# Priority 2: GOOGLE_APPLICATION_CREDENTIALS pointing to a file
#             — used in local development
# ────────────────────────────────────────────────────────────────────────────

creds_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")

if creds_json:
    # Write the JSON content to a temp file so google-auth can read it
    try:
        # Handle both raw JSON string and base64-encoded JSON
        try:
            import base64
            decoded = base64.b64decode(creds_json).decode("utf-8")
            json.loads(decoded)          # validate it's real JSON
            creds_json = decoded
        except Exception:
            pass                          # already raw JSON, use as-is

        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        )
        tmp.write(creds_json)
        tmp.flush()
        tmp.close()
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = tmp.name
    except Exception as e:
        print(f"[config] Warning: could not write credentials JSON to temp file: {e}")

else:
    # Local dev: resolve relative path to absolute
    creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if creds and not os.path.isabs(creds):
        for candidate in [
            os.path.abspath(os.path.join(BASE_DIR, creds)),
            os.path.abspath(os.path.join(os.path.dirname(BASE_DIR), creds)),
            os.path.abspath(os.path.join(BASE_DIR, os.path.basename(creds))),
        ]:
            if os.path.exists(candidate):
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = candidate
                break
