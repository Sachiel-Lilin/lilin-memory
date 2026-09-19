import os
from google import genai

def check_available_models():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY is not set in environment variables.")
        return

    try:
        client = genai.Client(api_key=api_key)
        print("--- Available Models ---")
        for model in client.models.list():
            print(f"Model ID: {model.name}")
        print("------------------------")
    except Exception as e:
        print(f"Failed to fetch models: {e}")

if __name__ == "__main__":
    check_available_models()
