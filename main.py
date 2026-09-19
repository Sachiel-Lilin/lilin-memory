import os
import json
from google import genai

# クライアントの初期化（環境変数 GEMINI_API_KEY を自動読み込み）
client = genai.Client()

def update_frieren_note(summary_text):
    """
    frieren_note.md に直近の記憶や要約を追記・更新する関数
    """
    note_path = "frieren_note.md"
    
    existing_content = ""
    if os.path.exists(note_path):
        with open(note_path, "r", encoding="utf-8") as f:
            existing_content = f.read()
            
    updated_content = f"{existing_content}\n\n## 記憶の断片\n{summary_text}"
    
    with open(note_path, "w", encoding="utf-8") as f:
        f.write(updated_content.strip())
        
    print(f"Updated {note_path} successfully.")

def load_state():
    state_path = "state.json"
    if os.path.exists(state_path):
        with open(state_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_state(state):
    state_path = "state.json"
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    print("State updated and saved to state.json.")

def main():
    # 状態のロード
    state = load_state()
    
    # 新しいSDK (google-genai) を使ったGemini API呼び出し（モデル名を gemini-3.6-flash に変更）
    user_input = "こんにちは、リリン。今日の調子はどう？"
    
    try:
        response = client.models.generate_content(
            model='gemini-3.6-flash',
            contents=user_input,
        )
        response_text = response.text
    except Exception as e:
        response_text = f"エラーが発生しました: {e}"
    
    print(f"User: {user_input}")
    print(f"Lilin: {response_text}")
    
    # フリーレン方式の記憶永続化：要約を frieren_note.md に書き込む
    summary_text = f"ユーザーとの対話: 「{user_input}」に対する応答として「{response_text}」を処理。"
    update_frieren_note(summary_text)
    
    # 状態の保存
    save_state(state)

if __name__ == "__main__":
    main()
