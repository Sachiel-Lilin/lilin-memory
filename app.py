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
# 2. Supabase 側でのデータ入出力関数
# ==========================================
def load_memories_from_supabase() -> list:
    """Supabaseの memories テーブルから会話履歴を読み込む"""
    try:
        response = supabase.table("memories") \
            .select("content, created_at") \
            .order("created_at", desc=False) \
            .execute()
        
        history = []
        if response.data:
            for row in response.data:
                raw_content = row.get("content", "")
                if not isinstance(raw_content, str):
                    raw_content = str(raw_content)
                
                if raw_content.startswith("user: "):
                    role = "user"
                    content_text = raw_content[6:]
                elif raw_content.startswith("assistant: "):
                    role = "assistant"
                    content_text = raw_content[11:]
                else:
                    role = "user"
                    content_text = raw_content
                
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
# 3. HTML テンプレート（スレッド内画像サムネイル表示対応）
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>咲鳥りん (リリン)</title>
    <style>
        * { box-sizing: border-box; }
        body { 
            background-color: #121212; 
            color: #e0e0e0; 
            font-family: sans-serif; 
            margin: 0; 
            padding: 0; 
            height: 100dvh; 
            display: flex; 
            flex-direction: column; 
            overflow: hidden;
        }
        header { 
            background: #1f1f1f; 
            padding: 12px; 
            text-align: center; 
            font-weight: bold; 
            border-bottom: 1px solid #333; 
            color: #d4af37; 
            flex-shrink: 0;
        }
        #chat-container { 
            flex: 1; 
            overflow-y: auto; 
            padding: 15px; 
            display: flex; 
            flex-direction: column; 
            gap: 12px; 
            -webkit-overflow-scrolling: touch;
        }
        .message { 
            padding: 12px 16px; 
            border-radius: 8px; 
            max-width: 90%; 
            line-height: 1.5; 
            word-break: break-all; 
            white-space: pre-wrap; 
        }
        .user { background: #2b3a4a; align-self: flex-end; }
        .assistant { background: #1e1e1e; align-self: flex-start; border: 1px solid #333; }
        .error { background: #4a2b2b; align-self: center; color: #ff8080; }
        
        /* スレッド内の画像サムネイル */
        .msg-image-container {
            display: flex;
            gap: 6px;
            margin-top: 8px;
            flex-wrap: wrap;
        }
        .msg-thumb {
            width: 80px;
            height: 80px;
            border-radius: 4px;
            object-fit: cover;
            border: 1px solid #444;
        }

        /* プレビュー領域のスタイル */
        #preview-container {
            display: flex;
            gap: 8px;
            padding: 0 10px;
            margin-bottom: 4px;
            flex-wrap: wrap;
        }
        .preview-thumb-wrapper {
            position: relative;
            width: 60px;
            height: 60px;
            border-radius: 4px;
            overflow: hidden;
            border: 1px solid #444;
            background: #222;
        }
        .preview-thumb-wrapper img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }

        form { 
            background: #1f1f1f; 
            padding: 10px; 
            display: flex; 
            flex-direction: column;
            border-top: 1px solid #333; 
            flex-shrink: 0;
            position: sticky;
            bottom: 0;
            width: 100%;
            z-index: 10;
        }
        .form-row {
            display: flex;
            gap: 8px;
            align-items: center;
            width: 100%;
        }
        input[type="text"] { 
            flex: 1; 
            padding: 10px; 
            border-radius: 4px; 
            border: 1px solid #444; 
            background: #2a2a2a; 
            color: #fff; 
            font-size: 16px; 
        }
        input[type="file"] { display: none; }
        .file-label { 
            background: #333; 
            color: #ccc; 
            padding: 8px 12px; 
            border-radius: 4px; 
            cursor: pointer; 
            font-size: 14px; 
            white-space: nowrap;
        }
        .file-label:hover { background: #444; }
        button[type="submit"] { 
            background: #d4af37; 
            color: #121212; 
            border: none; 
            padding: 10px 16px; 
            border-radius: 4px; 
            font-weight: bold; 
            cursor: pointer; 
            white-space: nowrap;
        }
        button[type="submit"]:hover { background: #e6c555; }
    </style>
</head>
<body>
    <header>咲鳥りん (リリン)</header>
    <div id="chat-container">
        {% for msg in history %}
            <div class="message {{ msg.role }}">
                {{ msg.content | safe }}
            </div>
        {% endfor %}
    </div>
    
    <form id="chat-form" enctype="multipart/form-data">
        <div id="preview-container"></div>
        <div class="form-row">
            <label class="file-label" for="images">＋画像</label>
            <input type="file" id="images" name="images" accept="image/*" multiple onchange="handleFileSelect(event)">
            <input type="text" id="message-input" name="message" placeholder="メッセージを入力..." autocomplete="off">
            <button type="submit">送信</button>
        </div>
    </form>

    <script>
        const chatContainer = document.getElementById('chat-container');
        chatContainer.scrollTop = chatContainer.scrollHeight;

        let selectedFilesBase64 = [];

        function handleFileSelect(event) {
            const input = event.target;
            const previewContainer = document.getElementById('preview-container');
            previewContainer.innerHTML = '';
            selectedFilesBase64 = [];

            if (input.files.length > 0) {
                if (input.files.length > 2) {
                    alert("一度に送信できる画像は最大2枚までです。");
                    input.value = "";
                    return;
                }

                for (let i = 0; i < input.files.length; i++) {
                    const file = input.files[i];
                    const reader = new FileReader();

                    reader.onload = function(e) {
                        const base64Data = e.target.result;
                        selectedFilesBase64.push(base64Data);

                        const wrapper = document.createElement('div');
                        wrapper.className = 'preview-thumb-wrapper';
                        
                        const img = document.createElement('img');
                        img.src = base64Data;
                        
                        wrapper.appendChild(img);
                        previewContainer.appendChild(wrapper);
                    }
                    reader.readAsDataURL(file);
                }
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
            const currentImages = [...selectedFilesBase64];
            
            // フォームとプレビューをリセット
            msgInput.value = '';
            fileInput.value = '';
            selectedFilesBase64 = [];
            document.getElementById('preview-container').innerHTML = '';

            // ユーザーメッセージの吹き出しを作成（テキスト ＋ サムネイル画像）
            const userDiv = document.createElement('div');
            userDiv.className = 'message user';
            
            const textSpan = document.createElement('div');
            textSpan.textContent = userText;
            userDiv.appendChild(textSpan);

            if (currentImages.length > 0) {
                const imgContainer = document.createElement('div');
                imgContainer.className = 'msg-image-container';
                currentImages.forEach(imgSrc => {
                    const thumb = document.createElement('img');
                    thumb.className = 'msg-thumb';
                    thumb.src = imgSrc;
                    imgContainer.appendChild(thumb);
                });
                userDiv.appendChild(imgContainer);
            }

            chatContainer.appendChild(userDiv);
            chatContainer.scrollTop = chatContainer.scrollHeight;

            try {
                const response = await fetch('/', { method: 'POST', body: formData });
                const data = await response.json();

                const aiDiv = document.createElement('div');
                aiDiv.className = data.status === 'success' ? 'message assistant' : 'message error';
                aiDiv.textContent = data.reply || data.error;
                chatContainer.appendChild(aiDiv);

                aiDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });

            } catch (err) {
                const errDiv = document.createElement('div');
                errDiv.className = 'message error';
                errDiv.textContent = '通信エラーが発生しました。';
                chatContainer.appendChild(errDiv);
                chatContainer.scrollTop = chatContainer.scrollHeight;
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
            r = str(msg.get("role", "user"))
            c = str(msg.get("content", ""))
            groq_messages.append({"role": r, "content": c})

        valid_files = [f for f in uploaded_files if f and f.filename != ''][:2]
        image_contents = []
        db_image_tags = []
        
        for f in valid_files:
            file_bytes = f.read()
            encoded_image = base64.b64encode(file_bytes).decode('utf-8')
            mime_type = f.content_type or 'image/jpeg'
            
            data_url = f"data:{mime_type};base64,{encoded_image}"
            
            image_contents.append({
                "type": "image_url",
                "image_url": {
                    "url": data_url
                }
            })
            # DBに保存する際、HTMLタグ（<img>）として履歴に埋め込めるようにする
            db_image_tags.append(f'<img class="msg-thumb" src="{data_url}">')

        final_user_message = str(user_message).strip()
        if not final_user_message and not valid_files:
            return jsonify({"status": "error", "error": "メッセージまたは画像を入力してください。"})

        # DB保存用のテキスト構築
        db_save_message = final_user_message
        if db_image_tags:
            db_save_message += f'<div class="msg-image-container">{"".join(db_image_tags)}</div>'

        if image_contents:
            current_content_payload = []
            if final_user_message:
                current_content_payload.append({"type": "text", "text": final_user_message})
            current_content_payload.extend(image_contents)
            
            current_message_for_groq = {"role": "user", "content": current_content_payload}
        else:
            current_message_for_groq = {"role": "user", "content": final_user_message}

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
        
        safe_payload = [system_prompt]
        for m in groq_messages:
            safe_payload.append({
                "role": str(m["role"]),
                "content": str(m["content"])
            })
        safe_payload.append(current_message_for_groq)

        try:
            completion = client.chat.completions.create(
                model="qwen/qwen3.8-27b",
                messages=safe_payload,
                temperature=0.7,
                max_tokens=800
            )
            ai_reply = str(completion.choices[0].message.content)

            save_memory_to_supabase("user", db_save_message)
            save_memory_to_supabase("assistant", ai_reply)

            return jsonify({"status": "success", "reply": ai_reply})

        except Exception as e:
            print(f"【Groq API エラー】: {str(e)}")
            return jsonify({"status": "error", "error": f"Error: {str(e)}"})

    history = load_memories_from_supabase()
    return render_template_string(HTML_TEMPLATE, history=history)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
