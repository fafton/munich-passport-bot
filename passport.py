import asyncio
import json
import os
from playwright.async_api import async_playwright
from telegram import Bot

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
USERS_FILE = "users.json"
URL = "https://munich.pasport.org.ua/solutions/e-queue"

bot = Bot(token=TELEGRAM_TOKEN)


def load_users():
    users = set()
    if CHAT_ID:
        users.add(int(CHAT_ID))
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r") as f:
                data = json.load(f)
                for u in data:
                    users.add(int(u))
        except Exception:
            pass
    return users


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
            # 1. Переходим на страницу записи
            await page.goto(URL, wait_until="networkidle", timeout=60000)
            await page.wait_for_timeout(3000)

            # 2. Нажимаем на выбор услуги (выпадающее меню или карточку)
            # Пытаемся кликнуть по элементу с текстом "Закордонний" или открывающему меню
            try:
                # Нажимаем на селект/меню выбора услуги, если оно есть
                select_element = page.locator("text=Оберіть послугу").or_(
                    page.locator("text=Виберіть послугу")
                )
                if await select_element.count() > 0:
                    await select_element.first.click()
                    await page.wait_for_timeout(1000)

                # Нажимаем на саму услугу "Закордонний паспорт"
                passport_option = page.locator(
                    "text=/Закордонний/i"
                ).or_(
                    page.locator("text=/паспорт для виїзду/i")
                )
                if await passport_option.count() > 0:
                    await passport_option.first.click()
                    print("[+] Выбрана услуга оформления загранпаспорта.")
            except Exception as select_err:
                print(f"[!] Не удалось кликнуть по меню, проверяем текущее состояние: {select_err}")

            # 3. Ждем 4 секунды подгрузку ответа о наличии мест
            await page.wait_for_timeout(4000)

            # 4. Считываем видимый текст страницы
            text = await page.inner_text("body")

            # Проверяем, есть ли фраза про отсутствие мест
            if "Наразі всі місця зайняті" not in text and "вибачте" not in text.lower():
                print("[+] Места появились!")
                return True
            else:
                print("[-] Мест нет (выдает сообщение о том, что все места заняты).")
                return False

        except Exception as e:
            print(f"Ошибка при проверке страницы: {e}")
            return False
        finally:
            await browser.close()


async def main():
    users = load_users()
    if not users:
        print("Нет пользователей для отправки.")
        return

    has_slots = await check_queue()

    if has_slots:
        message = (
            f"🚨 **Появились свободные места на Загранпаспорт!**\n\nБыстрее переходи по ссылке:\n{URL}"
        )
        for user_id in users:
            try:
                await bot.send_message(
                    chat_id=user_id, text=message, parse_mode="Markdown"
                )
                print(f"Уведомление отправлено: {user_id}")
            except Exception as e:
                print(f"Ошибка отправки {user_id}: {e}")


if __name__ == "__main__":
    asyncio.run(main())
