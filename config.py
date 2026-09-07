import os
from dotenv import load_dotenv

load_dotenv()

LLM_PROVIDER = os.getenv(
    "LLM_PROVIDER",
    "groq"
).strip().lower()