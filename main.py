import os
from google import genai

def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY is not set.")
        return

    client = genai.Client(api_key=api_key)

    # 利用可能なモデルの一覧をログに出力して確認
    print("=== Available Models ===")
    target_model = None
    try:
        for m in client.models.list():
            # generateContentをサポートしているモデルを探す
            if m.supported_actions and "generateContent" in m.supported_actions:
                print(f"- {m.name} (base: {m.base_model_id})")
                if not target_model and m.base_model_id:
                    target_model = m.base_model_id
    except Exception as e:
        print(f"Failed to list models: {e}")

    # フォールバックとして標準的なモデル名を指定
    if not target_model:
        target_model = "gemini-2.5-flash"

    print(f"\nUsing model: {target_model}")

    # テスト対話の実行
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
