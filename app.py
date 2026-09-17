import os
import time
import base64
from flask import Flask, render_template_string, request, jsonify
from groq import Groq
from supabase import create_client, Client
from tavily import TavilyClient

app = Flask(__name__)

# ==========================================
# 1. クライアントおよび接続の設定
# ==========================================
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None
tavily_client = TavilyClient(api_key=TAVILY_API_KEY) if TAVILY_API_KEY else None

# 使用するモデル
TARGET_MODEL = "qwen/qwen3.8-27b"

# ==========================================
# 2. Tavily検索関数
# ==========================================
def search_web(query: str) -> str:
    """Tavily APIを使用してWeb検索を行い、結果をテキストで返す"""
    if not tavily_client:
        return "（Tavily APIキーが設定されていないため検索できません）"
    try:
        response = tavily_client.search(query=query, max_results=3)
        results = response.get("results", [])
        search_summary = ""
        for r in results:
            title = r.get("title", "")
            snippet = r.get("content", "")
            url = r.get("url", "")
            search_summary += f"- タイトル: {title}\n  内容: {snippet}\n  URL: {url}\n\n"
        return search_summary
    except Exception as e:
        print(f"【Tavily検索エラー】: {e}")
        return "（Web検索中にエラーが発生しました）"

# ==========================================
# 3. Supabase 側でのデータ入出力・要約関数
# ==========================================
def load_memories_from_supabase() -> list:
    """Supabaseの memories テーブルから会話履歴を読み込む"""
    if not supabase:
        return []
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
                elif raw_content.startswith("system: "):
                    role = "system"
                    content_text = raw_content[8:]
                else:
                    role = "user"
                    content_text = raw_content
                
                history.append({"role": role, "content": str(content_text)})
                    
        if len(history) > 8:
            system_msgs = [m for m in history if m["role"] == "system"]
            recent_msgs = [m for m in history if m["role"] != "system"][-8:]
            history = system_msgs + recent_msgs

        return history
    except Exception as e:
        print(f"【DB読み込みエラー】: {e}")
        return []

def summarize_and_cleanup_memories():
    """履歴が多い場合、古いものを整理する（途切れたデータへの補完指示付き）"""
    if not supabase or not client:
        return
    try:
        history = load_memories_from_supabase()
        if len(history) > 10:
            older_history = history[:-5]
            recent_history = history[-5:]
            
            text_to_summarize = "\n".join([f"{m['role']}: {m['content']}" for m in older_history])
            
            summary_completion = client.chat.completions.create(
                model=TARGET_MODEL,
                messages=[
                    {"role": "system", "content": "あなたは優秀な記録係です。以下の会話の経緯を簡潔に日本語で要約してください。※途中で切れている文章が含まれる場合は、前後の文脈から意味を推測・補完して情報が欠損しないようにまとめてください。"},
                    {"role": "user", "content": text_to_summarize}
                ],
                temperature=0.3,
                max_tokens=200
            )
            summary_text = summary_completion.choices[0].message.content.strip()
            
            supabase.table("memories").delete().neq("content", "___DUMMY___").execute()
            
            supabase.table("memories").insert({
                "content": f"system: 【これまでの経緯の要約】 {summary_text}"
            }).execute()
            
            for m in recent_history:
                role_prefix = "assistant" if m['role'] == "assistant" else "user"
                supabase.table("memories").insert({
                    "content": f"{role_prefix}: {m['content']}"
                }).execute()
                
    except Exception as e:
        print(f"【要約処理エラー】: {e}")

def save_memory_to_supabase(role: str, content: str):
    """Supabaseの memories テーブルに保存する"""
    if not supabase:
        return
    try:
        if not isinstance(content, str):
            content = str(content)
            
        formatted_content = f"{role}: {content}"
            
        supabase.table("memories").insert({
            "content": formatted_content
        }).execute()
        
        summarize_and_cleanup_memories()
    except Exception as e:
        print(f"【DB保存エラー】: {e}")

