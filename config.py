import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
    DB_NAME = 'parser_bot.db'
    CHECK_INTERVAL = 20  
    ADMIN_IDS = [7166331865, 415709200]  