# main.py
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.fsm.storage.redis import RedisStorage
import os
import asyncio
from config import BOT_TOKEN
from handlers import register_handlers

async def main():
    bot = Bot(token=BOT_TOKEN)
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", 6379))
    redis_db = int(os.getenv("REDIS_DB", 0))
    storage = RedisStorage.from_url(f"redis://{redis_host}:{redis_port}/{redis_db}")
    dp = Dispatcher(storage=storage)
    register_handlers(dp)
    print("Бот работает с Redis FSM!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
