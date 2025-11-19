from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from keyboards.inline_keyboards import InlineKeyboards
from database.db import Database
from config import Config

router = Router()
db = Database()


class AddParserStates(StatesGroup):
    waiting_for_site = State()
    waiting_for_url = State()
    waiting_for_channel = State()
    waiting_for_filter = State()


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    user_id = message.from_user.id
    if user_id not in Config.ADMIN_IDS:
        await message.answer("❌ Sizda admin huquqlari yo'q. Admin panelga kirish mumkin emas.")
        return
    
    await message.answer(
        "🔧 <b>Admin Panel</b>\n\n"
        "Quyidagi amallardan birini tanlang:",
        reply_markup=InlineKeyboards.admin_menu(),
        parse_mode='HTML'
    )


@router.callback_query(F.data == "back_admin")
async def back_to_admin(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in Config.ADMIN_IDS:
        await callback.answer("❌ Admin huquqlari yo'q!", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🔧 <b>Admin Panel</b>\n\n"
        "Quyidagi amallardan birini tanlang:",
        reply_markup=InlineKeyboards.admin_menu(),
        parse_mode='HTML'
    )
    await callback.answer()


@router.callback_query(F.data == "add_parser")
async def add_parser_start(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if user_id not in Config.ADMIN_IDS:
        await callback.answer("❌ Admin huquqlari yo'q!", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🌐 <b>Sayt tanlang:</b>\n\n"
        "Quyidagi saytlardan birini tanlang:",
        reply_markup=InlineKeyboards.site_selection(),
        parse_mode='HTML'
    )
    await state.set_state(AddParserStates.waiting_for_site)
    await callback.answer()


@router.callback_query(F.data.in_(["site_olx", "site_avtoelon"]))
async def select_site(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if user_id not in Config.ADMIN_IDS:
        await callback.answer("❌ Admin huquqlari yo'q!", show_alert=True)
        return
    
    site_type = 'olx' if callback.data == 'site_olx' else 'avtoelon'
    await state.update_data(site_type=site_type)
    
    site_name = 'OLX.uz' if site_type == 'olx' else 'Avtoelon.uz'
    example_url = 'https://www.olx.uz/transport/legkovye-avtomobili/chevrolet/q-cobalt/?currency=UYE' if site_type == 'olx' else 'https://avtoelon.uz/avto/chevrolet/cobalt/gorod-samarkand/?price[from]=5500&price[to]=11000&year[from]=2013&year[to]=2025&sort_by=add_date-desc'
    
    await callback.message.edit_text(
        f"📎 <b>{site_name} dan URL yuboring:</b>\n\n"
        f"Misol:\n"
        f"<code>{example_url}</code>\n\n"
        f"⚠️ URL to'liq va to'g'ri bo'lishi kerak!",
        reply_markup=InlineKeyboards.cancel(),
        parse_mode='HTML'
    )
    await state.set_state(AddParserStates.waiting_for_url)
    await callback.answer()


@router.message(AddParserStates.waiting_for_url)
async def process_url(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in Config.ADMIN_IDS:
        await message.answer("❌ Admin huquqlari yo'q!")
        await state.clear()
        return
    
    url = message.text.strip()
    data = await state.get_data()
    site_type = data['site_type']
    
    if site_type == 'olx' and not url.startswith('https://www.olx.uz'):
        await message.answer(
            "❌ Noto'g'ri URL!\n\n"
            "URL https://www.olx.uz bilan boshlanishi kerak.",
            reply_markup=InlineKeyboards.cancel()
        )
        return
    elif site_type == 'avtoelon' and not url.startswith('https://avtoelon.uz'):
        await message.answer(
            "❌ Noto'g'ri URL!\n\n"
            "URL https://avtoelon.uz bilan boshlanishi kerak.",
            reply_markup=InlineKeyboards.cancel()
        )
        return
    
    await state.update_data(url=url)
    
    await message.answer(
        "📱 <b>Kanal ID sini kiriting:</b>\n\n"
        "Misol: <code>-1001234567890</code>\n\n"
        "⚠️ Kanal ID -100 bilan boshlanadi!\n"
        "Bot kanalni admin bo'lishi kerak!",
        reply_markup=InlineKeyboards.cancel(),
        parse_mode='HTML'
    )
    await state.set_state(AddParserStates.waiting_for_channel)


@router.message(AddParserStates.waiting_for_channel)
async def process_channel(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in Config.ADMIN_IDS:
        await message.answer("❌ Admin huquqlari yo'q!")
        await state.clear()
        return
    
    channel_id = message.text.strip()
    
    if not channel_id.startswith('-100'):
        await message.answer(
            "❌ Noto'g'ri Kanal ID!\n\n"
            "Kanal ID -100 bilan boshlanishi kerak.\n"
            "Misol: -1001234567890",
            reply_markup=InlineKeyboards.cancel()
        )
        return

    await state.update_data(channel_id=channel_id)
    
    data = await state.get_data()
    url = data['url']
    site_type = data['site_type']
    admin_id = user_id
    
    if site_type == 'avtoelon':
        await message.answer(
            "🔍 <b>Filter so'zlarini kiriting (ixtiyoriy):</b>\n\n"
            "Masalan: <code>3 позиция</code>\n\n"
            "Bu so'zlar title da bo'lmagan e'lonlarni saralaydi.\n"
            "Bo'sh qoldirsangiz, barcha e'lonlar olinadi.",
            reply_markup=InlineKeyboards.cancel(),
            parse_mode='HTML'
        )
        await state.set_state(AddParserStates.waiting_for_filter)
    else:
        parser_id = await db.add_parser(admin_id, url, channel_id, site_type)
        await state.clear()
        await message.answer(
            f"✅ <b>Parser muvaffaqiyatli qo'shildi!</b>\n\n"
            f"🆔 Parser ID: {parser_id}\n"
            f"🔗 URL: {url[:50]}...\n"
            f"📱 Kanal: {channel_id}\n"
            f"🌐 Sayt: OLX.uz\n\n"
            f"Bot har 3 minutda yangi e'lonlarni tekshirib turadi.",
            reply_markup=InlineKeyboards.back_to_admin(),
            parse_mode='HTML'
        )


@router.message(AddParserStates.waiting_for_filter)
async def process_filter(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in Config.ADMIN_IDS:
        await message.answer("❌ Admin huquqlari yo'q!")
        await state.clear()
        return
    
    filter_text = message.text.strip() or None
    
    data = await state.get_data()
    url = data['url']
    admin_id = user_id
    site_type = data['site_type']
    channel_id = data['channel_id']
    
    parser_id = await db.add_parser(admin_id, url, channel_id, site_type, filter_text)
    
    await state.clear()
    
    await message.answer(
        f"✅ <b>Parser muvaffaqiyatli qo'shildi!</b>\n\n"
        f"🆔 Parser ID: {parser_id}\n"
        f"🔗 URL: {url[:50]}...\n"
        f"📱 Kanal: {channel_id}\n"
        f"🌐 Sayt: Avtoelon.uz\n"
        f"🔍 Filter: {filter_text or 'Yoq'}\n\n"
        f"Bot har 3 minutda yangi e'lonlarni tekshirib turadi.",
        reply_markup=InlineKeyboards.back_to_admin(),
        parse_mode='HTML'
    )


@router.callback_query(F.data == "my_parsers")
async def show_parsers(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in Config.ADMIN_IDS:
        await callback.answer("❌ Admin huquqlari yo'q!", show_alert=True)
        return

    parsers = await db.get_all_active_parsers()
    
    if not parsers:
        await callback.message.edit_text(
            "❌ Hozircha parser yo'q.\n\n"
            "Yangi parser qo'shish uchun admin paneldan foydalaning.",
            reply_markup=InlineKeyboards.back_to_admin()
        )
    else:
        text = f"📋 <b>Barcha parserlar</b> ({len(parsers)} ta):\n\n"
        for p in parsers:
            site = 'OLX' if p['site_type'] == 'olx' else 'Avtoelon'
            filter_info = f" | Filter: {p['filter_text']}" if p['filter_text'] else ''
            admin_who_added = f" | Qo'shgan: {p['admin_id']}"
            channel_id = f" | Kanal: {p['channel_id']}"
            text += f"🆔 {p['id']}: {p['url'][:30]}... ({site}){filter_info}{admin_who_added}\n{channel_id}\n"

        text += "\nParser tanlang yoki o'chirish uchun ❌ bosing:"
        
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboards.parsers_list(parsers),
            parse_mode='HTML'
        )
    
    await callback.answer()


@router.callback_query(F.data.startswith("delete_"))
async def delete_parser(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in Config.ADMIN_IDS:
        await callback.answer("❌ Admin huquqlari yo'q!", show_alert=True)
        return
    
    parser_id = int(callback.data.split('_')[1])
    
    await db.delete_parser(parser_id)
    
    await callback.answer("✅ Parser o'chirildi!", show_alert=True)
    
    parsers = await db.get_all_active_parsers()
    
    if not parsers:
        await callback.message.edit_text(
            "❌ Hozircha parser yo'q.\n\n"
            "Yangi parser qo'shish uchun admin paneldan foydalaning.",
            reply_markup=InlineKeyboards.back_to_admin()
        )
    else:
        text = f"📋 <b>Barcha parserlar</b> ({len(parsers)} ta):\n\n"
        for p in parsers:
            site = 'OLX' if p['site_type'] == 'olx' else 'Avtoelon'
            filter_info = f" | Filter: {p['filter_text']}" if p['filter_text'] else ''
            admin_who_added = f" | Qo'shgan: {p['admin_id']}"
            channel_id = f" | Kanal: {p['channel_id']}"
            text += f"🆔 {p['id']}: {p['url'][:30]}... ({site}){filter_info}{admin_who_added}\n{channel_id}\n"
        text += "\nParser tanlang yoki o'chirish uchun ❌ bosing:"
        
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboards.parsers_list(parsers),
            parse_mode='HTML'
        )


@router.callback_query(F.data == "cancel")
async def cancel_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if user_id not in Config.ADMIN_IDS:
        await callback.answer("❌ Admin huquqlari yo'q!", show_alert=True)
        return
    
    await state.clear()
    await callback.message.edit_text(
        "❌ Amal bekor qilindi.",
        reply_markup=InlineKeyboards.back_to_admin()
    )
    await callback.answer()