import asyncio
import os
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiohttp import web
from curl_cffi import requests as async_requests

TG_TOKEN = "8821212478:AAE1JD6RXTrnm45xtBhigZgKVfZZBZtf01I"
URL_PAGE = "https://munich.pasport.org.ua/solutions/e-queue"
URL_API = "https://munich.pasport.org.ua/api/qms/services/1/dates"  # AJAX-эндпоинт для паспорта
CHECK_INTERVAL = 60

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
        "👋 **Привет!** Вы подписаны на мониторинг слотов (Паспорт/ID) в Мюнхене.\n\n"
        "Бот проверяет наличие свободных дат напрямую через API услуги."
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
            print(f"Ошибка отправки {user_id}: {e}")


# --- ПРОВЕРКА СЛОТОВ ---
async def check_website_loop():
    while True:
        try:
            session = async_requests.Session(impersonate="chrome120")

            # 1. Загружаем токен и сессионные куки
            res_page = session.get(URL_PAGE, timeout=15)

            # 2. Делаем прямой AJAX запрос с выбором услуги
            headers = {
                "X-Requested-With": "XMLHttpRequest",
                "Referer": URL_PAGE,
            }
            res_api = session.get(URL_API, headers=headers, timeout=15)

            # Проверяем ответ: если пришел список дат, а не пустой массив/ошибка
            if res_api.status_code == 200:
                data_str = res_api.text
                if (
                    "[]" not in data_str
                    and "null" not in data_str
                    and len(data_str) > 10
                ):
                    msg = (
                        f"🚨 <b>ПОЯВИЛИСЬ СВОБОДНЫЕ СЛОТЫ!</b> 🚨\n\n"
                        f"Открылась запись на Паспорт / ID-карту!\n"
                        f"Срочно заходите: {URL_PAGE}"
                    )
                    print("СЛОТЫ НАЙДЕНЫ! Отправка уведомлений...")
                    await notify_all_users(msg)
                    await asyncio.sleep(300)
                else:
                    print("Проверка выполнена: доступных дат нет.")
            else:
                print(f"Защита Cloudflare или ошибка API: {res_api.status_code}")

        except Exception as e:
            print(f"Ошибка соединения: {e}")

        await asyncio.sleep(CHECK_INTERVAL)


# --- ФИКТИВНЫЙ СЕРВЕР ДЛЯ УДОВЛЕТВОРЕНИЯ RENDER ---
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