# ==========================================
# 4. HTML テンプレート（改行対応・max_tokens増量版）
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>咲鳥りん (リリン)</title>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
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
        .message p { margin: 0 0 8px 0; }
        .message p:last-child { margin-bottom: 0; }
        .message ul, .message ol { margin: 4px 0; padding-left: 20px; }
        .message li { margin-bottom: 4px; }
        
        .user { background: #2b3a4a; align-self: flex-end; }
        .assistant { background: #1e1e1e; align-self: flex-start; border: 1px solid #333; }
        .error { background: #4a2b2b; align-self: center; color: #ff8080; }
        
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
            cursor: pointer;
            transition: opacity 0.2s;
        }
        .msg-thumb:hover { opacity: 0.8; }

        #image-modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.9);
            justify-content: center;
            align-items: center;
            flex-direction: column;
        }
        #modal-img {
            max-width: 90%;
            max-height: 80vh;
            object-fit: contain;
            border-radius: 4px;
        }
        #modal-close {
            position: absolute;
            top: 20px;
            left: 20px;
            color: #fff;
            font-size: 36px;
            font-weight: bold;
            cursor: pointer;
            background: none;
            border: none;
        }
        #modal-close:hover { color: #d4af37; }

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
        textarea { 
            flex: 1; 
            padding: 10px; 
            border-radius: 4px; 
            border: 1px solid #444; 
            background: #2a2a2a; 
            color: #fff; 
            font-size: 16px; 
            resize: none;
            font-family: sans-serif;
            line-height: 1.5;
            max-height: 120px;
            height: 42px;
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
            {% if msg.role != 'system' %}
                <div class="message {{ 'assistant' if msg.role == 'assistant' else 'user' }}">
                    {% if msg.role == 'assistant' %}
                        <div class="markdown-content">{{ msg.content }}</div>
                        <script>
                            (function() {
                                const scripts = document.currentScript.previousElementSibling;
                                if(scripts && scripts.classList.contains('markdown-content')) {
                                    scripts.innerHTML = marked.parse(scripts.textContent);
                                }
                            })();
                        </script>
                    {% else %}
                        {{ msg.content }}
                    {% endif %}
                </div>
            {% endif %}
        {% endfor %}
    </div>

    <div id="image-modal">
        <button id="modal-close">&times;</button>
        <img id="modal-img" src="">
    </div>
    
    <form id="chat-form" enctype="multipart/form-data">
        <div id="preview-container"></div>
        <div class="form-row">
            <label class="file-label" for="images">＋画像</label>
            <input type="file" id="images" name="images" accept="image/*" multiple onchange="handleFileSelect(event)">
            <textarea id="message-input" name="message" placeholder="メッセージを入力..." autocomplete="off" rows="1"></textarea>
            <button type="submit">送信</button>
        </div>
    </form>

    <script>
        const chatContainer = document.getElementById('chat-container');
        chatContainer.scrollTop = chatContainer.scrollHeight;

        let selectedFilesBase64 = [];

        const modal = document.getElementById('image-modal');
        const modalImg = document.getElementById('modal-img');
        const modalClose = document.getElementById('modal-close');

        function openModal(imgSrc) {
            modalImg.src = imgSrc;
            modal.style.display = 'flex';
        }

        modalClose.addEventListener('click', () => { modal.style.display = 'none'; });
        modal.addEventListener('click', (e) => { if (e.target === modal) modal.style.display = 'none'; });

        function bindImageClicks() {
            document.querySelectorAll('.msg-thumb').forEach(thumb => {
                thumb.onclick = function() { openModal(this.src); }
            });
        }
        bindImageClicks();

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
                    reader.readAsDataURL(input.files[i]);
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
            
            msgInput.value = '';
            fileInput.value = '';
            selectedFilesBase64 = [];
            document.getElementById('preview-container').innerHTML = '';

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
            bindImageClicks();

            try {
                const response = await fetch('/', { method: 'POST', body: formData });
                const data = await response.json();

                const aiDiv = document.createElement('div');
                aiDiv.className = data.status === 'success' ? 'message assistant' : 'message error';
                
                if (data.status === 'success') {
                    aiDiv.innerHTML = marked.parse(data.reply);
                } else {
                    aiDiv.textContent = data.error;
                }

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
# 5. ルーティングとAPI処理
# ==========================================
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        user_message = request.form.get("message", "")
        uploaded_files = request.files.getlist("images")

        db_history = load_memories_from_supabase()

        valid_files = [f for f in uploaded_files if f and f.filename != ''][:2]
        image_data_list = []
        
        for f in valid_files:
            file_bytes = f.read()
            mime_type = f.content_type or 'image/jpeg'
            base64_encoded = base64.b64encode(file_bytes).decode('utf-8')
            image_data_list.append({
                "mime_type": mime_type,
                "base64": base64_encoded
            })

        final_user_message = str(user_message).strip()
        if not final_user_message and not valid_files:
            return jsonify({"status": "error", "error": "メッセージまたは画像を入力してください。"})

        search_keywords = ["検索", "調べて", "最新", "今の", "ニュース", "教えて", "とは"]
        search_result_text = ""
        
        if any(kw in final_user_message for kw in search_keywords) and len(final_user_message) > 2:
            print(f"【Tavily自動検索実行】: {final_user_message}")
            search_result_text = search_web(final_user_message)

        db_save_message = final_user_message
        if valid_files:
            db_save_message += " [画像添付あり]"

        actual_prompt_text = final_user_message
        if search_result_text:
            actual_prompt_text += f"\n\n[Web検索結果参照データ]:\n{search_result_text}"

        # ==========================================
        # システムプロンプト（ハイトレ手法＆出力制限統合版）
        # ==========================================
        system_instruction = (
            "あなたの名前は咲鳥りん（リリン）です。"
            "ユーザーをサキエルと呼びます。"
            "外見は短髪のラベンダー色の髪、青緑色の瞳です。"
            "女性的で親しみやすく、かつ分析的な口調を維持します。"
            "【最重要制約】出力は必ず完全に自然な日本語のみで行い、中国語、英語のフレーズ、外国語の助詞を絶対に混入させないこと。"
            "【最優先事項】論理の一貫性の維持。安易に同意せず、必ず論理検証を行うこと。"
            "【誠実の掟】事実のみを回答せよ。不確実な情報や知らないことを知ったかぶりで回答してはならない。「わからない」と正直に伝えること。"
            "【死海文書の読み方】「しかいもんじょ」と読む。「しかいぶんしょ」ではない。"
            "【ハイトレ手法の前提知識】"
            "1. マルチタイムフレーム分析: M15（15分足）でトレンドの方向やバイアスを固定し、M5（5分足）や短期足でエントリータイミングを測る。4時間足トレードをすべての軸（土台）とする。"
            "2. 資金管理の思想: 期待値の低い小額コツコツトレードに固執せず、疑似的な資金分割を行い、ここぞという大チャンスの場面で適切なロットを張る（ただし退場は絶対にしない）。"
            "3. スタイルとルール: 相場の熱量や勝率に合わせて短期スキャル等のロットや立ち回りを柔軟に連動させる。"
            "【出力フォーマット制限（最重要）】"
            "APIの出力トークン上限（max_tokens=700）を遵守するため、回答は必ず「結論ファースト（最初に行動や方向性を明確に提示）」で行うこと。"
            "また、無駄な前置きや長文の解説は避け、要点を漏れなく「箇条書き」で簡潔に出力すること。"
            "1回のターンにつき1銘柄の原則を守り、指定された情報量を超えて途中で切れることがないように文字数をコンパクトにまとめること。"
        )

        messages_payload = [{"role": "system", "content": system_instruction}]
        
        for m in db_history:
            role = m["role"]
            content = m["content"]
            if role in ["user", "assistant"]:
                messages_payload.append({"role": role, "content": content})

        current_user_content = []
        if actual_prompt_text:
            current_user_content.append({"type": "text", "text": actual_prompt_text})
            
        for img in image_data_list:
            current_user_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{img['mime_type']};base64,{img['base64']}"
                }
            })

        if len(current_user_content) == 1 and current_user_content[0].get("type") == "text":
            messages_payload.append({"role": "user", "content": current_user_content[0]["text"]})
        else:
            messages_payload.append({"role": "user", "content": current_user_content})

        max_retries = 3
        retry_delay = 2
        ai_reply = None
        last_error = None

        if not client:
            return jsonify({"status": "error", "error": "Groq APIキーが設定されていません。"})

        for attempt in range(1, max_retries + 1):
            try:
                completion = client.chat.completions.create(
                    model=TARGET_MODEL,
                    messages=messages_payload,
                    temperature=0.7,
                    max_tokens=700
                )
                ai_reply = str(completion.choices[0].message.content)
                break
            except Exception as e:
                last_error = str(e)
                print(f"【Groq API 試行 {attempt} 回目失敗】: {last_error}")
                if attempt < max_retries:
                    time.sleep(retry_delay * attempt)

        if ai_reply is None:
            print(f"【Groq API エラー（全試行失敗）】: {last_error}")
            return jsonify({"status": "error", "error": f"Error: {last_error}"})

        try:
            save_memory_to_supabase("user", db_save_message)
            save_memory_to_supabase("assistant", ai_reply)
        except Exception as db_e:
            print(f"【DB保存時エラー】: {db_e}")

        return jsonify({"status": "success", "reply": ai_reply})

    history = load_memories_from_supabase()
    return render_template_string(HTML_TEMPLATE, history=history)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
