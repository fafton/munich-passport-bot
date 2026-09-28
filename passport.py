import asyncio
import json
import os
from playwright.async_api import async_playwright
from telegram import Bot

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
USERS_FILE = "users.json"
URL = "https://munich.pasport.org.ua/solutions/e-queue"

bot = Bot(token=TELEGRAM_TOKEN)


# Функция для загрузки списка ID пользователей
def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


# Функция для проверки страницы
async def check_queue():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            await page.goto(URL, wait_until="networkidle", timeout=60000)
            content = await page.content()

            # Если фраза об отсутствии мест пропала — места появились
            if "Наразі всі місця зайняті" not in content:
                return True
            return False
        except Exception as e:
            print(f"Ошибка при проверке страницы: {e}")
            return False
        finally:
            await browser.close()


# Главная функция рассылки
async def main():
    users = load_users()

    # Также можно добавить свой CHAT_ID из секретов по умолчанию, если список пуст
    default_chat_id = os.getenv("CHAT_ID")
    if default_chat_id:
        users.add(int(default_chat_id))

    if not users:
        print("Список подписчиков пуст. Рассылка не требуется.")
        return

    has_slots = await check_queue()

    if has_slots:
        message = (
            f"🚨 **Появились свободные места в очереди!**\n\nБыстрее переходи по ссылке:\n{URL}"
        )
        print(f"Места найдены! Отправка уведомления {len(users)} пользователям...")

        # Рассылка всем сохраненным пользователям
        for user_id in users:
            try:
                await bot.send_message(
                    chat_id=user_id, text=message, parse_mode="Markdown"
                )
                print(f"[+] Сообщение отправлено пользователью: {user_id}")
            except Exception as e:
                print(f"[!] Не удалось отправить пользователю {user_id}: {e}")
    else:
        print("Мест нет. Проверка завершена.")


if __name__ == "__main__":
    asyncio.run(main())
