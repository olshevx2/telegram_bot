import asyncio
import logging

from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, BotCommand          # ← добавили BotCommand

from token_data import TOKEN
from recipes_handler import router as recipes_router

main_router = Router()


@main_router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я бот с рецептами 🍳\n\n"
        "Команда:\n"
        "/category_search_random <число> — случайные рецепты в категории"
    )


async def main():
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(main_router)
    dp.include_router(recipes_router)

    await bot.set_my_commands([
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="category_search_random", description="Случайные рецепты в категории"),
    ])
    await bot.set_my_description(
        description="Бот с рецептами из themealdb"
    )

    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())