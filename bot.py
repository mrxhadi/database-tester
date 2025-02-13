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
        print(f"📤 ارسال پیام به {chat_id}: {text}")
        await client.get(f"{BASE_URL}/sendMessage", params={"chat_id": chat_id, "text": text})

# 📌 **ارسال ۳ آهنگ تصادفی با `/random`**
async def send_random_songs(chat_id):
    global song_database  
    print(f"🔍 دریافت دستور /random از {chat_id}")

    if not song_database:
        print("⚠️ دیتابیس خالی است!")
        await send_message(chat_id, "⚠️ هیچ آهنگی در دیتابیس پیدا نشد!")
        return

    print(f"🎶 تعداد آهنگ‌های موجود در دیتابیس: {len(song_database)}")
    random.shuffle(song_database)
    valid_songs = random.sample(song_database, min(RANDOM_SONG_COUNT, len(song_database)))

    async with httpx.AsyncClient() as client:
        for song in valid_songs:
            print(f"📤 ارسال آهنگ {song['message_id']} از تاپیک {song['thread_id']}")
            response = await client.get(f"{BASE_URL}/copyMessage", params={
                "chat_id": chat_id,
                "from_chat_id": GROUP_ID,
                "message_id": song["message_id"],
                "message_thread_id": song["thread_id"]  
            })
            print(f"✅ نتیجه ارسال: {response.json()}")

# 📌 **دریافت و ذخیره `songs.json` از کاربر**
async def handle_document(document, chat_id):
    global song_database  
    print(f"📥 دریافت فایل {document['file_name']} از {chat_id}")

    file_id = document["file_id"]  
    async with httpx.AsyncClient() as client:
        file_info = await client.get(f"{BASE_URL}/getFile", params={"file_id": file_id})
        file_info_data = file_info.json()

        if not file_info_data.get("ok"):
            await send_message(chat_id, "❌ خطا در دریافت فایل از سرور تلگرام!")
            return

        file_path = file_info_data["result"]["file_path"]
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

        response = await client.get(file_url)
        with open(JSON_FILE, "wb") as file:
            file.write(response.content)

    song_database = load_database()  

    print(f"✅ دیتابیس با {len(song_database)} آهنگ آپدیت شد!")
    await send_message(chat_id, "✅ دیتابیس آپدیت شد و آهنگ‌های جدید اضافه شدند!")

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

                            # 📥 **پردازش فایل `songs.json` حتی در پیوی**
                            if "document" in message:
                                doc = message["document"]
                                if doc["file_name"] == "songs.json":
                                    await handle_document(doc, chat_id)

                            # 📌 **بررسی دستورات متنی**
                            elif "text" in message:
                                text = message["text"].strip()
                                print(f"📩 دریافت پیام متنی: {text}")
                                if text == "/random":
                                    await send_random_songs(chat_id)

        except Exception as e:
            print(f"⚠️ خطا در `check_new_messages()`: {e}")
            await asyncio.sleep(5)

        await asyncio.sleep(3)

# 📌 **اجرای ربات**
async def main():
    await send_message(GROUP_ID, "🔥 I'm Ready, brothers!")
    await asyncio.gather(check_new_messages())

if __name__ == "__main__":
    asyncio.run(main())
