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

USER_URLS = {}

def get_format_keyboard(url_key: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎬 Видео (Лучшее)", callback_data=f"dl_best_{url_key}"),
            InlineKeyboardButton(text="📱 Видео (720p)", callback_data=f"dl_720_{url_key}")
        ],
        [
            InlineKeyboardButton(text="🎵 Аудио (MP3)", callback_data=f"dl_audio_{url_key}")
        ]
    ])

@dp.message(CommandStart())
async def start_cmd(message: Message):
    try:
        await message.delete()
    except:
        pass
    
    welcome_msg = await message.answer(
        "🤖 **Media Downloader v3.5**\n"
        "Отправь ссылку на YouTube или TikTok — всё остальное я сделаю сам."
    )
    # Автоматически стираем приветствие через 10 секунд, чтобы не засорять чат
    await asyncio.sleep(10)
    try:
        await welcome_msg.delete()
    except:
        pass

@dp.message(F.text.startswith(('http://', 'https://')))
async def handle_url(message: Message):
    url = message.text.strip()
    url_key = str(message.from_user.id)
    USER_URLS[url_key] = url
    
    # Стираем сообщение пользователя со ссылкой
    try:
        await message.delete()
    except Exception:
        pass
    
    # Отправляем меню выбора
    menu_msg = await message.answer(
        "⚡️ **Выберите формат загрузки:**",
        reply_markup=get_format_keyboard(url_key)
    )
    # Сохраняем ID сообщения с меню, чтобы потом его удалить
    USER_URLS[f"{url_key}_msg"] = menu_msg.message_id

@dp.callback_query(F.data.startswith("dl_"))
async def process_download(callback: CallbackQuery):
    data_parts = callback.data.split("_", 2)
    mode = data_parts[1]
    url_key = data_parts[2]
    
    url = USER_URLS.get(url_key)
    if not url:
        await callback.message.edit_text("❌ Ссылка устарела. Отправьте её заново.")
        return

    status_msg = await callback.message.edit_text("🔄 **[▒▒▒▒▒▒▒▒▒▒] 0%** — Подготовка к скачиванию...")
    file_path = None

    try:
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
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
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
                title = info.get('title', 'Медиафайл')
                return filename, title

        file_path, video_title = await asyncio.to_thread(download_process)

        if file_path and os.path.exists(file_path):
            safe_title = video_title[:80] if video_title else "Медиафайл"
            
            await status_msg.edit_text("📤 **Отправка файла в чат...**")
            
            if mode == "audio":
                sent_msg = await callback.message.answer_audio(FSInputFile(file_path), caption=f"🎵 {safe_title} | ✨ w1xsent bot")
            else:
                sent_msg = await callback.message.answer_video(FSInputFile(file_path), caption=f"🎬 {safe_title} | ✨ w1xsent bot")
            
            # Удаляем служебное сообщение с прогрессом
            try:
                await status_msg.delete()
            except:
                pass
        else:
            await status_msg.edit_text("❌ Не удалось обработать файл.")

    except Exception as e:
        logging.error(f"Download error: {e}")
        await status_msg.edit_text(f"❌ Ошибка: {str(e)[:120]}")
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
