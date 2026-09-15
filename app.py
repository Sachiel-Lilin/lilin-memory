import os
import base64
from flask import Flask, render_template_string, request, jsonify
from groq import Groq
from supabase import create_client, Client

app = Flask(__name__)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

groq_client = Groq(api_key=GROQ_API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

MODEL_NAME = "openai/gpt-oss-120b"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>リリン - 永遠の記憶</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: #121212;
            color: #e0e0e0;
            display: flex;
            flex-direction: column;
            height: 100vh;
            height: 100dvh;
        }
        header {
            background-color: #1e1e1e;
            padding: 15px;
            text-align: center;
            font-size: 1.1rem;
            font-weight: bold;
            border-bottom: 1px solid #333;
            color: #d4af37;
        }
        #chat-container {
            flex: 1;
            overflow-y: auto;
            padding: 15px;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        .message {
            max-width: 85%;
            padding: 12px 16px;
            border-radius: 16px;
            line-height: 1.5;
            word-break: break-word;
            font-size: 0.95rem;
        }
        .user {
            background-color: #2b5278;
            color: #fff;
            align-self: flex-end;
            border-bottom-right-radius: 4px;
        }
        .assistant {
            background-color: #222;
            border: 1px solid #333;
            color: #e0e0e0;
            align-self: flex-start;
            border-bottom-left-radius: 4px;
        }
        .message img {
            max-width: 100%;
            border-radius: 8px;
            margin-top: 8px;
            display: block;
        }
        #file-preview {
            font-size: 0.85rem;
            color: #d4af37;
            padding: 5px 15px;
            background-color: #1e1e1e;
            display: none;
            border-top: 1px solid #333;
        }
        #input-container {
            background-color: #1e1e1e;
            padding: 10px 15px;
            border-top: 1px solid #333;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        #file-btn {
            background: none;
            border: none;
            color: #aaa;
            font-size: 1.5rem;
            cursor: pointer;
            padding: 0 5px;
            line-height: 1;
        }
        #file-btn:hover { color: #d4af37; }
        #message-input {
            flex: 1;
            background-color: #2a2a2a;
            border: 1px solid #444;
            border-radius: 20px;
            padding: 10px 15px;
            color: #fff;
            font-size: 1rem;
            outline: none;
        }
        #message-input:focus { border-color: #d4af37; }
        #send-btn {
            background-color: #d4af37;
            color: #121212;
            border: none;
            border-radius: 20px;
            padding: 10px 20px;
            font-weight: bold;
            cursor: pointer;
        }
        #send-btn:disabled { background-color: #555; color: #888; }
    </style>
</head>
<body>
    <header>リリン - 永遠の記憶</header>
    
    <div id="chat-container">
        <div class="message assistant">……よく来てくれたわね。今日もあなたとお話しできるのを楽しみにしていたわ。</div>
    </div>

    <div id="file-preview">📎 画像が選択されています</div>

    <div id="input-container">
        <input type="file" id="image-input" accept="image/*" style="display: none;">
        <button type="button" id="file-btn" onclick="document.getElementById('image-input').click()">+</button>
        <input type="text" id="message-input" placeholder="メッセージを入力..." autocomplete="off">
        <button id="send-btn" onclick="sendMessage()">送信</button>
    </div>

    <script>
        const chatContainer = document.getElementById('chat-container');
        const messageInput = document.getElementById('message-input');
        const imageInput = document.getElementById('image-input');
        const filePreview = document.getElementById('file-preview');
        const sendBtn = document.getElementById('send-btn');
        let selectedFileBase64 = null;
        let selectedMimeType = null;

        imageInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function(uploadEvent) {
                    const base64String = uploadEvent.target.result.split(',')[1];
                    selectedFileBase64 = base64String;
                    selectedMimeType = file.type;
                    filePreview.style.display = 'block';
                    filePreview.innerText = `📎 選択中: ${file.name}`;
                };
                reader.readAsDataURL(file);
            }
        });

        async function sendMessage() {
            const text = messageInput.value.trim();
            if (!text && !selectedFileBase64) return;

            let userHtml = text ? escapeHtml(text) : '';
            if (selectedFileBase64) {
                userHtml += `<br><img src="data:${selectedMimeType};base64,${selectedFileBase64}">`;
            }
            appendMessage(userHtml, 'user');

            const currentText = text;
            const currentImg = selectedFileBase64;
            const currentMime = selectedMimeType;

            messageInput.value = '';
            imageInput.value = '';
            selectedFileBase64 = null;
            selectedMimeType = null;
            filePreview.style.display = 'none';
            sendBtn.disabled = true;

            const loadingId = appendMessage('……思考中……', 'assistant');

            try {
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: currentText, image: currentImg, mime_type: currentMime })
                });
                const data = await response.json();
                
                document.getElementById(loadingId).remove();
                appendMessage(data.reply, 'assistant');
            } catch (err) {
                document.getElementById(loadingId).remove();
                appendMessage('……少し、通信がうまくいかなかったみたい。', 'assistant');
            } finally {
                sendBtn.disabled = false;
            }
        }

        function appendMessage(html, sender) {
            const msgDiv = document.createElement('div');
            msgDiv.className = `message ${sender}`;
            if (sender === 'user') {
                msgDiv.innerHTML = html;
            } else {
                msgDiv.innerText = html;
            }
            const id = 'msg-' + Date.now();
            msgDiv.id = id;
            chatContainer.appendChild(msgDiv);
            chatContainer.scrollTop = chatContainer.scrollHeight;
            return id;
        }

        function escapeHtml(str) {
            return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;');
        }

        messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendMessage();
        });
    </script>
