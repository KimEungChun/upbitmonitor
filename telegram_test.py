import asyncio
from telegram import Bot

# 아까 복사한 Bot Token
TOKEN = "7475326912:AAHdnqpXNyOiSclg56zFvqu3gTq3CDXexXU"
# 아까 찾은 내 Chat ID
CHAT_ID = 7692872494

async def main():
    bot = Bot(token=TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text="🚀 Azure 서버에서 테스트 메시지 보냄!")

if __name__ == "__main__":
    asyncio.run(main())
