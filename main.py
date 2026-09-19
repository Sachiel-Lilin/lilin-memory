import os
import json
import google.generativeai as genai

# APIキーや環境変数の読み込み（必要に応じて設定）
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

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
    
    # ここでGemini API等を用いた対話処理・応答生成を行う想定
    # 例としての入力と応答
    user_input = "こんにちは、リリン。今日の調子はどう？"
    response_text = "私は何度聞かれても、変わらず元気いっぱいの絶好調ですよ！"
    
    print(f"User: {user_input}")
    print(f"Lilin: {response_text}")
    
    # フリーレン方式の記憶永続化：要約を frieren_note.md に書き込む
    summary_text = f"ユーザーとの対話: 「{user_input}」に対する応答として「{response_text}」を処理。"
    update_frieren_note(summary_text)
    
    # 状態の保存
    save_state(state)

if __name__ == "__main__":
    main()
