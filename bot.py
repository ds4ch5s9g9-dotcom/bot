import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, FSInputFile
import yt_dlp

# Токен бота уже на месте
TOKEN = "9127173006:AAETtxdOLjsSJCwiHsw5vvMNI1NiYPtNHlQ"

dp = Dispatcher()

YDL_OPTIONS = {
    'format': 'best[ext=mp4]/best',
    'outtmpl': 'downloads/%(id)s.%(ext)s',
    'noplaylist': True,
    'quiet': True,
}

@dp.message(CommandStart())
async def start_cmd(message: Message):
    await message.answer(
        "Привет! Я w1xsent loader bot 🤖\n"
        "Я могу скачивать видео из TikTok, YouTube и т.д.\n\n"
        "Попробуй отправить ссылку!"
    )

@dp.message(F.text.startswith(('http://', 'https://')))
async def download_video(message: Message):
    url = message.text.strip()
    msg = await message.answer("⏳ Качаю видео, подожди секунду...")
    os.makedirs('downloads', exist_ok=True)
    file_path = None
    
    try:
        def get_vid():
            with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info)

        file_path = await asyncio.to_thread(get_vid)
        
        if file_path and os.path.exists(file_path):
            await message.answer_video(FSInputFile(file_path))
            await msg.delete()
        else:
            await msg.edit_text("❌ Не получилось найти или скачать файл.")
    except Exception as e:
        await msg.edit_text(f"❌ Ошибка при скачивании: {str(e)[:100]}")
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

async def main():
    bot = Bot(token=TOKEN)
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
