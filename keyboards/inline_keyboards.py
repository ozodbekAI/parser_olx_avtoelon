from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Dict


class InlineKeyboards:
    
    @staticmethod
    def admin_menu() -> InlineKeyboardMarkup:
        buttons = [
            [InlineKeyboardButton(text="➕ Yangi parser qo'shish", callback_data='add_parser')],
            [InlineKeyboardButton(text="📋 Mening parserlarim", callback_data='my_parsers')],
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    @staticmethod
    def site_selection() -> InlineKeyboardMarkup:
        buttons = [
            [InlineKeyboardButton(text="🌐 OLX.uz", callback_data='site_olx')],
            [InlineKeyboardButton(text="🚗 Avtoelon.uz", callback_data='site_avtoelon')],
        ]
        buttons.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data='cancel')])
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    @staticmethod
    def parsers_list(parsers: List[Dict]) -> InlineKeyboardMarkup:
        buttons = []
        
        for parser in parsers:
            url = parser['url']
            try:
                short_name = url.split('/')[-2][:30]
            except:
                short_name = f"Parser {parser['id']}"
            
            site = 'OLX' if parser['site_type'] == 'olx' else 'Avtoelon'
            buttons.append([
                InlineKeyboardButton(
                    text=f"🔗 {short_name} ({site})",
                    callback_data=f"view_{parser['id']}"
                ),
                InlineKeyboardButton(
                    text="❌",
                    callback_data=f"delete_{parser['id']}"
                )
            ])
        
        if not buttons:
            buttons.append([InlineKeyboardButton(text="❌ Parserlar yo'q", callback_data='none')])
        
        buttons.append([InlineKeyboardButton(text="◀️ Orqaga", callback_data='back_admin')])
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    @staticmethod
    def back_to_admin() -> InlineKeyboardMarkup:
        buttons = [[InlineKeyboardButton(text="◀️ Admin panel", callback_data='back_admin')]]
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    @staticmethod
    def cancel() -> InlineKeyboardMarkup:
        buttons = [[InlineKeyboardButton(text="❌ Bekor qilish", callback_data='cancel')]]
        return InlineKeyboardMarkup(inline_keyboard=buttons)