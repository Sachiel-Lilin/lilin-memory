import os
from flask import Flask, render_template_string, request, jsonify
from google import genai

app = Flask(__name__)
client = genai.Client()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Lilin Memory</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { background: #121212; color: #e0e0e0; font-family: sans-serif; padding: 20px; max-width: 600px; margin: auto; }
        .chat-box { height: 70vh; overflow-y: scroll; border: 1px solid #333; padding: 10px; margin-bottom: 10px; background: #1e1e1e; }
        .msg { margin: 10px 0; padding: 8px; border-radius: 5px; word-break: break-all; }
        .user { background: #2c3e50; text-align: right; }
        .bot { background: #34495e; }
        input, button { width: 100%; padding: 10px; margin-top: 5px; box-sizing: border-box; }
    </style>
</head>
<body>
    <h2>Lilin Memory</h2>
    <div class="chat-box" id="chatBox"></div>
    <input type="text" id="userInput" placeholder="メッセージを入力..." onkeypress="if(event.key==='Enter')sendMessage()">
    <button onclick="sendMessage()">送信</button>

    <script>
        async function sendMessage() {
            const input = document.getElementById('userInput');
            const chatBox = document.getElementById('chatBox');
            const text = input.value;
            if (!text) return;

            chatBox.innerHTML += `<div class="msg user">${text}</div>`;
            input.value = '';
            chatBox.scrollTop = chatBox.scrollHeight;

            try {
                const res = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: text })
                });
                const data = await res.json();
                const replyText = data.reply !== undefined ? data.reply : "レスポンスエラー";
                chatBox.innerHTML += `<div class="msg bot">${replyText}</div>`;
            } catch (err) {
                chatBox.innerHTML += `<div class="msg bot">通信エラーが発生しました</div>`;
            }
            chatBox.scrollTop = chatBox.scrollHeight;
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json() or {}
        user_message = data.get('message', '')
        
        response = client.models.generate_content(
            model='gemini-3.5-flash',
            contents=user_message,
        )
        return jsonify({'reply': response.text})
    except Exception as e:
        return jsonify({'reply': f'サーバーエラー: {str(e)}'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
