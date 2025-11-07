import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import Config
from handlers import admin_handler, start_handler
from database.db import Database
from services.scheduler_service import SchedulerService

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def main():
    db = Database()
    await db.create_tables()
    
    bot = Bot(token=Config.BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    dp.include_router(start_handler.router)
    dp.include_router(admin_handler.router)
    
    scheduler = SchedulerService(bot, db)
    asyncio.create_task(scheduler.start())
    
    logger.info("Bot ishga tushdi!")
    
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())