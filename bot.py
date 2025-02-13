import os
import json
import random
import asyncio
import httpx
from datetime import datetime
import pytz
from aiogram import Bot, Dispatcher, types
from aiogram.types import ContentType
from aiogram.utils import executor

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")
JSON_FILE = "songs.json"

if not BOT_TOKEN or not GROUP_ID:
    raise ValueError("❌ متغیرهای محیطی BOT_TOKEN و GROUP_ID تنظیم نشده‌اند!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
IRAN_TZ = pytz.timezone("Asia/Tehran")

EXCLUDED_TOPICS_RANDOM = ["Nostalgic", "Golchin-e Shad-e Irooni"]
EXCLUDED_TOPICS_PROCESSING = ["Database"]
RANDOM_SONG_COUNT = 3  

# 📌 **لود کردن دیتابیس از `songs.json`**
def load_database():
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    return []

# 📌 **ذخیره دیتابیس در `songs.json`**
def save_database(data):
    with open(JSON_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)

song_database = load_database()

# 📌 **بررسی آهنگ تکراری در تاپیک**
def is_duplicate_song(audio, thread_id):
    title = audio.get("title", "نامشخص").lower()
    performer = audio.get("performer", "نامشخص").lower()
    
    for song in song_database:
        if song["title"] == title and song["performer"] == performer and song["thread_id"] == thread_id:
            return True
    return False

# 📌 **دریافت و ذخیره `songs.json` از کاربر**
@dp.message_handler(content_types=ContentType.DOCUMENT)
async def handle_document(message: types.Message):
    document = message.document
    if document.file_name == "songs.json":
        file_path = await bot.get_file(document.file_id)
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path.file_path}"

        async with httpx.AsyncClient() as client:
            response = await client.get(file_url)
            with open(JSON_FILE, "wb") as file:
                file.write(response.content)

        global song_database
        song_database = load_database()
        await message.reply("✅ دیتابیس آپدیت شد و آهنگ‌های جدید اضافه شدند!")

# 📌 **ارسال فایل `songs.json` با `/list`**
@dp.message_handler(commands=['list'])
async def send_song_list(message: types.Message):
    save_database(song_database)
    if os.path.exists(JSON_FILE):
        await message.reply_document(open(JSON_FILE, "rb"))
    else:
        await message.reply("❌ دیتابیس آهنگ‌ها خالی است!")

# 📌 **فوروارد آهنگ‌های جدید بدون کپشن و حذف پیام اصلی**
async def forward_music_without_caption(message, thread_id):
    if thread_id in EXCLUDED_TOPICS_PROCESSING:
        return  

    message_id = message["message_id"]
    audio = message["audio"]

    if is_duplicate_song(audio, thread_id):
        async with httpx.AsyncClient(timeout=20) as client:
            await client.get(f"{BASE_URL}/deleteMessage", params={
                "chat_id": GROUP_ID,
                "message_id": message_id
            })
        return  

    audio_file_id = audio["file_id"]
    audio_title = audio.get("title", "نامشخص").lower()
    audio_performer = audio.get("performer", "نامشخص").lower()

    async with httpx.AsyncClient(timeout=20) as client:
        forward_response = await client.get(f"{BASE_URL}/sendAudio", params={
            "chat_id": GROUP_ID,
            "audio": audio_file_id,
            "message_thread_id": thread_id,
            "caption": ""  
        })
        forward_data = forward_response.json()

        if forward_data.get("ok"):
            new_message_id = forward_data["result"]["message_id"]

            song_database.append({
                "title": audio_title,
                "performer": audio_performer,
                "message_id": new_message_id,
                "thread_id": thread_id
            })
            save_database(song_database)

            await asyncio.sleep(1)
            await client.get(f"{BASE_URL}/deleteMessage", params={
                "chat_id": GROUP_ID,
                "message_id": message_id
            })

# 📌 **ارسال ۳ آهنگ تصادفی با `/random`**
@dp.message_handler(commands=['random'])
async def send_random_songs(message: types.Message):
    if not song_database:
        await message.reply("⚠️ هیچ آهنگی در دیتابیس پیدا نشد!")
        return

    random_songs = random.sample(song_database, min(3, len(song_database)))

    async with httpx.AsyncClient() as client:
        for song in random_songs:
            await client.get(f"{BASE_URL}/copyMessage", params={
                "chat_id": message.chat.id,
                "from_chat_id": GROUP_ID,
                "message_id": song["message_id"],
                "message_thread_id": song["thread_id"]
            })

# 📌 **چک کردن پیام‌های جدید و مدیریت آهنگ‌ها**
async def check_new_messages():
    last_update_id = None
    while True:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(f"{BASE_URL}/getUpdates", params={"offset": last_update_id})
                data = response.json()

                if data.get("ok"):
                    for update in data["result"]:
                        last_update_id = update["update_id"] + 1
                        if "message" in update:
                            message = update["message"]
                            chat_id = message["chat"]["id"]
                            thread_id = message.get("message_thread_id")

                            if "audio" in message and str(chat_id) == GROUP_ID:
                                await forward_music_without_caption(message, thread_id)

        except Exception as e:
            print(f"⚠️ خطا: {e}")
            await asyncio.sleep(5)

        await asyncio.sleep(3)

# 📌 **اجرای ربات**
async def main():
    await bot.send_message(GROUP_ID, "🔥 I'm Ready, brothers!")
    await asyncio.gather(check_new_messages())

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
