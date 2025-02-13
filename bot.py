import os
import json
import random
import asyncio
import httpx
from datetime import datetime
import pytz

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")
JSON_FILE = "songs.json"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

if not BOT_TOKEN or not GROUP_ID:
    raise ValueError("❌ متغیرهای محیطی BOT_TOKEN و GROUP_ID تنظیم نشده‌اند!")

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

# 📌 **ارسال فایل `songs.json` در `/list`**
async def send_song_list(chat_id):
    save_database(song_database)
    async with httpx.AsyncClient() as client:
        with open(JSON_FILE, "rb") as file:
            files = {"document": file}
            await client.post(f"{BASE_URL}/sendDocument", params={"chat_id": chat_id}, files=files)

# 📌 **دریافت و ذخیره `songs.json` از کاربر**
async def handle_document(document, chat_id):
    file_path = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{document['file_path']}"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(file_path)
        with open(JSON_FILE, "wb") as file:
            file.write(response.content)

    global song_database
    song_database = load_database()

    await send_message(chat_id, "✅ دیتابیس آپدیت شد و آهنگ‌های جدید اضافه شدند!")

# 📌 **ارسال پیام به تلگرام**
async def send_message(chat_id, text):
    async with httpx.AsyncClient() as client:
        await client.get(f"{BASE_URL}/sendMessage", params={"chat_id": chat_id, "text": text})

# 📌 **فوروارد آهنگ‌های جدید بدون کپشن و حذف پیام اصلی**
async def forward_music_without_caption(message, thread_id):
    if thread_id in EXCLUDED_TOPICS_PROCESSING:
        return  

    message_id = message["message_id"]
    audio = message["audio"]

    if is_duplicate_song(audio, thread_id):
        async with httpx.AsyncClient() as client:
            await client.get(f"{BASE_URL}/deleteMessage", params={
                "chat_id": GROUP_ID,
                "message_id": message_id
            })
        return  

    audio_file_id = audio["file_id"]
    audio_title = audio.get("title", "نامشخص").lower()
    audio_performer = audio.get("performer", "نامشخص").lower()

    async with httpx.AsyncClient() as client:
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
async def send_random_songs(chat_id):
    if not song_database:
        await send_message(chat_id, "⚠️ هیچ آهنگی در دیتابیس پیدا نشد!")
        return

    random_songs = random.sample(song_database, min(3, len(song_database)))

    async with httpx.AsyncClient() as client:
        for song in random_songs:
            await client.get(f"{BASE_URL}/copyMessage", params={
                "chat_id": chat_id,
                "from_chat_id": GROUP_ID,
                "message_id": song["message_id"],
                "message_thread_id": song["thread_id"]
            })

# 📌 **چک کردن پیام‌های جدید و مدیریت آهنگ‌ها**
async def check_new_messages():
    last_update_id = None
    while True:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{BASE_URL}/getUpdates", params={"offset": last_update_id})
                data = response.json()

                if data.get("ok"):
                    for update in data["result"]:
                        last_update_id = update["update_id"] + 1
                        if "message" in update:
                            message = update["message"]
                            chat_id = message["chat"]["id"]
                            thread_id = message.get("message_thread_id")

                            if "document" in message:
                                await handle_document(message["document"], chat_id)

                            elif "text" in message:
                                text = message["text"].strip()
                                if text == "/list":
                                    await send_song_list(chat_id)
                                elif text == "/random":
                                    await send_random_songs(chat_id)

                            elif "audio" in message and str(chat_id) == GROUP_ID:
                                await forward_music_without_caption(message, thread_id)

        except Exception as e:
            print(f"⚠️ خطا: {e}")
            await asyncio.sleep(5)

        await asyncio.sleep(3)

# 📌 **اجرای ربات**
async def main():
    await send_message(GROUP_ID, "🔥 I'm Ready, brothers!")
    await asyncio.gather(check_new_messages())

if __name__ == "__main__":
    asyncio.run(main())
