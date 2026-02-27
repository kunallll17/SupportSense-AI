"""Quick script to list all available Gemini models that support embedContent."""
import google.generativeai as genai
from dotenv import load_dotenv
import os

load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

print("Models supporting embedContent:")
for m in genai.list_models():
    if "embedContent" in m.supported_generation_methods:
        print(f"  {m.name}")

print("\nAll available models:")
for m in genai.list_models():
    print(f"  {m.name} — {m.supported_generation_methods}")