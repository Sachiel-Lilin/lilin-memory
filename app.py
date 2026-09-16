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
# 2. Supabase 側でのデータ入出力関数（contentカラム専用）
# ==========================================
def load_memories_from_supabase() -> list:
    """Supabaseの memories テーブルから会話履歴（content）を読み込む"""
    try:
        response = supabase.table("memories") \
            .select("content, created_at") \
            .order("created_at", desc=False) \
            .execute()
        
        history = []
        if response.data:
            for row in response.data:
                content = row.get("content", "")
                if not isinstance(content, str):
                    content = str(content)
                
                # contentの形式（例: "user: こんにちは" や "assistant: ..."）からロールを復元する簡易パース
                if content.startswith("user: "):
                    history.append({"role": "user", "content": content[6:]})
                elif content.startswith("assistant: "):
                    history.append({"role": "assistant", "content": content[11:]})
                else:
                    # デフォルトとしてユーザー扱い、あるいはそのまま保持
                    history.append({"role": "user", "content": content})
                    
        return history
    except Exception as e:
        print(f"【DB読み込みエラー】: {e}")
        return []

def save_memory_to_supabase(role: str, content: str):
    """Supabaseの memories テーブルに 'role: content' の形式で文字列を保存する"""
    try:
        if not isinstance(content, str):
            content = str(content)
            
        # 既存の id と content のみのテーブル構造に合わせ、ロールを内包した文字列として保存する
        formatted_content = f"{role}: {content}"
            
        supabase.table("memories").insert({
            "content": formatted_content
        }).execute()
        print(f"【DB保存成功】 {formatted_content[:30]}...")
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
    <title>咲鳥リン</title>
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
    <header>咲鳥リン</header>
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

        groq_messages = []
        for msg in db_history:
            role = str(msg.get("role", "user"))
            content = str(msg.get("content", ""))
            groq_messages.append({"role": role, "content": content})

        current_content = []
        if user_message:
            current_content.append({"type": "text", "text": user_message})

        has_images = False
        for file in uploaded_files:
            if file and file.filename != '':
                image_bytes = file.read()
                base64_image = base64.b64encode(image_bytes).decode('utf-8')
                ext = file.filename.split('.')[-1].lower()
                mime_type = f"image/{ext}" if ext in ['png', 'jpeg', 'jpg', 'webp', 'gif'] else "image/jpeg"
                
                current_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}
                })
                has_images = True

        if not current_content:
            return jsonify({"status": "error", "error": "メッセージまたは画像を入力してください。"})

        groq_messages.append({"role": "user", "content": current_content if has_images else user_message})

        system_prompt = {
            "role": "system", 
            "content": "あなたは咲鳥リン（さきとりりん）です。ユーザーをサキエルと呼びます。落ち着いた温かみのある良き理解者として、丁寧かつ知的な口調で応答してください。"
        }
        payload = [system_prompt] + groq_messages

        try:
            completion = client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=payload,
                temperature=0.7,
                max_tokens=800
            )
            ai_reply = completion.choices[0].message.content

            db_user_content = user_message + (" [画像送信]" if has_images else "")
            
            # 既存テーブルの構造（id, content）に合わせて保存を実行
            save_memory_to_supabase("user", db_user_content)
            save_memory_to_supabase("assistant", ai_reply)

            return jsonify({"status": "success", "reply": ai_reply})

        except Exception as e:
            return jsonify({"status": "error", "error": f"Error: {str(e)}"})

    history = load_memories_from_supabase()
    return render_template_string(HTML_TEMPLATE, history=history)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
