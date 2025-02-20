import discord
from discord.ext import commands
from src.config import BOT_TOKEN, CHANNEL_ID


intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await channel.send("ALL INITIALIZED. GPU WORKER IS READY.")
    else:
        print("지정한 채널을 찾을 수 없습니다.")

async def send_message(content: str):
    """
    지정한 채널에 메시지를 전송하는 함수입니다.
    """
    # get_channel은 봇이 on_ready 이후에 준비된 채널 캐시를 기반으로 동작합니다.
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await channel.send(content)
    else:
        print("채널을 찾을 수 없습니다.")

async def run_bot():
    """
    봇을 실행시키는 함수입니다.
    다른 모듈에서 import하여 사용할 수 있습니다.
    """
    return await bot.start(BOT_TOKEN)