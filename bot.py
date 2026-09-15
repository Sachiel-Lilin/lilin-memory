import os
import threading
from flask import Flask
import discord
from discord.ext import commands
from groq import Groq
from supabase import create_client, Client

# --- 超シンプルなFlask Webサーバー ---
app = Flask(__name__)

@app.route("/")
def home():
    return "Lilin is alive!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# --- 環境変数の取得 ---
TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

groq_client = Groq(api_key=GROQ_API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if bot.user.mentioned_in(message):
        user_message = message.content.replace(f"<@{bot.user.id}>", "").strip()
        user_id = str(message.author.id)

        try:
            response = supabase.table("memories").select("role, content").eq("user_id", user_id).order("created_at", desc=False).limit(10).execute()
            chat_history = response.data if response.data else []

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

            completion = groq_client.chat.completions.create(
                model="llama3-70b-8192",
                messages=messages,
                temperature=0.7,
            )
            reply = completion.choices[0].message.content

            supabase.table("memories").insert({"user_id": user_id, "role": "user", "content": user_message}).execute()
            supabase.table("memories").insert({"user_id": user_id, "role": "assistant", "content": reply}).execute()

            await message.reply(reply)

        except Exception as e:
            print(f"Error: {e}")
            await message.reply("……少し、記憶の整理に時間がかかっているみたい。")

    await bot.process_commands(message)

if __name__ == "__main__":
    # Webサーバーを別スレッドで走らせる
    web_thread = threading.Thread(target=run_web)
    web_thread.daemon = True
    web_thread.start()

    # Discordボットを起動
    bot.run(TOKEN)
