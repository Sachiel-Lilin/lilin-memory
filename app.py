import os
from flask import Flask, render_template_string, request, jsonify
from groq import Groq
from supabase import create_client, Client

app = Flask(__name__)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

groq_client = Groq(api_key=GROQ_API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>リリン - 診断モード</title>
    <style>
        body { background-color: #121212; color: #fff; font-family: sans-serif; padding: 20px; }
        .box { background: #222; padding: 15px; border-radius: 8px; margin-bottom: 15px; }
        button { background: #d4af37; border: none; padding: 10px 20px; font-weight: bold; cursor: pointer; border-radius: 5px; }
        pre { background: #111; padding: 10px; overflow-x: auto; color: #0ff; }
    </style>
</head>
<body>
    <h2>リリン - システム診断</h2>
    <div class="box">
        <p>「診断開始」を押すと、あなたのGroq APIキーで現在利用できるモデル一覧を取得します。</p>
        <button onclick="checkModels()">モデル一覧を確認する</button>
    </div>
    <div class="box">
        <h3>結果:</h3>
        <pre id="result">ここに結果が表示されます...</pre>
    </div>

    <script>
        async function checkModels() {
            document.getElementById('result').innerText = "確認中...";
            try {
                const res = await fetch('/debug-models');
                const data = await res.json();
                document.getElementById('result').innerText = JSON.stringify(data, null, 2);
            } catch (e) {
                document.getElementById('result').innerText = "エラー: " + e;
            }
        }
    </script>
</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route("/debug-models", methods=["GET"])
def debug_models():
    try:
        # Groqから利用可能なモデル一覧を取得を試みる
        models = groq_client.models.list()
        model_ids = [m.id for m in models.data]
        return jsonify({"status": "success", "available_models": model_ids})
    except Exception as e:
        import traceback
        return jsonify({"status": "error", "message": str(e), "trace": traceback.format_exc()})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
