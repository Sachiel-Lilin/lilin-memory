import os
import json
from google import genai

STATE_FILE = "state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"history": []}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY is not set.")
        return

    client = genai.Client(api_key=api_key)
    target_model = "gemini-3.6-flash"

    # 状態のロード
    state = load_state()
    history = state.get("history", [])

    # 今回の入力データ（自動実行時のプロンプトやメッセージ）
    user_message = "こんにちは、リリン。今日の調子はどう？"
    print(f"User: {user_message}")

    # 履歴にユーザーの発言を追加
    history.append({"role": "user", "parts": [{"text": user_message}]})

    # トークン肥大化を防ぐため、直近の最大ターン数（例: 直近10件）のみを送信対象に制限
    max_turns = 10
    send_history = history[-max_turns:]

    try:
        # チャットセッションを構築してメッセージを送信
        # ※直近の履歴から今回のメッセージを除いたものを初期履歴として渡す
        chat_history = send_history[:-1] if len(send_history) > 1 else []
        chat = client.chats.create(model=target_model, history=chat_history)
        
        response = chat.send_message(user_message)
        bot_reply = response.text
        print(f"Lilin: {bot_reply}")

        # 履歴にボットの応答を追加
        history.append({"role": "model", "parts": [{"text": bot_reply}]})

        # 状態を更新して state.json に保存
        state["history"] = history
        save_state(state)
        print("State updated and saved to state.json.")

    except Exception as e:
        print(f"API Error: {e}")

if __name__ == "__main__":
    main()
