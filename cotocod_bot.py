import asyncio
import logging
import re
from datetime import datetime, timedelta
from collections import defaultdict
from config import tokens, idd
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.utils import executor
from aiogram.dispatcher.filters import Command

API_TOKEN = tokens
ADMIN_USER_ID = idd

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)


data_store = defaultdict(lambda: {'count': 0, 'total': 0.0})

SUM_PATTERN = re.compile(r"Итоговая сумма:\s*([\d\s,.]+)", re.IGNORECASE)
MANAGER_PATTERN = re.compile(r"Персональный менеджер:\s*([А-Яа-яЁё]+ [А-Яа-яЁё]+)", re.IGNORECASE)

def parse_message(text: str):
    sum_match = SUM_PATTERN.search(text)
    manager_match = MANAGER_PATTERN.search(text)
    if not sum_match or not manager_match:
        return None, None

    raw_sum = sum_match.group(1).replace(" ", "").replace(",", ".")
    try:
        amount = float(raw_sum)
    except ValueError:
        return None, None

    manager = manager_match.group(1).strip()
    return amount, manager

@dp.message_handler(commands=["report"])
async def manual_report(message: Message):
    await send_report(ADMIN_USER_ID)

@dp.message_handler()
async def handle_message(message: Message):
    amount, manager = parse_message(message.text)
    if amount is None or manager is None:
        logging.info("Сообщение не содержит нужных полей или ошибка парсинга.")
        return

    entry = data_store[manager]
    entry['count'] += 1
    entry['total'] += amount
    logging.info(f"Добавлена оплата: {manager}, {amount:.2f}₽")

async def send_report(user_id):
    today = datetime.now().strftime('%d.%m.%Y')
    report_lines = [f"Отчет за {today}\n"]
    total_sum = 0.0

    for manager, stats in data_store.items():
        report_lines.append(f"{manager} - {stats['total']:.0f} ₽")
        total_sum += stats['total']

    if total_sum > 0:
        report_lines.append(f"\nОбщая сумма: {total_sum:.0f} ₽")
        report_text = "\n".join(report_lines)
        await bot.send_message(user_id, report_text)
        logging.info(f"Отчет отправлен пользователю {user_id}")
    else:
        logging.info("Нет данных для отчета.")

    data_store.clear()

async def daily_report_scheduler():
    while True:
        now = datetime.utcnow() + timedelta(hours=3)  # UTC+3 = Москва
        target_time = now.replace(hour=23, minute=59, second=0, microsecond=0)
        if now >= target_time:
            target_time += timedelta(days=1)

        wait_seconds = (target_time - now).total_seconds()
        logging.info(f"Ожидание до 23:59 по МСК: {wait_seconds / 60:.2f} минут")
        await asyncio.sleep(wait_seconds)
        await send_report(ADMIN_USER_ID)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(daily_report_scheduler())
    executor.start_polling(dp, skip_updates=True)
