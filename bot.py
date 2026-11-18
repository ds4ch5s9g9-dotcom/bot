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

# Продвинутые параметры для обхода блокировок TikTok и YouTube
def get_ydl_opts(mode):
    ydl_opts = {
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'noplaylist': True,
        'quiet': True,
        'nocheckcertificate': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['ios', 'web_creator'],
            },
            'tiktok': {
                'webpage_download': True,
            }
        },
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Referer': 'https://www.tiktok.com/',
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
    return ydl_opts

USER_URLS = {}

def make_keyboard(unique_id: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎬 Видео (Лучшее)", callback_data=f"dl_best_{unique_id}"),
            InlineKeyboardButton(text="📱 Видео (720p)", callback_data=f"dl_720_{unique_id}")
        ],
        [
            InlineKeyboardButton(text="🎵 Аудио (MP3)", callback_data=f"dl_audio_{unique_id}")
        ]
    ])

@dp.message(CommandStart())
async def start_cmd(message: Message):
    try:
        await message.delete()
    except:
        pass

@dp.message(F.text.startswith(('http://', 'https://')))
async def handle_url(message: Message):
    url = message.text.strip()
    user_id = message.from_user.id
    
    try:
        await message.delete()
    except:
        pass
    
    unique_id = f"{user_id}_{abs(hash(url))}"
    USER_URLS[unique_id] = url
    
    await message.answer(
        "⚡️ **Выберите формат загрузки:**",
        reply_markup=make_keyboard(unique_id)
    )

@dp.callback_query(F.data.startswith("dl_"))
async def process_download(callback: CallbackQuery):
    try:
        parts = callback.data.split("_", 2)
        mode = parts[1]
        unique_id = parts[2]
    except:
        await callback.message.edit_text("❌ Ошибка данных. Отправьте ссылку заново.")
        return

    url = USER_URLS.get(unique_id)
    if not url:
        await callback.message.edit_text("❌ Ссылка не найдена в памяти. Отправьте её ещё раз.")
        return

    status_msg = await callback.message.edit_text("🔄 **[▒▒▒▒▒▒▒▒▒▒] 0%** — Загрузка с сервера...")
    file_path = None

    try:
        ydl_opts = get_ydl_opts(mode)

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
            safe_title = video_title[:80] if video_title else "Медиафайл"
            await status_msg.edit_text("📤 **Отправка файла...**")
            
            if mode == "audio":
                await callback.message.answer_audio(FSInputFile(file_path), caption=f"🎵 {safe_title} | ✨ w1xsent bot")
            else:
                await callback.message.answer_video(FSInputFile(file_path), caption=f"🎬 {safe_title} | ✨ w1xsent bot")
            
            try:
                await status_msg.delete()
            except:
                pass
        else:
            await status_msg.edit_text("❌ Не удалось обработать файл.")

    except Exception as e:
        logging.error(f"Download error: {e}")
        error_text = str(e)
        if "status code 0" in error_text or "not available" in error_text:
            await status_msg.edit_text("❌ TikTok временно ограничил доступ с этого сервера. Попробуйте еще раз через минуту.")
        else:
            await status_msg.edit_text(f"❌ Ошибка: {error_text[:120]}")
    finally:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass

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
