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
            logger.info(f"Parser {parser_id}: Hech qanday e'lon topilmadi.")
            return

        logger.info(f"Parser {parser_id}: Joriy hreflar soni: {len(current_hrefs)}")

        last_known_href = await self.db.get_last_known_href(parser_id)
        logger.info(f"Parser {parser_id}: Bookmark (diagnostika): {last_known_href}")

        new_hrefs: List[str] = []

        MAX_NEW = 50              
        MAX_CONSEC_OLD = 5     
        consec_old = 0

        for href in current_hrefs:
            try:
                is_parsed = await self.db.is_ad_parsed(parser_id, href)
            except Exception as e:
                logger.error(f"Parser {parser_id}: is_ad_parsed tekshirayotganda xato ({href}): {e}")
                is_parsed = False

            if is_parsed:
                consec_old += 1
                logger.debug(f"Parser {parser_id}: Oldin yuborilgan e'lon – {href} (ketma-ket {consec_old})")
                if consec_old >= MAX_CONSEC_OLD:
                    logger.info(
                        f"Parser {parser_id}: Ketma-ket {MAX_CONSEC_OLD} ta eski e'lon topildi, "
                        f"keyingi e'lonlar ham eski deb hisoblaymiz va to'xtaymiz."
                    )
                    break
                continue

            consec_old = 0
            new_hrefs.append(href)
            logger.info(f"Parser {parser_id}: Yangi e'lon topildi: {href}")

            if len(new_hrefs) >= MAX_NEW:
                logger.warning(
                    f"Parser {parser_id}: {MAX_NEW} ta yangi e'lon limitiga yetdik, "
                    f"keyingilar keyingi siklga qoldiriladi."
                )
                break

        if not new_hrefs:
            logger.info(f"Parser {parser_id}: Yangi e'lon topilmadi.")
            try:
                if current_hrefs:
                    await self.db.set_last_known_href(parser_id, current_hrefs[0])
            except Exception as e:
                logger.error(f"Parser {parser_id}: Bookmark yangilashda xato: {e}")
            return

        logger.info(f"Parser {parser_id}: {len(new_hrefs)} ta yangi e'lon yuboriladi.")

        sent_count = 0

        for href in new_hrefs:
            try:
                details = await self.parser_service.get_ad_details(href, site_type)

                if not details:
                    logger.warning(f"Parser {parser_id}: E'lon tafsilotlari olinmadi: {href}")
                    continue

                await self.send_to_channel(channel_id, details, site_type)
                await self.db.add_parsed_ad(parser_id, href)
                sent_count += 1
                logger.info(f"Parser {parser_id}: ✅ Yuborildi ({sent_count}/{len(new_hrefs)}): {href}")

                await asyncio.sleep(3) 

            except Exception as e:
                logger.error(f"Parser {parser_id}: E'lon yuborishda xato {href}: {e}")
                continue

        try:
            if current_hrefs:
                new_bookmark = current_hrefs[0]
                await self.db.set_last_known_href(parser_id, new_bookmark)
                logger.info(f"Parser {parser_id}: Bookmark yangilandi: {new_bookmark}")
        except Exception as e:
            logger.error(f"Parser {parser_id}: Bookmark yangilashda xato: {e}")

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