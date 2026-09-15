import os
import discord
from discord.ext import commands
from groq import Groq
from supabase import create_client, Client

# 環境変数の取得（Renderに設定した値が自動で読み込まれます）
TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# 各種クライアントの初期化
groq_client = Groq(api_key=GROQ_API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ボットのインテント設定
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("------")

@bot.event
async def on_message(message):
    # ボット自身の発言には反応しない
    if message.author == bot.user:
        return

    # ボットがメンションされた場合にGroqで返答する処理
    if bot.user.mentioned_in(message):
        # メンション部分を除いたテキストを取得
        prompt = message.content.replace(f"<@{bot.user.id}>", "").strip()
        if prompt:
            try:
                # Groq APIへのリクエスト
                chat_completion = groq_client.chat.completions.create(
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    model="llama-3.3-70b-versatile",
                )
                reply = chat_completion.choices[0].message.content
                await message.reply(reply)
            except Exception as e:
                await message.reply(f"エラーが発生しました: {e}")

    await bot.process_commands(message)

# ボットの起動
if TOKEN:
    bot.run(TOKEN)
else:
    print("エラー: DISCORD_BOT_TOKEN が設定されていません。")
