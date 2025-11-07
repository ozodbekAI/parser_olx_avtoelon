import asyncpg
import logging
from typing import List, Dict, Optional
import json

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.pool: Optional[asyncpg.Pool] = None
    
    async def connect(self):
        """Database bilan ulanish"""
        self.pool = await asyncpg.create_pool(
            self.connection_string,
            min_size=1,
            max_size=10
        )
        await self.create_tables()
        logger.info("Database ulanishi o'rnatildi")
    
    async def disconnect(self):
        """Database ulanishini yopish"""
        if self.pool:
            await self.pool.close()
            logger.info("Database ulanishi yopildi")
    
    async def create_tables(self):
        """Kerakli jadvallarni yaratish"""
        async with self.pool.acquire() as conn:
            # Parsers jadvali
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS parsers (
                    id SERIAL PRIMARY KEY,
                    channel_id VARCHAR(255) NOT NULL,
                    url TEXT NOT NULL,
                    site_type VARCHAR(50) DEFAULT 'olx',
                    filter_text TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Parsed ads jadvali
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS parsed_ads (
                    id SERIAL PRIMARY KEY,
                    parser_id INTEGER REFERENCES parsers(id) ON DELETE CASCADE,
                    href TEXT NOT NULL,
                    parsed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(parser_id, href)
                )
            ''')
            
            # Parser hrefs jadvali - oxirgi ko'rilgan hreflarni saqlash uchun
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS parser_hrefs (
                    id SERIAL PRIMARY KEY,
                    parser_id INTEGER REFERENCES parsers(id) ON DELETE CASCADE,
                    hrefs JSONB NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # parser_id uchun unique constraint
            await conn.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS idx_parser_hrefs_parser_id 
                ON parser_hrefs(parser_id)
            ''')
            
            logger.info("Barcha jadvallar yaratildi")
    
    # Parser metodlari
    async def add_parser(self, channel_id: str, url: str, site_type: str = 'olx', 
                        filter_text: Optional[str] = None) -> int:
        """Yangi parser qo'shish"""
        async with self.pool.acquire() as conn:
            parser_id = await conn.fetchval(
                '''INSERT INTO parsers (channel_id, url, site_type, filter_text)
                   VALUES ($1, $2, $3, $4) RETURNING id''',
                channel_id, url, site_type, filter_text
            )
            logger.info(f"Yangi parser qo'shildi: {parser_id}")
            return parser_id
    
    async def get_all_active_parsers(self) -> List[Dict]:
        """Barcha faol parserlarni olish"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                'SELECT * FROM parsers WHERE is_active = TRUE'
            )
            return [dict(row) for row in rows]
    
    async def get_parser_by_channel(self, channel_id: str) -> Optional[Dict]:
        """Channel bo'yicha parserni olish"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT * FROM parsers WHERE channel_id = $1 AND is_active = TRUE',
                channel_id
            )
            return dict(row) if row else None
    
    async def delete_parser(self, parser_id: int) -> bool:
        """Parserni o'chirish"""
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                'UPDATE parsers SET is_active = FALSE WHERE id = $1',
                parser_id
            )
            return result == 'UPDATE 1'
    
    # Href saqlash metodlari - YANGILANGAN
    async def save_last_known_hrefs(self, parser_id: int, hrefs: List[str]):
        """Oxirgi ko'rilgan hreflarni saqlash (10 tagacha)"""
        async with self.pool.acquire() as conn:
            # Faqat 10 ta eng yangi hrefni saqlash
            hrefs_to_save = hrefs[:10]
            hrefs_json = json.dumps(hrefs_to_save)
            
            await conn.execute('''
                INSERT INTO parser_hrefs (parser_id, hrefs, updated_at)
                VALUES ($1, $2, CURRENT_TIMESTAMP)
                ON CONFLICT (parser_id) 
                DO UPDATE SET hrefs = $2, updated_at = CURRENT_TIMESTAMP
            ''', parser_id, hrefs_json)
            
            logger.info(f"Parser {parser_id}: {len(hrefs_to_save)} ta href saqlab qo'yildi")
    
    async def get_last_known_hrefs(self, parser_id: int, limit: int = 10) -> List[str]:
        """Oxirgi saqlab qo'yilgan hreflarni olish"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT hrefs FROM parser_hrefs WHERE parser_id = $1',
                parser_id
            )
            
            if row and row['hrefs']:
                hrefs = json.loads(row['hrefs'])
                return hrefs[:limit]
            return []
    
    # Eski metodlar - backward compatibility uchun
    async def get_last_known_href(self, parser_id: int) -> Optional[str]:
        """Oxirgi bitta hrefni olish (eski versiya bilan moslik uchun)"""
        hrefs = await self.get_last_known_hrefs(parser_id, limit=1)
        return hrefs[0] if hrefs else None
    
    async def set_last_known_href(self, parser_id: int, href: str):
        """Bitta hrefni saqlash (eski versiya bilan moslik uchun)"""
        await self.save_last_known_hrefs(parser_id, [href])
    
    # Parsed ads metodlari
    async def add_parsed_ad(self, parser_id: int, href: str):
        """Yangi parse qilingan elonni qo'shish"""
        async with self.pool.acquire() as conn:
            try:
                await conn.execute(
                    '''INSERT INTO parsed_ads (parser_id, href)
                       VALUES ($1, $2)
                       ON CONFLICT (parser_id, href) DO NOTHING''',
                    parser_id, href
                )
            except Exception as e:
                logger.error(f"Parsed ad qo'shishda xato: {e}")
    
    async def is_ad_parsed(self, parser_id: int, href: str) -> bool:
        """Elon ilgari parse qilinganmi tekshirish"""
        async with self.pool.acquire() as conn:
            result = await conn.fetchval(
                'SELECT EXISTS(SELECT 1 FROM parsed_ads WHERE parser_id = $1 AND href = $2)',
                parser_id, href
            )
            return result
    
    async def get_parsed_ads_count(self, parser_id: int) -> int:
        """Parser uchun parse qilingan elonlar sonini olish"""
        async with self.pool.acquire() as conn:
            count = await conn.fetchval(
                'SELECT COUNT(*) FROM parsed_ads WHERE parser_id = $1',
                parser_id
            )
            return count
    
    async def cleanup_old_ads(self, days: int = 30):
        """Eski elonlarni tozalash"""
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                '''DELETE FROM parsed_ads 
                   WHERE parsed_at < CURRENT_TIMESTAMP - INTERVAL '%s days' ''',
                days
            )
            logger.info(f"Eski elonlar tozalandi: {result}")