import os
from flask import Flask, render_template_string
from groq import Groq

app = Flask(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

@app.route("/", methods=["GET"])
def index():
    models_list = []
    error_message = None

    if not client:
        error_message = "Groq APIキーが設定されていません。"
    else:
        try:
            # Groqから利用可能なモデルの一覧を取得
            response = client.models.list()
            for model in response.data:
                models_list.append(model.id)
        except Exception as e:
            error_message = f"モデル一覧の取得に失敗しました: {e}"

    # ブラウザにシンプルに一覧を表示するHTML
    html_content = """
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Groq 利用可能モデル一覧</title>
        <style>
            body { background-color: #121212; color: #e0e0e0; font-family: sans-serif; padding: 20px; }
            h1 { color: #d4af37; font-size: 20px; }
            ul { line-height: 1.8; }
            li { background: #1e1e1e; margin-bottom: 6px; padding: 8px 12px; border-radius: 4px; border: 1px solid #333; }
            .error { color: #ff8080; background: #4a2b2b; padding: 10px; border-radius: 4px; }
        </style>
    </head>
    <body>
        <h1>現在使えるGroqモデル一覧</h1>
        {% if error %}
            <div class="error">{{ error }}</div>
        {% elif models %}
            <p>以下のモデルがこのAPIキーで使用可能です：</p>
            <ul>
                {% for m in models %}
                    <li><code>{{ m }}</code></li>
                {% endfor %}
            </ul>
        {% else %}
            <p>利用可能なモデルが見つかりませんでした。</p>
        {% endif %}
    </body>
    </html>
    """
    return render_template_string(html_content, models=models_list, error=error_message)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
