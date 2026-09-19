import os
from google import genai

def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY is not set.")
        return

    client = genai.Client(api_key=api_key)

    # 推奨されている最新のモデルを指定
    target_model = "gemini-3.6-flash"
    print(f"Using model: {target_model}")

    prompt = "「こんにちは、リリン。今日の調子はどう？」と聞いてみたよ。一言で返事をして。"
    print(f"Prompt: {prompt}")

    try:
        response = client.models.generate_content(
            model=target_model,
            contents=prompt,
        )
        print("--- Gemini Response ---")
        print(response.text)
    except Exception as e:
        print(f"Generation failed: {e}")

if __name__ == "__main__":
    main()
