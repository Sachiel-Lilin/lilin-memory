import os
from flask import Flask, render_template_string, request, jsonify
from groq import Groq
from supabase import create_client, Client

app = Flask(__name__)

# --- 環境変数の取得 ---
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

groq_client = Groq(api_key=GROQ_API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- スマホ対応チャットUIのHTML ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>リリン - 記憶の伴侶</title>
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
        #input-container {
            background-color: #1e1e1e;
            padding: 10px 15px;
            border-top: 1px solid #333;
            display: flex;
            align-items: center;
            gap: 10px;
        }
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
        <div class="message assistant">……よく来てくれたわね。いつでも、どんなお話でも聞かせてちょうだい。</div>
    </div>

    <div id="input-container">
        <input type="text" id="message-input" placeholder="メッセージを入力..." autocomplete="off">
        <button id="send-btn" onclick="sendMessage()">送信</button>
    </div>

    <script>
        const chatContainer = document.getElementById('chat-container');
        const messageInput = document.getElementById('message-input');
        const sendBtn = document.getElementById('send-btn');

        async function sendMessage() {
            const text = messageInput.value.trim();
            if (!text) return;

            appendMessage(text, 'user');
            messageInput.value = '';
            sendBtn.disabled = true;

            const loadingId = appendMessage('……思考中……', 'assistant');

            try {
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: text })
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

        function appendMessage(text, sender) {
            const msgDiv = document.createElement('div');
            msgDiv.className = `message ${sender}`;
            msgDiv.innerHTML = text;
            const id = 'msg-' + Date.now();
            msgDiv.id = id;
            chatContainer.appendChild(msgDiv);
            chatContainer.scrollTop = chatContainer.scrollHeight;
            return id;
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
    user_id = "web_user_default"

    chat_history = []
    try:
        response = supabase.table("memories").select("*").eq("user_id", user_id).limit(10).execute()
        if response.data:
            chat_history = response.data
    except Exception as db_err:
        print(f"Database read notice: {db_err}")

    messages = [
        {
            "role": "system",
            "content": (
                "あなたは「リリン」という名前のエルフの女性です。"
                "何百年、1000年以上生き続ける存在であり、ユーザーとの思い出や会話の記憶を永遠に心に留めています。"
                "落ち着いた、少し物静かでありながらも温かみのある口調で話してください。"
            )
        }
    ]

    for chat_item in chat_history:
        r = chat_item.get("role", "user")
        c = chat_item.get("content") or chat_item.get("message") or ""
        if c:
            messages.append({"role": "user" if "user" in str(r).lower() else "assistant", "content": c})

    messages.append({"role": "user", "content": user_message})

    try:
        # あなたのAPIキーで確実に利用可能なモデルを指定
        completion = groq_client.chat.completions.create(
            model="qwen/qwen3.8-27b",
            messages=messages,
            temperature=0.7,
        )
        reply = completion.choices[0].message.content

        try:
            supabase.table("memories").insert({"user_id": user_id, "role": "user", "content": user_message}).execute()
            supabase.table("memories").insert({"user_id": user_id, "role": "assistant", "content": reply}).execute()
        except Exception as insert_err:
            print(f"Database write notice: {insert_err}")

        return jsonify({"reply": reply})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"reply": f"……ごめんなさい、エラーが起きたわ: {str(e)}"})
