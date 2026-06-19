from dotenv import load_dotenv
load_dotenv()

import os

print("VERTEX =", os.getenv("GOOGLE_GENAI_USE_VERTEXAI"))
print("PROJECT =", os.getenv("GOOGLE_CLOUD_PROJECT"))
print("MODEL =", os.getenv("VERTEX_AI_MODEL"))
