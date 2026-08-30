import asyncio
import os
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiohttp import web
from curl_cffi import requests as async_requests

TG_TOKEN = "8821212478:AAE1JD6RXTrnm45xtBhigZgKVfZZBZtf01I"
# Прямой URL страницы записи
URL = "https://munich.pasport.org.ua/solutions/e-queue"
CHECK_INTERVAL = 60

# Текст, который появляется, если после выбора услуги мест НЕТ
NO_SLOTS_TEXT = "Вибачте, на даний момент всі місця зайняті!"
# Маркер успешного ответа сайта
VALID_MARKER = "Електронна черга"

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
        "👋 **Привет!** Вы подписались на мониторинг свободных слотов в Мюнхене.\n\n"
        "Я запрашиваю наличие мест с выбранной услугой и пришлю уведомление, как только откроется запись!"
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
            print(f"Ошибка отправки пользователю {user_id}: {e}")


# --- ПРОВЕРКА НАЛИЧИЯ МЕСТ ---
async def check_website_loop():
    while True:
        try:
            session = async_requests.Session(impersonate="chrome120")

            # 1. Запрашиваем страницу
            response = session.get(URL, timeout=15)
            html = response.text

            # 2. Проверяем, что ответ не заблокирован Cloudflare
            if VALID_MARKER not in html:
                print("Сайт временно выдал защиту Cloudflare. Пропускаем...")
            else:
                # 3. Если плашка с текстом "все места заняты" отсутствует в HTML — значит слоты доступны
                if NO_SLOTS_TEXT not in html:
                    msg = (
                        f"🚨 <b>ПОЯВИЛИСЬ СВОБОДНЫЕ МЕСТА!</b> 🚨\n\n"
                        f"Форма с выбором даты и времени доступна!\n"
                        f"Срочно переходите и регистрируйтесь: {URL}"
                    )
                    print(
                        "МЕСТА НАЙДЕНЫ! Отправляем уведомления подписчикам..."
                    )
                    await notify_all_users(msg)
                    # Пауза 5 минут после обнаружения, чтобы не спамить
                    await asyncio.sleep(300)
                else:
                    print("Проверка выполнена: мест для записи нет.")

        except Exception as e:
            print(f"Ошибка запроса к сайту: {e}")

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
