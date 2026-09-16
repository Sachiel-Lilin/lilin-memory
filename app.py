import os
from flask import Flask, render_template_string, request, jsonify
from google import genai
from supabase import create_client, Client

app = Flask(__name__)

# クライアントの設定（環境変数から取得）
gemini_api_key = os.environ.get("GEMINI_API_KEY", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

# 新しいGoogle Gen AI SDKの初期化
client = genai.Client(api_key=gemini_api_key)
        # 現在のAPIキーで利用可能なモデルをリストアップしてログに出力
        try:
            print("=== 利用可能なモデル一覧 ===")
            for m in client.models.list():
                print(f"Model Name: {m.name}")
            print("============================")
        except Exception as list_err:
            print(f"モデル一覧の取得に失敗: {list_err}")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 履歴の読み込み（Supabaseから取得）
def load_memories_from_supabase():
    try:
        response = supabase.table("memories").select("content").order("created_at", desc=False).execute()
        if response.data:
            return [row.get("content", "") for row in response.data]
        return []
    except Exception as e:
        print(f"Supabase読込エラー: {e}")
        return []

# 履歴の保存
def save_memory_to_supabase(role, text):
    try:
        content = f"{role}: {text}"
        supabase.table("memories").insert({"content": content}).execute()
        
        # 簡易的なフリーレン方式（例：20件を超えたら古いものを整理する等の処理をここに挟むことも可能）
        history = load_memories_from_supabase()
        if len(history) > 20:
            # 古いものを削るなどの処理
            pass
    except Exception as e:
        print(f"Supabase保存エラー: {e}")

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        user_message = request.form.get("message", "")
        
        # データベースからこれまでの履歴をロード
        history = load_memories_from_supabase()
        
        # Geminiに渡すためのプロンプト構成
        # 履歴のテキストリストに今回のユーザー発言を追加
        chat_contents = history + [f"user: {user_message}"]
        
        try:
            # 新SDKでのコンテンツ生成（例: gemini-2.5-flash）
            response = client.models.generate_content(
                model='gemini3.6-flash',
                contents=chat_contents,
            )
            ai_reply = str(response.text)
            
            # データベースに保存
            save_memory_to_supabase("user", user_message)
            save_memory_to_supabase("assistant", ai_reply)
            
            return jsonify({"status": "success", "reply": ai_reply})
            
        except Exception as e:
            print(f"Gemini API エラー: {str(e)}")
            return jsonify({"status": "error", "error": f"Error: {str(e)}"})

    # GETアクセスのときはチャット画面を表示（必要に応じてHTMLテンプレートをここに）
    return render_template_string(HTML_TEMPLATE, history=load_memories_from_supabase())

# チャット画面のHTMLテンプレート（スマホ対応・textarea＆送信ボタン）
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>咲鳥りん（リリン）</title>
    <style>
        body { background-color: #121212; color: #e0e0e0; font-family: sans-serif; margin: 0; padding: 10px; display: flex; flex-direction: column; height: 100vh; box-sizing: border-box; }
        h2 { text-align: center; color: #f0a500; font-size: 1.1rem; margin: 5px 0; }
        #chat-container { flex: 1; overflow-y: auto; border: 1px solid #333; padding: 10px; margin-bottom: 10px; background: #1e1e1e; border-radius: 8px; display: flex; flex-direction: column; gap: 8px; }
        .message { padding: 8px 12px; border-radius: 6px; max-width: 85%; word-break: break-all; font-size: 0.95rem; line-height: 1.4; }
        .user { background: #2b2b2b; align-self: flex-end; color: #fff; }
        .assistant { background: #332211; align-self: flex-start; color: #ffeb3b; border: 1px solid #553311; }
        #input-form { display: flex; gap: 5px; align-items: flex-end; }
        textarea { flex: 1; padding: 8px; background: #222; color: #fff; border: 1px solid #444; border-radius: 4px; resize: none; height: 40px; font-size: 1rem; }
        button { padding: 8px 15px; background: #f0a500; color: #121212; border: none; border-radius: 4px; font-weight: bold; cursor: pointer; height: 40px; }
    </style>
</head>
<body>
    <h2>咲鳥りん（リリン）</h2>
    <div id="chat-container">
        {% for item in history %}
            {% set parts = item.split(': ', 1) %}
            <div class="message {{ parts[0] }}">{{ parts[1] if parts|length > 1 else item }}</div>
        {% endfor %}
    </div>
    <form id="input-form">
        <textarea name="message" id="message-input" placeholder="メッセージを入力..." required></textarea>
        <button type="submit" id="send-btn">送信</button>
    </form>

    <script>
        const container = document.getElementById('chat-container');
        container.scrollTop = container.scrollHeight;

        const form = document.getElementById('input-form');
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const textarea = document.getElementById('message-input');
            const message = textarea.value.trim();
            if (!message) return;

            // ユーザーのメッセージを即時表示
            const userDiv = document.createElement('div');
            userDiv.className = 'message user';
            userDiv.textContent = message;
            container.appendChild(userDiv);
            textarea.value = '';
            container.scrollTop = container.scrollHeight;

            try {
                const formData = new FormData();
                formData.append('message', message);
                const res = await fetch('/', { method: 'POST', body: formData });
                const data = await res.json();

                const aiDiv = document.createElement('div');
                aiDiv.className = 'message assistant';
                if (data.status === 'success') {
                    aiDiv.textContent = data.reply;
                } else {
                    aiDiv.textContent = 'Error: ' + data.error;
                }
                container.appendChild(aiDiv);
                container.scrollTop = container.scrollHeight;
            } catch (err) {
                const errDiv = document.createElement('div');
                errDiv.className = 'message assistant';
                errDiv.textContent = 'Error: Connection error.';
                container.appendChild(aiDiv);
                container.scrollTop = container.scrollHeight;
            }
        });
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
