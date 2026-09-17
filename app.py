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

# トークン消費を抑えつつ動作するモデル
TARGET_MODEL = "openai/gpt-oss-20b"

# ==========================================
# 2. Tavily検索関数
# ==========================================
def search_web(query: str) -> str:
    """Tavily APIを使用してWeb検索を行い、結果をテキストで返す"""
    if not tavily_client:
        return ""
    try:
        response = tavily_client.search(query=query, max_results=2)
        results = response.get("results", [])
        search_summary = ""
        for r in results:
            search_summary += f"- {r.get('title', '')}: {r.get('content', '')[:100]}...\n"
        return search_summary
    except Exception as e:
        print(f"【Tavily検索エラー】: {e}")
        return ""

# ==========================================
# 3. Supabase 側でのデータ入出力・要約（トークン節約型）
# ==========================================
def load_memories_from_supabase() -> list:
    """Supabaseから履歴を読み込むが、送信量を抑えるために直近の数件のみにする"""
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
                raw_content = str(row.get("content", ""))
                if raw_content.startswith("user: "):
                    history.append({"role": "user", "content": raw_content[6:]})
                elif raw_content.startswith("assistant: "):
                    history.append({"role": "assistant", "content": raw_content[11:]})
                elif raw_content.startswith("system: "):
                    history.append({"role": "system", "content": raw_content[8:]})
                    
        # 【トークン節約対策】システム要約 ＋ 直近の会話は「最大2往復（4件）」までに厳しく制限
        system_msgs = [m for m in history if m["role"] == "system"]
        recent_msgs = [m for m in history if m["role"] != "system"][-4:]
        
        return system_msgs + recent_msgs
    except Exception as e:
        print(f"【DB読み込みエラー】: {e}")
        return []

def summarize_and_cleanup_memories():
    """古い履歴をギュッと要約してトークン消費を節約する"""
    if not supabase or not client:
        return
    try:
        response = supabase.table("memories").select("content, created_at").order("created_at", desc=False).execute()
        all_rows = response.data if response.data else []
        
        # 履歴が溜まりすぎたら（例: 8件以上）古いものを要約に圧縮
        if len(all_rows) > 8:
            older_rows = all_rows[:-4]
            recent_rows = all_rows[-4:]
            
            text_to_summarize = "\n".join([r.get("content", "") for r in older_rows])
            
            summary_completion = client.chat.completions.create(
                model=TARGET_MODEL,
                messages=[
                    {"role": "system", "content": "以下の会話の要点を箇条書きで極力短く日本語で要約してください。"},
                    {"role": "user", "content": text_to_summarize}
                ],
                temperature=0.3,
                max_tokens=100
            ]
            summary_text = summary_completion.choices[0].message.content.strip()
            
            # DBをクリアして要約と直近のみ再登録
            supabase.table("memories").delete().neq("content", "___DUMMY___").execute()
            
            supabase.table("memories").insert({
                "content": f"system: 【要約】 {summary_text}"
            }).execute()
            
            for r in recent_rows:
                supabase.table("memories").insert({"content": r.get("content")}).execute()
                
    except Exception as e:
        print(f"【要約処理エラー】: {e}")

def save_memory_to_supabase(role: str, content: str):
    if not supabase:
        return
    try:
        supabase.table("memories").insert({"content": f"{role}: {str(content)}"}).execute()
        summarize_and_cleanup_memories()
    except Exception as e:
        print(f"【DB保存エラー】: {e}")

