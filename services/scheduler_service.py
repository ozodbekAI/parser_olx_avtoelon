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
                logger.error(f"Parser {parser['id']} xatosi: {e}")
   
    async def check_parser(self, parser: dict):
        parser_id = parser['id']
        url = parser['url']
        channel_id = parser['channel_id']
        site_type = parser['site_type']
        filter_text = parser['filter_text']
       
        # Joriy elonlarni olish
        current_hrefs = await self.parser_service.get_listings(url, site_type, filter_text)
       
        if not current_hrefs:
            logger.info(f"Parser {parser_id}: Hech qanday elon topilmadi.")
            return
        
        logger.info(f"Parser {parser_id}: Joriy elonlar soni: {len(current_hrefs)}")
       
        # Oxirgi saqlab qo'yilgan 10 ta hrefni olish
        last_known_hrefs = await self.db.get_last_known_hrefs(parser_id, limit=10)
        logger.info(f"Parser {parser_id}: Saqlab qo'yilgan hrefs soni: {len(last_known_hrefs)}")
       
        # Birinchi ishga tushirish
        if not last_known_hrefs:
            logger.info(f"Parser {parser_id}: Birinchi ishga tushirish - faqat eng yangi elon yuboriladi")
            
            # Faqat eng yangi elonni yuborish
            if current_hrefs:
                new_href = current_hrefs[0]
                
                try:
                    details = await self.parser_service.get_ad_details(new_href, site_type)
                    
                    if details:
                        await self.send_to_channel(channel_id, details, site_type)
                        await self.db.add_parsed_ad(parser_id, new_href)
                        logger.info(f"✅ Birinchi elon yuborildi: {new_href}")
                        await asyncio.sleep(3)
                    else:
                        logger.warning(f"E'lon tafsilotlari olinmadi: {new_href}")
                        
                except Exception as e:
                    logger.error(f"Birinchi elonni yuborishda xato {new_href}: {e}")
                
                # Oxirgi 10 ta hrefni saqlash
                hrefs_to_save = current_hrefs[:10]
                await self.db.save_last_known_hrefs(parser_id, hrefs_to_save)
                logger.info(f"Saqlab qo'yildi: {len(hrefs_to_save)} ta href")
               
            return
       
        # Yangi elonlarni topish
        new_hrefs = []
        found_any_known = False
        
        for href in current_hrefs:
            # Agar bu href oldin ko'rilgan bo'lsa, to'xtash
            if href in last_known_hrefs:
                found_any_known = True
                logger.info(f"Ma'lum href topildi: {href}")
                break
            new_hrefs.append(href)
            
            # Xavfsizlik: juda ko'p yangi elon bo'lmasin
            if len(new_hrefs) >= 50:
                logger.warning(f"Parser {parser_id}: 50 tadan ortiq yangi elon topildi, to'xtatilmoqda")
                break
       
        # Agar hech qanday ma'lum href topilmasa (masalan, hammasi o'chirilgan)
        if not found_any_known and len(current_hrefs) > 0:
            logger.warning(f"Parser {parser_id}: Hech qanday ma'lum href topilmadi! Ehtimol barcha eski elonlar o'chirilgan.")
            logger.warning(f"Xavfsizlik uchun faqat 5 ta eng yangi elonni yuborish")
            new_hrefs = current_hrefs[:5]  # Faqat 5 ta eng yangi
       
        logger.info(f"Parser {parser_id}: Yangi elonlar soni: {len(new_hrefs)}")
       
        if not new_hrefs:
            logger.info(f"Parser {parser_id}: Yangi elon yo'q")
            return
       
        # Yangi elonlarni yuborish (eng yangi birinchi)
        sent_count = 0
        successfully_sent = []
        
        for href in new_hrefs:
            try:
                logger.info(f"E'lon yuklanmoqda: {href}")
                details = await self.parser_service.get_ad_details(href, site_type)
               
                if details:
                    await self.send_to_channel(channel_id, details, site_type)
                    await self.db.add_parsed_ad(parser_id, href)
                    successfully_sent.append(href)
                    sent_count += 1
                    logger.info(f"✅ Yuborildi ({sent_count}/{len(new_hrefs)}): {href}")
                    await asyncio.sleep(3)
                else:
                    logger.warning(f"E'lon tafsilotlari olinmadi: {href}")
                   
            except Exception as e:
                logger.error(f"E'lon yuborishda xato {href}: {e}")
                continue
       
        # Oxirgi 10 ta hrefni yangilash
        # Yangi yuborilgan + eski saqlab qo'yilganlarni birlashtirish
        updated_hrefs = current_hrefs[:10]  # Eng yangi 10 ta
        await self.db.save_last_known_hrefs(parser_id, updated_hrefs)
        logger.info(f"Parser {parser_id}: Yangilangan hrefs saqlab qo'yildi: {len(updated_hrefs)} ta")
       
   
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
            raise
   
    def stop(self):
        self.is_running = False
        logger.info("Scheduler to'xtatildi")