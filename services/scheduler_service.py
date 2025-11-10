import asyncio
import logging
from typing import Dict, List, Optional
from aiogram import Bot
from aiogram.types import InputMediaPhoto
from database.db import Database
from services.parser_service import ParserService
from config import Config

logger = logging.getLogger(__name__)

class SchedulerService:
   
    def __init__(self, bot: Bot, db: Database):
        self.bot = bot
        self.db = db
        self.parser_service = ParserService()
        self.is_running = False
   
    async def start(self):
        self.is_running = True
       
        while self.is_running:
            try:
                await self.check_all_parsers()
            except Exception as e:
                logger.error(f"Scheduler xatosi: {e}")
           
            # 3 minut kutish
            await asyncio.sleep(Config.CHECK_INTERVAL)
   
    async def check_all_parsers(self):
        parsers = await self.db.get_all_active_parsers()
       
        for parser in parsers:
            try:
                await self.check_parser(parser)
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"Parser {parser.get('id')} xatosi: {e}")
   
    async def find_last_seen_ad(self, parser_id: int, hrefs: List[str], check_limit: int = 10) -> Optional[int]:
        """
        Berilgan hrefs ro'yxatida avval yuborilgan elonni topadi.
        Topilgan elonning indeksini qaytaradi, yoki None.
        """
        check_hrefs = hrefs[:min(check_limit, len(hrefs))]
        
        for i, href in enumerate(check_hrefs):
            is_parsed = await self.db.is_ad_parsed(parser_id, href)
            if is_parsed:
                logger.info(f"Parser {parser_id}: Avval yuborilgan elon topildi index {i}: {href}")
                return i
        
        return None
   
    async def check_parser(self, parser: dict):
        parser_id = parser['id']
        url = parser['url']
        channel_id = parser['channel_id']
        site_type = parser['site_type']
        filter_text = parser['filter_text']
       
        current_hrefs = await self.parser_service.get_listings(url, site_type, filter_text)
       
        if not current_hrefs:
            logger.info(f"Parser {parser_id}: Hech qanday elon topilmadi.")
            return
        
        logger.info(f"Parser {parser_id}: Joriy hrefs soni: {len(current_hrefs)}")
       
        last_known_href = await self.db.get_last_known_href(parser_id)
        logger.info(f"Parser {parser_id}: Bookmark: {last_known_href}")
       
        # Birinchi ish: faqat eng yangi elonni yuborish
        if last_known_href is None:
            if current_hrefs:
                bookmark_href = current_hrefs[0]
                await self.db.set_last_known_href(parser_id, bookmark_href)
                logger.info(f"Birinchi ish: Bookmark o'rnatildi - {bookmark_href}")
               
                new_hrefs = [current_hrefs[0]]
               
                for href in new_hrefs:
                    try:
                        logger.info(f"E'lon yuklanmoqda (birinchi ish): {href}")
                        details = await self.parser_service.get_ad_details(href, site_type)
                       
                        if details:
                            await self.send_to_channel(channel_id, details, site_type)
                            await self.db.add_parsed_ad(parser_id, href)
                            logger.info(f"✅ Yuborildi (birinchi ish): {href}")
                            await asyncio.sleep(3)
                        else:
                            logger.warning(f"E'lon tafsilotlari olinmadi: {href}")
                           
                    except Exception as e:
                        logger.error(f"E'lon yuborishda xato {href}: {e}")
                        continue
               
            return
       
        # Bookmark ni topishga urinish
        new_hrefs = []
        bookmark_index = None
        
        for i, href in enumerate(current_hrefs):
            if href == last_known_href:
                bookmark_index = i
                logger.info(f"Bookmark topildi index {i}: {href}")
                break
            new_hrefs.append(href)
            
            # Xavfsizlik: juda ko'p elon bo'lsa to'xtatish
            if len(new_hrefs) >= 50:
                logger.warning(f"Parser {parser_id}: 50 ta yangi elonga yetdik, to'xtatamiz")
                break
       
        # Agar bookmark topilmasa
        if bookmark_index is None:
            logger.warning(f"Parser {parser_id}: Bookmark topilmadi! Avval yuborilgan elonni qidiramiz...")
            
            # Eng yangi 10 ta elondan avval yuborilganini topish
            last_seen_index = await self.find_last_seen_ad(parser_id, current_hrefs, check_limit=10)
            
            if last_seen_index is not None:
                # Topildi! Faqat shu elondan yuqoridagilarni yuborish
                new_hrefs = current_hrefs[:last_seen_index]
                logger.info(f"Parser {parser_id}: Avval yuborilgan elon index {last_seen_index}da topildi. Yangi elonlar: {len(new_hrefs)} ta")
            else:
                # Hech narsa topilmadi - ehtiyot chorasi: faqat eng yangi 3 ta elonni yuborish
                max_safe_count = 3
                new_hrefs = current_hrefs[:max_safe_count]
                logger.warning(f"Parser {parser_id}: Hech qanday avval yuborilgan elon topilmadi. Xavfsizlik uchun faqat {max_safe_count} ta eng yangi elonni yuboramiz")
        
        if not new_hrefs:
            logger.info(f"Parser {parser_id}: Yangi elon yo'q.")
            return
       
        logger.info(f"Parser {parser_id}: {len(new_hrefs)} ta yangi elon topildi")
       
        # Yangi elonlarni yuborish (eng yangi birinchi)
        sent_count = 0
        for href in new_hrefs:
            try:
                details = await self.parser_service.get_ad_details(href, site_type)
               
                if details:
                    await self.send_to_channel(channel_id, details, site_type)
                    await self.db.add_parsed_ad(parser_id, href)
                    sent_count += 1
                    logger.info(f"✅ Yuborildi ({sent_count}/{len(new_hrefs)}): {href}")
                    await asyncio.sleep(3)
                else:
                    logger.warning(f"E'lon tafsilotlari olinmadi: {href}")
                   
            except Exception as e:
                logger.error(f"E'lon yuborishda xato {href}: {e}")
                continue
       
        # Bookmark ni yangilash: eng yangi elonga
        if current_hrefs:
            new_bookmark = current_hrefs[0]
            await self.db.set_last_known_href(parser_id, new_bookmark)
            logger.info(f"Bookmark yangilandi: {new_bookmark}")
   
    async def send_to_channel(self, channel_id: str, details: Dict, site_type: str = 'olx'):
        try:
            message = self.parser_service.format_message(details, site_type)
            images = details.get('images', [])
            
            if not images:
                await self.bot.send_message(
                    chat_id=channel_id,
                    text=message,
                    parse_mode='HTML',
                    disable_web_page_preview=False
                )
            elif len(images) == 1:
                await self.bot.send_photo(
                    chat_id=channel_id,
                    photo=images[0],
                    caption=message,
                    parse_mode='HTML'
                )
            else:
                media_group = []
                for i, img_url in enumerate(images[:10]):
                    try:
                        if i == 0:
                            media_group.append(
                                InputMediaPhoto(media=img_url, caption=message, parse_mode='HTML')
                            )
                        else:
                            media_group.append(InputMediaPhoto(media=img_url))
                    except Exception as e:
                        logger.error(f"Rasm qo'shishda xato: {e}")
                        continue
               
                if media_group:
                    await self.bot.send_media_group(
                        chat_id=channel_id,
                        media=media_group
                    )
                else:
                    logger.warning("Media group yaratilmadi, oddiy xabar yuborilmoqda")
                    await self.bot.send_message(
                        chat_id=channel_id,
                        text=message,
                        parse_mode='HTML',
                        disable_web_page_preview=False
                    )
           
        except Exception as e:
            logger.error(f"Channelga yuborishda xato: {e}")
   
    def stop(self):
        self.is_running = False
        logger.info("Scheduler to'xtatildi")