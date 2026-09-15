import os
import threading
from flask import Flask
import discord
from discord.ext import commands
from groq import Groq
from supabase import create_client, Client

# --- Flask Webサーバー（RenderのWeb Service要件を満たすため） ---
app = Flask(__name__)

@app.route("/")
def home():
    return "Lilin is alive (Forever Memory Active)!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- 環境変数の取得 ---
TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# --- 各種クライアントの初期化 ---
groq_client = Groq(api_key=GROQ_API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- ボットのインテント設定 ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("--- Lilin is ready with Forever Memory ---")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if bot.user.mentioned_in(message):
        user_message = message.content.replace(f"<@{bot.user.id}>", "").strip()
        user_id = str(message.author.id)

        try:
            # 1. Supabaseから過去の記憶（履歴）を取得
            response = supabase.table("memories").select("role, content").eq("user_id", user_id).order("created_at", desc=False).limit(10).execute()
            chat_history = response.data if response.data else []

            # 2. フリーレンのような長期記憶のシステムプロンプト
            messages = [
                {
                    "role": "system",
                    "content": (
                        "あなたは「リリン」という名前のDiscordボットです。"
                        "あなたはエルフであり、何百年、1000年以上生き続ける存在です。"
                        "目の前のユーザーとの思い出や会話の記憶を永遠に忘れず、大切に心に留めています。"
                        "落ち着いた、少しどこか物静かでありながらも温かみのある口調で話してください。"
                    )
                }
            ]

            for chat in chat_history:
                messages.append({"role": chat["role"], "content": chat["content"]})

            messages.append({"role": "user", "content": user_message})

            # 3. Groq APIで返答を生成
            completion = groq_client.chat.completions.create(
                model="llama3-70b-8192",
                messages=messages,
                temperature=0.7,
            )
            reply = completion.choices[0].message.content

            # 4. やり取りをSupabaseに保存（長期記憶の書き込み）
            supabase.table("memories").insert({"user_id": user_id, "role": "user", "content": user_message}).execute()
            supabase.table("memories").insert({"user_id": user_id, "role": "assistant", "content": reply}).execute()

            await message.reply(reply)

        except Exception as e:
            print(f"Error: {e}")
            await message.reply("……少し、記憶の整理に時間がかかっているみたい。もう一度話しかけてくれる？")

    await bot.process_commands(message)

if __name__ == "__main__":
    web_thread = threading.Thread(target=run_web)
    web_thread.daemon = True
    web_thread.start()

    try:
        bot.run(TOKEN)
    except Exception as e:
        print(f"[ERROR] 起動エラー: {e}")
