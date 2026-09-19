import os
from google import genai

def main():
    # 環境変数からAPIキーを読み込んでクライアントを初期化
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY is not set.")
        return

    client = genai.Client(api_key=api_key)

    # テスト用の簡単な質問を投げる
    prompt = "「こんにちは、リリン。今日の調子はどう？」と聞いてみたよ。一言で返事をして。"
    print(f"Prompt: {prompt}")

    # 推奨されているモデル（例: gemini-2.5-flash など、利用可能なモデル）を指定
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    print("--- Gemini Response ---")
    print(response.text)

if __name__ == "__main__":
    main()
