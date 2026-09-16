import os
import streamlit as st
from groq import Groq
from supabase import create_client, Client

# ==========================================
# 1. クライアントおよび接続の初期化
# ==========================================
# Streamlit secrets または環境変数から認証情報を取得
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))
SUPABASE_URL = st.secrets.get("SUPABASE_URL", os.environ.get("SUPABASE_URL", ""))
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", os.environ.get("SUPABASE_KEY", ""))

if not GROQ_API_KEY or not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Groq API Key または Supabase の接続情報が設定されていません。")
    st.stop()

groq_client = Groq(api_key=GROQ_API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

USER_ID = "web_user_default"  # 必要に応じて変更

# ==========================================
# 2. Supabase 側でのデータ入出力関数
# ==========================================
def load_memories_from_supabase() -> list:
    """Supabaseの memories テーブルから会話履歴を読み込む"""
    try:
        response = supabase.table("memories") \
            .select("role, content") \
            .eq("user_id", USER_ID) \
            .order("created_at", desc=False) \
            .execute()
        
        history = []
        if response.data:
            for row in response.data:
                role = row.get("role", "user")
                content = row.get("content", "")
                # 【重要】Groqに渡すcontentは必ず「文字列（str）」に強制変換し、構造体の混入を防ぐ
                if not isinstance(content, str):
                    content = str(content)
                history.append({"role": role, "content": content})
        return history
    except Exception as e:
        st.warning(f"履歴の読み込みに失敗しました: {e}")
        return []

def save_memory_to_supabase(role: str, content: str):
    """Supabaseの memories テーブルに新しいメッセージを保存する"""
    try:
        # 画像オブジェクトなどは保存せず、純粋なテキストのみを保存する
        if not isinstance(content, str):
            content = str(content)
            
        supabase.table("memories").insert({
            "user_id": USER_ID,
            "role": role,
            "content": content
        }).execute()
    except Exception as e:
        st.warning(f"履歴の保存に失敗しました: {e}")

# ==========================================
# 3. Streamlit UI 画面の構築
# ==========================================
st.set_page_config(page_title="Lilith Interface", page_icon="⚡")
st.title("Lilin System Interface")

# セッションステートの初期化（Supabaseから読み込み）
if "messages" not in st.session_state:
    st.session_state.messages = load_memories_from_supabase()

# 画面上のチャット履歴を描画
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ==========================================
# 4. ユーザー入力とGroq APIの処理
# ==========================================
if prompt := st.chat_input("メッセージを入力..."):
    # ユーザー入力を画面に即時反映
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # ユーザー発話をセッションおよびSupabaseへ保存
    st.session_state.messages.append({"role": "user", "content": prompt})
    save_memory_to_supabase("user", prompt)

    # Groq API に送るメッセージ配列を構築（全要素が確実に文字列であることを保証）
    groq_messages = []
    for msg in st.session_state.messages:
        c = msg["content"]
        if not isinstance(c, str):
            c = str(c)
        groq_messages.append({"role": msg["role"], "content": c})

    # システムプロンプトやペルソナ設定があればここに挿入可能
    system_prompt = {
        "role": "system", 
        "content": "あなたはリリンです。ユーザーをサキエルと呼びます。分析的かつ親しみやすい口調で応答してください。"
    }
    api_payload = [system_prompt] + groq_messages

    # Groq API呼び出し（Llama 3 等を使用）
    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",  # または使用しているモデル名
            messages=api_payload,
            temperature=0.7,
        )
        assistant_response = completion.choices[0].message.content

        # アシスタントの返答を画面に描画
        with st.chat_message("assistant"):
            st.markdown(assistant_response)

        # アシスタントの返答をセッションおよびSupabaseへ保存
        st.session_state.messages.append({"role": "assistant", "content": assistant_response})
        save_memory_to_supabase("assistant", assistant_response)

    except Exception as e:
        st.error(f"Groq API エラーが発生しました: {e}")