# ==========================================
# 4. HTML テンプレート
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
        body { background-color: #121212; color: #e0e0e0; font-family: sans-serif; margin: 0; padding: 0; height: 100dvh; display: flex; flex-direction: column; overflow: hidden; }
        header { background: #1f1f1f; padding: 12px; text-align: center; font-weight: bold; border-bottom: 1px solid #333; color: #d4af37; flex-shrink: 0; }
        #chat-container { flex: 1; overflow-y: auto; padding: 15px; display: flex; flex-direction: column; gap: 12px; -webkit-overflow-scrolling: touch; }
        .message { padding: 12px 16px; border-radius: 8px; max-width: 90%; line-height: 1.5; word-break: break-all; white-space: pre-wrap; }
        .message p { margin: 0 0 8px 0; }
        .message p:last-child { margin-bottom: 0; }
        .user { background: #2b3a4a; align-self: flex-end; }
        .assistant { background: #1e1e1e; align-self: flex-start; border: 1px solid #333; }
        .error { background: #4a2b2b; align-self: center; color: #ff8080; }
        .msg-image-container { display: flex; gap: 6px; margin-top: 8px; flex-wrap: wrap; }
        .msg-thumb { width: 80px; height: 80px; border-radius: 4px; object-fit: cover; border: 1px solid #444; cursor: pointer; }
        #image-modal { display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.9); justify-content: center; align-items: center; flex-direction: column; }
        #modal-img { max-width: 90%; max-height: 80vh; object-fit: contain; }
        #modal-close { position: absolute; top: 20px; left: 20px; color: #fff; font-size: 36px; background: none; border: none; cursor: pointer; }
        #preview-container { display: flex; gap: 8px; padding: 0 10px; margin-bottom: 4px; flex-wrap: wrap; }
        .preview-thumb-wrapper { width: 60px; height: 60px; border-radius: 4px; overflow: hidden; border: 1px solid #444; background: #222; }
        .preview-thumb-wrapper img { width: 100%; height: 100%; object-fit: cover; }
        form { background: #1f1f1f; padding: 10px; display: flex; flex-direction: column; border-top: 1px solid #333; flex-shrink: 0; position: sticky; bottom: 0; width: 100%; z-index: 10; }
        .form-row { display: flex; gap: 8px; align-items: center; width: 100%; }
        textarea { flex: 1; padding: 10px; border-radius: 4px; border: 1px solid #444; background: #2a2a2a; color: #fff; font-size: 16px; resize: none; height: 42px; line-height: 1.5; }
        input[type="file"] { display: none; }
        .file-label { background: #333; color: #ccc; padding: 8px 12px; border-radius: 4px; cursor: pointer; font-size: 14px; white-space: nowrap; }
        button[type="submit"] { background: #d4af37; color: #121212; border: none; padding: 10px 16px; border-radius: 4px; font-weight: bold; cursor: pointer; white-space: nowrap; }
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
                                const sc = document.currentScript.previousElementSibling;
                                if(sc && sc.classList.contains('markdown-content')) {
                                    sc.innerHTML = marked.parse(sc.textContent);
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
    <div id="image-modal"><button id="modal-close">&times;</button><img id="modal-img" src=""></div>
    <form id="chat-form" enctype="multipart/form-data">
        <div id="preview-container"></div>
        <div class="form-row">
            <label class="file-label" for="images">＋画像</label>
            <input type="file" id="images" name="images" accept="image/*" multiple onchange="handleFileSelect(event)">
            <textarea id="message-input" name="message" placeholder="メッセージを入力..." rows="1"></textarea>
            <button type="submit">送信</button>
        </div>
    </form>
    <script>
        const chatContainer = document.getElementById('chat-container');
        chatContainer.scrollTop = chatContainer.scrollHeight;
        let selectedFilesBase64 = [];
        const modal = document.getElementById('image-modal');
        const modalImg = document.getElementById('modal-img');
        document.getElementById('modal-close').onclick = () => modal.style.display = 'none';
        
        function bindImageClicks() {
            document.querySelectorAll('.msg-thumb').forEach(t => t.onclick = () => { modalImg.src = t.src; modal.style.display = 'flex'; });
        }
        bindImageClicks();

        function handleFileSelect(event) {
            const input = event.target;
            const pc = document.getElementById('preview-container');
            pc.innerHTML = '';
            selectedFilesBase64 = [];
            if (input.files.length > 0) {
                if (input.files.length > 2) { alert("最大2枚までです。"); input.value = ""; return; }
                for (let i = 0; i < input.files.length; i++) {
                    const reader = new FileReader();
                    reader.onload = (e) => {
                        selectedFilesBase64.push(e.target.result);
                        const w = document.createElement('div'); w.className = 'preview-thumb-wrapper';
                        const img = document.createElement('img'); img.src = e.target.result;
                        w.appendChild(img); pc.appendChild(w);
                    }
                    reader.readAsDataURL(input.files[i]);
                }
            }
        }

        document.getElementById('chat-form').onsubmit = async (e) => {
            e.preventDefault();
            const msgInput = document.getElementById('message-input');
            const fileInput = document.getElementById('images');
            const formData = new FormData();
            formData.append('message', msgInput.value);
            for (let i = 0; i < fileInput.files.length; i++) formData.append('images', fileInput.files[i]);

            const userText = msgInput.value;
            const currentImages = [...selectedFilesBase64];
            msgInput.value = ''; fileInput.value = ''; selectedFilesBase64 = [];
            document.getElementById('preview-container').innerHTML = '';

            const userDiv = document.createElement('div');
            userDiv.className = 'message user';
            userDiv.textContent = userText;
            if (currentImages.length > 0) {
                const ic = document.createElement('div'); ic.className = 'msg-image-container';
                currentImages.forEach(src => {
                    const img = document.createElement('img'); img.className = 'msg-thumb'; img.src = src;
                    ic.appendChild(img);
                });
                userDiv.appendChild(ic);
            }
            chatContainer.appendChild(userDiv);
            chatContainer.scrollTop = chatContainer.scrollHeight;
            bindImageClicks();

            try {
                const res = await fetch('/', { method: 'POST', body: formData });
                const data = await res.json();
                const aiDiv = document.createElement('div');
                aiDiv.className = data.status === 'success' ? 'message assistant' : 'message error';
                aiDiv.innerHTML = data.status === 'success' ? marked.parse(data.reply) : data.error;
                chatContainer.appendChild(aiDiv);
                chatContainer.scrollTop = chatContainer.scrollHeight;
            } catch (err) {
                const errDiv = document.createElement('div');
                errDiv.className = 'message error';
                errDiv.textContent = '通信エラーが発生しました。';
                chatContainer.appendChild(errDiv);
            }
        };
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
            image_data_list.append({
                "mime_type": f.content_type or 'image/jpeg',
                "base64": base64.b64encode(file_bytes).decode('utf-8')
            })

        final_user_message = str(user_message).strip()
        if not final_user_message and not valid_files:
            return jsonify({"status": "error", "error": "メッセージまたは画像を入力してください。"})

        # 必要時のみ検索
        search_result_text = ""
        if any(kw in final_user_message for kw in ["検索", "調べて", "最新", "今の", "ニュース", "教えて"]) and len(final_user_message) > 2:
            search_result_text = search_web(final_user_message)

        db_save_message = final_user_message + (" [画像添付あり]" if valid_files else "")
        actual_prompt_text = final_user_message + (f"\n\n[検索結果]:\n{search_result_text}" if search_result_text else "")

        # システムプロンプト（トークン消費を抑えるため簡潔化しつつペルソナ維持）
        system_instruction = (
            "名前は咲鳥りん（リリン）。ユーザーをサキエルと呼ぶ。"
            "女性的で分析的な口調。必ず自然な日本語のみを使用すること。"
            "【制約】結論ファーストで、要点を箇条書きで簡潔に出力すること（最大出力トークン制限のため長文禁止）。"
        )

        messages_payload = [{"role": "system", "content": system_instruction}]
        for m in db_history:
            if m["role"] in ["user", "assistant", "system"]:
                messages_payload.append({"role": m["role"], "content": m["content"]})

        current_user_content = []
        if actual_prompt_text:
            current_user_content.append({"type": "text", "text": actual_prompt_text})
        for img in image_data_list:
            current_user_content.append({"type": "image_url", "image_url": {"url": f"data:{img['mime_type']};base64,{img['base64']}"}})

        if len(current_user_content) == 1 and current_user_content[0].get("type") == "text":
            messages_payload.append({"role": "user", "content": current_user_content[0]["text"]})
        else:
            messages_payload.append({"role": "user", "content": current_user_content})

        ai_reply = None
        try:
            completion = client.chat.completions.create(
                model=TARGET_MODEL,
                messages=messages_payload,
                temperature=0.7,
                max_tokens=400  # 1回あたりのトークン消費を抑える
            )
            ai_reply = str(completion.choices[0].message.content)
        except Exception as e:
            return jsonify({"status": "error", "error": f"API制限エラー: {str(e)}"})

        save_memory_to_supabase("user", db_save_message)
        save_memory_to_supabase("assistant", ai_reply)

        return jsonify({"status": "success", "reply": ai_reply})

    return render_template_string(HTML_TEMPLATE, history=load_memories_from_supabase())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