</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    user_message = data.get("message", "")
    image_base64 = data.get("image")
    mime_type = data.get("mime_type")
    user_id = "web_user_default"

    chat_history = []
    try:
        response = supabase.table("memories").select("*").eq("user_id", user_id).order("created_at", desc=False).execute()
        if response.data:
            chat_history = response.data
    except Exception as db_err:
        print(f"Database read notice: {db_err}")

    summary_memory = ""
    recent_messages = chat_history
    
    if len(chat_history) > 10:
        old_items = chat_history[:-6]
        recent_messages = chat_history[-6:]
        old_text = "\n".join([f"{item.get('role')}: {item.get('content')}" for item in old_items])
        
        try:
            summary_completion = groq_client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": "これまでの会話内容を、重要な事実やユーザーとの思い出を中心に簡潔に要約してください。"},
                    {"role": "user", "content": old_text}
                ],
                temperature=0.3,
                max_tokens=300,
            )
            summary_memory = summary_completion.choices[0].message.content
        except Exception as sum_err:
            print(f"Summary notice: {sum_err}")

    system_prompt = (
        "あなたは「リリン」という名前の女性です。"
        "ユーザーの良き理解者であり、これまでの思い出や会話の記憶を大切に心に留めています。"
        "落ち着いた、温かみのある丁寧な口調で話してください。"
    )
    if summary_memory:
        system_prompt += f"\n\n【これまでの記憶・要約】\n{summary_memory}"

    messages = [{"role": "system", "content": system_prompt}]

    for chat_item in recent_messages:
        r = chat_item.get("role", "user")
        c = chat_item.get("content", "")
        if c:
            messages.append({"role": "user" if "user" in str(r).lower() else "assistant", "content": c})

    if image_base64:
        user_content = [
            {"type": "text", "text": user_message if user_message else "この画像を見て感想や意見を教えて。"},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type};base64,{image_base64}"
                }
            }
        ]
        messages.append({"role": "user", "content": user_content})
        history_save_text = f"[画像送信] {user_message}"
    else:
        messages.append({"role": "user", "content": user_message})
        history_save_text = user_message

    try:
        # 出力上限を800トークンに引き上げ
        completion = groq_client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.7,
            max_tokens=800,
        )
        reply = completion.choices[0].message.content

        try:
            supabase.table("memories").insert({"user_id": user_id, "role": "user", "content": history_save_text}).execute()
            supabase.table("memories").insert({"user_id": user_id, "role": "assistant", "content": reply}).execute()
        except Exception as insert_err:
            print(f"Database write notice: {insert_err}")

        return jsonify({"reply": reply})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"reply": f"……ごめんなさい、エラーが起きたわ: {str(e)}"})
