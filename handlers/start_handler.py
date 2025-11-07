from asyncio.log import logger
from urllib.parse import urljoin
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

from services.parser_service import ParserService

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "👋 Salom! Men OLX.uz parser botiman.\n\n"
        "📋 Komandalar:\n"
        "/admin - Admin panel\n"
        "/help - Yordam"
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "ℹ️ <b>Bot haqida ma'lumot:</b>\n\n"
        "Bu bot OLX.uz saytidan avtomobil e'lonlarini avtomatik parse qilib, "
        "sizning Telegram kanalingizga yuboradi.\n\n"
        "🔧 <b>Qanday ishlatish:</b>\n"
        "1. /admin - Admin panelni oching\n"
        "2. 'Yangi parser qo'shish' tugmasini bosing\n"
        "3. OLX.uz dan kerakli URL ni yuboring\n"
        "4. Kanal ID sini kiriting (-100 bilan boshlanadi)\n"
        "5. Bot har 3 minutda yangi e'lonlarni kanalingizga yuboradi\n\n"
        "❓ Savol yoki muammo bo'lsa, adminlarga murojaat qiling.",
        parse_mode='HTML'
    )


@router.channel_post(F.text)
async def channel_post_handler(message: Message):
    await message.answer(f"Channel id: {message.chat.id}")

