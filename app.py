import os
import base64
from flask import Flask, render_template_string, request, jsonify
from groq import Groq
import sqlite3

app = Flask(__name__)

# --- 設定 ---
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "your-groq-api-key-here")
client = Groq(api_key=GROQ_API_KEY)
DB_NAME = "memory.db"

# --- データベース初期化 ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT,
            content TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- HTML テンプレート（複数画像添付対応） ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>リリン - 永遠の記憶</title>
    <style>
        body { background-color: #121212; color: #e0e0e0; font-family: sans-serif; margin: 0; padding: 0; display: flex; flex-direction: column; height: 100vh; }
        header { background: #1f1f1f; padding: 15px; text-align: center; font-weight: bold; border-bottom: 1px solid #333; color: #d4af37; }
        #chat-container { flex: 1; overflow-y: auto; padding: 15px; display: flex; flex-direction: column; gap: 10px; }
        .message { padding: 10px 14px; border-radius: 8px; max-width: 80%; line-height: 1.5; word-break: break-all; }
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
    <header>リリン - 永遠の記憶</header>
    <div id="chat-container">
        {% for role, content in history %}
            <div class="message {{ role }}">{{ content | safe }}</div>
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
                countSpan.textContent = `${input.files.length}枚選択`;
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
            msgInput.value = '';
            fileInput.value = '';
            document.getElementById('file-count').textContent = '';

            const userDiv = document.createElement('div');
            userDiv.className = 'message user';
            userDiv.textContent = userText + (fileInput.files.length > 0 ? ' [画像添付]' : '');
            chatContainer.appendChild(userDiv);
            chatContainer.scrollTop = chatContainer.scrollHeight;

            try {
                const response = await fetch('/', { method: 'POST', body: formData });
                const data = await response.json();

                const aiDiv = document.createElement('div');
                aiDiv.className = data.status === 'success' ? 'message assistant' : 'message error';
                aiDiv.innerHTML = data.reply || data.error;
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

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        user_message = request.form.get("message", "")
        uploaded_files = request.files.getlist("images")

        # 1. データベースから過去の会話履歴（テキストのみ）をロード
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT role, content FROM messages ORDER BY id ASC")
        rows = cursor.fetchall()
        
        groq_messages = []
        for role, content in rows:
            groq_messages.append({"role": role, "content": content})
        conn.close()

        # 2. 今回のユーザー入力メッセージの組み立て
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

        groq_messages.append({"role": "user", "content": current_content})

        try:
            # 3. Groq APIの呼び出し（モデル名を設定に合わせて指定）
            completion = client.chat.completions.create(
                model="openai/gpt-oss-120b",  # 正しいモデル名に修正
                messages=groq_messages,
                temperature=0.7,
                max_tokens=1024
            )
            ai_reply = completion.choices[0].message.content

            # 4. データベースへはテキストのみを保存（画像は保存しない）
            db_user_content = user_message + (" [画像送信]" if has_images else "")
            
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO messages (role, content) VALUES (?, ?)", ("user", db_user_content))
            cursor.execute("INSERT INTO messages (role, content) VALUES (?, ?)", ("assistant", ai_reply))
            conn.commit()
            conn.close()

            return jsonify({"status": "success", "reply": ai_reply})

        except Exception as e:
            return jsonify({"status": "error", "error": f"Error: {str(e)}"})

    # GETアクセス時
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT role, content FROM messages ORDER BY id ASC")
    history = cursor.fetchall()
    conn.close()

    return render_template_string(HTML_TEMPLATE, history=history)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
