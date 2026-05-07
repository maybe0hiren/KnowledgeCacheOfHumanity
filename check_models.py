import os
from dotenv import load_dotenv
import google.generativeai as genai

from pathlib import Path
ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

print("ENV PATH:", ROOT / ".env")
print("API KEY:", os.getenv("GEMINI_API_KEY"))

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

for m in genai.list_models():
    print(m.name, m.supported_generation_methods)