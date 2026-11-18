import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import yt_dlp
from aiohttp import web
from config import TOKEN

dp = Dispatcher()
os.makedirs('downloads', exist_ok=True)

# Словарь для временного хранения ссылок пользователей
USER_URLS = {}

# Клавиатура выбора формата
def get_format_keyboard(url_key: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎬 Видео (Лучшее)", callback_data=f"dl_best_{url_key}"),
            InlineKeyboardButton(text="📱 Видео (720p)", callback_data=f"dl_720_{url_key}")
        ],
        [
            InlineKeyboardButton(text="🎵 Только аудио (MP3)", callback_data=f"dl_audio_{url_key}")
        ]
    ])

@dp.message(CommandStart())
async def start_cmd(message: Message):
    await message.answer(
        "Привет! Я w1xsent loader bot 🤖\n"
        "Отправь мне ссылку на видео из YouTube или TikTok, и я предложу выбрать качество или скачать только звук!"
    )

@dp.message(F.text.startswith(('http://', 'https://')))
async def handle_url(message: Message):
    url = message.text.strip()
    url_key = str(message.from_user.id)
    USER_URLS[url_key] = url
    
    await message.answer(
        "🔗 Ссылка принята! Что именно нужно сделать?",
        reply_markup=get_format_keyboard(url_key)
    )

@dp.callback_query(F.data.startswith("dl_"))
async def process_download(callback: CallbackQuery):
    data_parts = callback.data.split("_", 2)
    mode = data_parts[1] # best, 720, audio
    url_key = data_parts[2]
    
    url = USER_URLS.get(url_key)
    if not url:
        await callback.message.edit_text("❌ Ссылка устарела или не найдена. Отправь её заново.")
        return

    await callback.message.edit_text("⏳ Загружаю файл, подожди немного...")
    file_path = None

    try:
        ydl_opts = {
            'outtmpl': 'downloads/%(id)s.%(ext)s',
            'noplaylist': True,
            'quiet': True,
            'extractor_args': {
                'youtube': {'player_client': ['ios', 'web']},
                'tiktok': {'webpage_download': True}
            },
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9',
            }
        }

        if mode == "best":
            ydl_opts['format'] = 'best'
        elif mode == "720":
            ydl_opts['format'] = 'bestvideo[height<=720]+bestaudio/best[height<=720] / best'
        elif mode == "audio":
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]

        def download_process():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                if mode == "audio":
                    filename = os.path.splitext(filename)[0] + ".mp3"
                return filename

        file_path = await asyncio.to_thread(download_process)

        if file_path and os.path.exists(file_path):
            if mode == "audio":
                await callback.message.answer_audio(FSInputFile(file_path))
            else:
                await callback.message.answer_video(FSInputFile(file_path))
            await callback.message.delete()
        else:
            await callback.message.edit_text("❌ Не удалось найти или обработать файл.")

    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка скачивания: {str(e)[:150]}")
    finally:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass

# Веб-сервер для удержания порта на Render и работы с UptimeRobot
async def handle(request):
    return web.Response(text="Bot is running 24/7!")

async def web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    bot = Bot(token=TOKEN)
    await web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
