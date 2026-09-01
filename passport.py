import asyncio
import random
import os
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiohttp import web
from curl_cffi import requests as async_requests

TG_TOKEN = "8821212478:AAE1JD6RXTrnm45xtBhigZgKVfZZBZtf01I"
URL = "https://munich.pasport.org.ua/solutions/e-queue"

# Текст, который появляется ТОЛЬКО когда мест нет
NO_SLOTS_TEXT = "Вибачте, на даний момент всі місця зайняті!"
VALID_MARKER = "Електронна черга"

bot = Bot(token=TG_TOKEN)
dp = Dispatcher()

def init_db():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()

def add_user(user_id: int):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    add_user(message.from_user.id)
    await message.answer(
        "👋 **Мониторинг запущен!**\n\n"
        "Я отслеживаю появление мест на паспорт в Мюнхене 24/7."
    )

async def notify_all_users(text: str):
    users = get_all_users()
    for user_id in users:
        try:
            await bot.send_message(chat_id=user_id, text=text, parse_mode="HTML")
            await asyncio.sleep(0.05)
        except Exception as e:
            print(f"Ошибка отправки {user_id}: {e}")

async def check_website_loop():
    while True:
        try:
            # Маскируемся под настоящую сессию Chrome
            session = async_requests.Session(impersonate="chrome124")
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
                "Cache-Control": "no-cache",
            }

            response = session.get(URL, headers=headers, timeout=20)

            if response.status_code == 200:
                html = response.text
                
                if VALID_MARKER in html:
                    if NO_SLOTS_TEXT not in html:
                        msg = (
                            f"🚨 <b>ПОЯВИЛИСЬ СВОБОДНЫЕ МЕСТА!</b> 🚨\n\n"
                            f"Плашка 'все места заняты' исчезла!\n"
                            f"Срочно переходите: {URL}"
                        )
                        print("СЛОТЫ НАЙДЕНЫ!")
                        await notify_all_users(msg)
                        await asyncio.sleep(300)
                    else:
                        print("Успешная проверка: мест пока нет (200 OK).")
                else:
                    print("Пропуск: Cloudflare выдал капчу.")
            else:
                print(f"Ошибка доступности сайта: статус {response.status_code}")

        except Exception as e:
            print(f"Ошибка запроса: {e}")

        # Рандомная задержка 70-100 сек, чтобы Cloudflare не банил IP за ровный тайминг
        await asyncio.sleep(random.randint(70, 100))

async def handle_ping(request):
    return web.Response(text="OK")

async def start_dummy_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    init_db()
    await start_dummy_server()
    asyncio.create_task(check_website_loop())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
