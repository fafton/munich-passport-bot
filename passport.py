import asyncio
import os
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiohttp import web
from curl_cffi import requests as async_requests

TG_TOKEN = "8821212478:AAE1JD6RXTrnm45xtBhigZgKVfZZBZtf01I"
URL = "https://munich.pasport.org.ua/solutions/e-queue"
CHECK_INTERVAL = 60
BLOCK_TEXT = "Вибачте, на даний момент всі місця зайняті!"

bot = Bot(token=TG_TOKEN)
dp = Dispatcher()


# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)"
    )
    conn.commit()
    conn.close()


def add_user(user_id: int):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,)
    )
    conn.commit()
    conn.close()


def get_all_users():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]


# --- ТЕЛЕГРАМ БОТ ---
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    add_user(message.from_user.id)
    await message.answer(
        "👋 **Привет!** Вы успешно подписались на мониторинг очереди в Мюнхене.\n\n"
        "Как только слоты откроются, я сразу отправлю вам уведомление."
    )


async def notify_all_users(text: str):
    users = get_all_users()
    for user_id in users:
        try:
            await bot.send_message(
                chat_id=user_id, text=text, parse_mode="HTML"
            )
            await asyncio.sleep(0.05)
        except Exception as e:
            print(
                f"Не удалось отправить сообщение пользователю {user_id}: {e}"
            )


# --- ПРОВЕРКА САЙТА ---
async def check_website_loop():
    while True:
        try:
            session = async_requests.Session(impersonate="chrome120")
            response = session.get(URL, timeout=15)

            if BLOCK_TEXT not in response.text:
                msg = (
                    f"🚨 <b>ПОЯВИЛИСЬ МЕСТА!</b> 🚨\n\n"
                    f"Плашка с надписью о занятых местах исчезла!\n"
                    f"Срочно переходите: {URL}"
                )
                print("Слоты найдены! Запускаем рассылку...")
                await notify_all_users(msg)
                await asyncio.sleep(300)
            else:
                print("Мест нет, ожидаем...")

        except Exception as e:
            print(f"Ошибка проверки: {e}")

        await asyncio.sleep(CHECK_INTERVAL)


# --- ФЕЙКОВЫЙ ВЕБ-СЕРВЕР ДЛЯ RENDER ---
async def handle_ping(request):
    return web.Response(text="Bot is running!")


async def start_dummy_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()


# --- ГЛАВНЫЙ ЗАПУСК ---
async def main():
    init_db()
    await start_dummy_server()
    asyncio.create_task(check_website_loop())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
