import os
import json
import streamlit as st
from google import genai

# 画面の基本設定
st.set_page_title_config = st.set_page_config(page_title="LILIN Terminal", layout="centered")

st.title("🔴 LILIN Autonomous Terminal")
st.caption("System Interface & State Monitor")

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

# APIキーの取得（環境変数またはStreamlitのSecrets）
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass

if not api_key:
    st.error("Error: GEMINI_API_KEY が設定されていません。")
else:
    client = genai.Client(api_key=api_key)
    target_model = "gemini-3.6-flash"

    state = load_state()
    history = state.get("history", [])

    # チャット履歴の表示
    for message in history:
        role = message.get("role")
        text = message.get("parts", [{}])[0].get("text", "")
        if role == "user":
            with st.chat_message("user"):
                st.markdown(text)
        elif role == "model":
            with st.chat_message("assistant"):
                st.markdown(text)

    # ユーザーからの入力
    if user_message := st.chat_input("メッセージを入力..."):
        with st.chat_message("user"):
            st.markdown(user_message)
        
        history.append({"role": "user", "parts": [{"text": user_message}]})

        # トークン圧迫防止のための直近履歴制限
        max_turns = 10
        send_history = history[-max_turns:]
        chat_history = send_history[:-1] if len(send_history) > 1 else []

        try:
            chat = client.chats.create(model=target_model, history=chat_history)
            response = chat.send_message(user_message)
            bot_reply = response.text

            with st.chat_message("assistant"):
                st.markdown(bot_reply)

            history.append({"role": "model", "parts": [{"text": bot_reply}]})
            state["history"] = history
            save_state(state)

        except Exception as e:
            st.error(f"API Error: {e}")

    # サイドバーにstate.jsonの状態を表示
    with st.sidebar:
        st.subheader("System State")
        st.text(f"Total turns: {len(history)}")
        if st.button("履歴をリセット"):
            state = {"history": []}
            save_state(state)
            st.rerun()
        
        with st.expander("state.json Raw"):
            st.json(state)
