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
    # Удаляем команду старт, чтобы не мусорить
    try:
        await message.delete()
    except:
        pass
    
    await message.answer(
        "Привет! Я твой медиа-бот 🤖\n"
        "Отправь мне ссылку на видео из **YouTube** или **TikTok**, и я предложу скачать видео в высоком качестве или чистый MP3!\n"
        "*(Твои сообщения со ссылками будут автоматически удаляться)*"
    )

@dp.message(F.text.startswith(('http://', 'https://')))
async def handle_url(message: Message):
    url = message.text.strip()
    url_key = str(message.from_user.id)
    USER_URLS[url_key] = url
    
    # Пытаемся сразу удалить сообщение пользователя со ссылкой, чтобы не засорять чат
    try:
        await message.delete()
    except Exception:
        pass
    
    # Отправляем меню выбора формата
    await message.answer(
        "🔗 Ссылка принята! Выбери формат файла:",
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

    await callback.message.edit_text("⏳ Загружаю файл с сервера, подожди немного...")
    file_path = None

    try:
        ydl_opts = {
            'outtmpl': 'downloads/%(id)s.%(ext)s',
            'noplaylist': True,
            'quiet': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['mweb', 'web_creator', 'tv']
                },
                'tiktok': {
                    'webpage_download': True,
                }
            },
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
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
                title = info.get('title', 'Медиафайл')
                return filename, title

        file_path, video_title = await asyncio.to_thread(download_process)

        if file_path and os.path.exists(file_path):
            safe_title = video_title[:100] if video_title else "Медиафайл"
            if mode == "audio":
                await callback.message.answer_audio(FSInputFile(file_path), caption=f"🎵 {safe_title}")
            else:
                await callback.message.answer_video(FSInputFile(file_path), caption=f"🎬 {safe_title}")
            
            # Удаляем служебное сообщение бота с кнопками
            try:
                await callback.message.delete()
            except:
                pass
        else:
            await callback.message.edit_text("❌ Не удалось найти или обработать файл.")

    except Exception as e:
        logging.error(f"Download error: {e}")
        await callback.message.edit_text(f"❌ Ошибка скачивания: {str(e)[:140]}")
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
