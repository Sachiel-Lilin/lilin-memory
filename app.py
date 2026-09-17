import os
from flask import Flask
from groq import Groq

app = Flask(__name__)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

@app.route("/")
def check_models():
    if not client:
        return "Groq APIキーが設定されていません。"
    
    try:
        # 利用可能なモデルの一覧を取得
        models = client.models.list()
        
        # 画面出力用のHTMLを組み立て
        html = "<h2>利用可能なGroqモデル一覧</h2><ul>"
        for model in models.data:
            print(f"Model ID: {model.id}")  # コンソールログにも出力
            html += f"<li><b>{model.id}</b></li>"
        html += "</ul>"
        
        return html
    except Exception as e:
        return f"エラーが発生しました: {e}"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
