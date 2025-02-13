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
                "message_id": song["message_id"]
            })

# 📌 **چک کردن پیام‌های جدید و مدیریت دستورات**
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

                            if "text" in message:
                                text = message["text"].strip()
                                if text == "/random":
                                    await send_random_songs(chat_id)

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
