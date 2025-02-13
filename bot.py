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

# 📌 **ارسال پیام به تلگرام**
async def send_message(chat_id, text):
    async with httpx.AsyncClient() as client:
        await client.get(f"{BASE_URL}/sendMessage", params={"chat_id": chat_id, "text": text})

# 📌 **حذف آهنگ‌های خراب از دیتابیس**
def remove_invalid_songs():
    global song_database
    valid_songs = []
    for song in song_database:
        if song.get("message_id") and song.get("thread_id"):
            valid_songs.append(song)
    song_database = valid_songs
    save_database(song_database)

# 📌 **بررسی دسترسی به پیام قبل از فوروارد**
async def can_forward_message(song):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/copyMessage", params={
            "chat_id": GROUP_ID,
            "from_chat_id": GROUP_ID,
            "message_id": song["message_id"],
            "message_thread_id": song["thread_id"]
        })
        data = response.json()
        if not data.get("ok"):  # پیام مشکل داره
            return False
        return True

# 📌 **ارسال ۳ آهنگ تصادفی با `/random`**
async def send_random_songs(chat_id):
    global song_database  
    if not song_database:
        await send_message(chat_id, "⚠️ هیچ آهنگی در دیتابیس پیدا نشد!")
        return

    random.shuffle(song_database)
    valid_songs = []

    async with httpx.AsyncClient() as client:
        for song in song_database:
            if await can_forward_message(song):
                valid_songs.append(song)
            else:
                print(f"❌ حذف پیام غیرقابل فوروارد: {song['message_id']}")
                song_database.remove(song)

            if len(valid_songs) >= RANDOM_SONG_COUNT:
                break

        save_database(song_database)  # ذخیره دیتابیس بعد از حذف پیام‌های خراب

        for song in valid_songs:
            await client.get(f"{BASE_URL}/copyMessage", params={
                "chat_id": chat_id,
                "from_chat_id": GROUP_ID,
                "message_id": song["message_id"],
                "message_thread_id": song["thread_id"]
            })

# 📌 **اجرای ربات**
async def main():
    await send_message(GROUP_ID, "🔥 I'm Ready, brothers!")
    await asyncio.gather(send_random_songs(GROUP_ID))

if __name__ == "__main__":
    asyncio.run(main())
