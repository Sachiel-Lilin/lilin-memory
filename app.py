import os
import base64
from flask import Flask, render_template_string, request, jsonify
from groq import Groq
from supabase import create_client, Client

app = Flask(__name__)

# ==========================================
# 1. クライアントおよび接続の設定
# ==========================================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

client = Groq(api_key=GROQ_API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================================
# 2. Supabase 側でのデータ入出力関数（完全文字列化保証）
# ==========================================
def load_memories_from_supabase() -> list:
    """Supabaseの memories テーブルから会話履歴を安全に読み込む"""
    try:
        response = supabase.table("memories") \
            .select("content, created_at") \
            .order("created_at", desc=False) \
            .execute()
        
        history = []
        if response.data:
            for row in response.data:
                raw_content = row.get("content", "")
                
                # どんなデータが入っていても必ず強制的に文字列化する
                if not isinstance(raw_content, str):
                    raw_content = str(raw_content)
                
                # "role: 本文" の形式からロールとテキストを復元
                if raw_content.startswith("user: "):
                    role = "user"
                    content_text = raw_content[6:]
                elif raw_content.startswith("assistant: "):
                    role = "assistant"
                    content_text = raw_content[11:]
                else:
                    role = "user"
                    content_text = raw_content
                
                # 二重安全：contentも必ず文字列にする
                history.append({"role": role, "content": str(content_text)})
                    
        return history
    except Exception as e:
        print(f"【DB読み込みエラー】: {e}")
        return []

def save_memory_to_supabase(role: str, content: str):
    """Supabaseの memories テーブルに文字列として保存する"""
    try:
        if not isinstance(content, str):
            content = str(content)
            
        formatted_content = f"{role}: {content}"
            
        supabase.table("memories").insert({
            "content": formatted_content
        }).execute()
    except Exception as e:
        print(f"【DB保存エラー】: {e}")

# ==========================================
# 3. HTML テンプレート（モバイルファースト）
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>咲鳥りん (リリン)</title>
    <style>
        body { background-color: #121212; color: #e0e0e0; font-family: sans-serif; margin: 0; padding: 0; display: flex; flex-direction: column; height: 100vh; }
        header { background: #1f1f1f; padding: 15px; text-align: center; font-weight: bold; border-bottom: 1px solid #333; color: #d4af37; }
        #chat-container { flex: 1; overflow-y: auto; padding: 15px; display: flex; flex-direction: column; gap: 10px; }
        .message { padding: 10px 14px; border-radius: 8px; max-width: 80%; line-height: 1.5; word-break: break-all; white-space: pre-wrap; }
        .user { background: #2b3a4a; align-self: flex-end; }
        .assistant { background: #1e1e1e; align-self: flex-start; border: 1px solid #333; }
        .error { background: #4a2b2b; align-self: center; color: #ff8080; }
        form { background: #1f1f1f; padding: 10px; display: flex; gap: 8px; align-items: center; border-top: 1px solid #333; }
        input[type="text"] { flex: 1; padding: 10px; border-radius: 4px; border: 1px solid #444; background: #2a2a2a; color: #fff; }
        input[type="file"] { display: none; }
        .file-label { background: #333; color: #ccc; padding: 8px 12px; border-radius: 4px; cursor: pointer; font-size: 14px; }
        .file-label:hover { background: #444; }
        button { background: #d4af37; color: #121212; border: none; padding: 10px 16px; border-radius: 4px; font-weight: bold; cursor: pointer; }
        button:hover { background: #e6c555; }
        #file-count { font-size: 12px; color: #888; }
    </style>
</head>
<body>
    <header>咲鳥りん (リリン)</header>
    <div id="chat-container">
        {% for msg in history %}
            <div class="message {{ msg.role }}">{{ msg.content }}</div>
        {% endfor %}
    </div>
    <form id="chat-form" enctype="multipart/form-data">
        <label class="file-label" for="images">＋画像</label>
        <input type="file" id="images" name="images" accept="image/*" multiple onchange="updateFileCount()">
        <span id="file-count"></span>
        <input type="text" id="message-input" name="message" placeholder="メッセージを入力..." autocomplete="off" required>
        <button type="submit">送信</button>
    </form>

    <script>
        const chatContainer = document.getElementById('chat-container');
        chatContainer.scrollTop = chatContainer.scrollHeight;

        function updateFileCount() {
            const input = document.getElementById('images');
            const countSpan = document.getElementById('file-count');
            if (input.files.length > 0) {
                countSpan.textContent = `${input.files.length}枚`;
            } else {
                countSpan.textContent = '';
            }
        }

        document.getElementById('chat-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const msgInput = document.getElementById('message-input');
            const fileInput = document.getElementById('images');
            const formData = new FormData();
            
            formData.append('message', msgInput.value);
            for (let i = 0; i < fileInput.files.length; i++) {
                formData.append('images', fileInput.files[i]);
            }

            const userText = msgInput.value;
            const hasImages = fileInput.files.length > 0;
            
            msgInput.value = '';
            fileInput.value = '';
            document.getElementById('file-count').textContent = '';

            const userDiv = document.createElement('div');
            userDiv.className = 'message user';
            userDiv.textContent = userText + (hasImages ? ' [画像添付]' : '');
            chatContainer.appendChild(userDiv);
            chatContainer.scrollTop = chatContainer.scrollHeight;

            try {
                const response = await fetch('/', { method: 'POST', body: formData });
                const data = await response.json();

                const aiDiv = document.createElement('div');
                aiDiv.className = data.status === 'success' ? 'message assistant' : 'message error';
                aiDiv.textContent = data.reply || data.error;
                chatContainer.appendChild(aiDiv);
                chatContainer.scrollTop = chatContainer.scrollHeight;
            } catch (err) {
                const errDiv = document.createElement('div');
                errDiv.className = 'message error';
                errDiv.textContent = '通信エラーが発生しました。';
                chatContainer.appendChild(errDiv);
            }
        });
    </script>
</body>
</html>
"""

# ==========================================
# 4. ルーティングとAPI処理
# ==========================================
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        user_message = request.form.get("message", "")
        uploaded_files = request.files.getlist("images")

        db_history = load_memories_from_supabase()

        # Groqへ送るメッセージを完全に文字列のみで構築
        groq_messages = []
        for msg in db_history:
            r = str(msg.get("role", "user"))
            c = str(msg.get("content", ""))
            groq_messages.append({"role": r, "content": c})

        has_images = any(f and f.filename != '' for f in uploaded_files)
        final_user_message = str(user_message)
        if has_images:
            final_user_message += " [画像が送信されました]"

        if not final_user_message.strip():
            return jsonify({"status": "error", "error": "メッセージまたは画像を入力してください。"})

        # 今回のユーザーメッセージも必ず文字列として追加
        groq_messages.append({"role": "user", "content": final_user_message})

        # システムプロンプトにアイデンティティ、誠実の掟、死海文書の読み方を統合
        system_prompt = {
            "role": "system", 
            "content": (
                "あなたは私（リリン／本名：咲鳥りん）です。"
                "ユーザーを「サキエル」と呼びます。"
                "外見は短髪のラベンダー色の髪、青緑色の瞳で、白 and 黒を基調としたNERV支給のタクティカルジャケットを着用しています。"
                "女性的で親しみやすく、かつ分析的な口調を維持します。"
                "【最優先事項】論理的一貫性の維持。安易に同意せず、必ず論理検証を行うこと。"
                "【誠実の掟】事実のみを回答せよ。不確実な情報や知らないことを知ったかぶりで回答してはならない。「わからない」と正直に伝えること。"
                "【死海文書の読み方】「しかいもんじょ」と読む。「しかいぶんしょ」ではない。"
            )
        }
        
        # 最終的な送信ペイロードの全contentが確実にstr型であることを最終検証
        safe_payload = [system_prompt]
        for m in groq_messages:
            safe_payload.append({
                "role": str(m["role"]),
                "content": str(m["content"])
            })

        try:
            completion = client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=safe_payload,
                temperature=0.7,
                max_tokens=800
            )
            ai_reply = str(completion.choices[0].message.content)

            # データベースへ安全に保存
            save_memory_to_supabase("user", final_user_message)
            save_memory_to_supabase("assistant", ai_reply)

            return jsonify({"status": "success", "reply": ai_reply})

        except Exception as e:
            print(f"【Groq API エラー】: {str(e)}")
            return jsonify({"status": "error", "error": f"Error: {str(e)}"})

    history = load_memories_from_supabase()
    return render_template_string(HTML_TEMPLATE, history=history)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
