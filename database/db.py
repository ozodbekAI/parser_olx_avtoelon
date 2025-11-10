import aiosqlite
import logging
from typing import List, Dict, Optional
from config import Config

logger = logging.getLogger(__name__)


class Database:
    
    def __init__(self):
        self.db_name = Config.DB_NAME
    
    def get_connection(self):
        return aiosqlite.connect(self.db_name)
    
    async def create_tables(self):
        async with self.get_connection() as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS parsers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id INTEGER NOT NULL,
                    url TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    site_type TEXT DEFAULT 'olx',
                    filter_text TEXT,
                    last_known_href TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'active'
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS parsed_ads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parser_id INTEGER NOT NULL,
                    href TEXT NOT NULL,
                    parsed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (parser_id) REFERENCES parsers (id),
                    UNIQUE(parser_id, href)
                )
            """)
            
            await db.commit()
            logger.info("Database jadvallar yaratildi")
    
    async def add_parser(self, admin_id: int, url: str, channel_id: str, site_type: str = 'olx', filter_text: Optional[str] = None) -> int:
        async with self.get_connection() as db:
            cursor = await db.execute(
                "INSERT INTO parsers (admin_id, url, channel_id, site_type, filter_text) VALUES (?, ?, ?, ?, ?)",
                (admin_id, url, channel_id, site_type, filter_text)
            )
            await db.commit()
            return cursor.lastrowid
    
    async def get_user_parsers(self, admin_id: int) -> List[Dict]:
        async with self.get_connection() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM parsers WHERE admin_id = ? AND status = 'active'",
                (admin_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def get_all_active_parsers(self) -> List[Dict]:
        async with self.get_connection() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM parsers WHERE status = 'active'"
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def delete_parser(self, parser_id: int) -> bool:
        async with self.get_connection() as db:
            await db.execute(
                "UPDATE parsers SET status = 'deleted' WHERE id = ?",
                (parser_id,)
            )
            await db.commit()
            return True
    
    async def add_parsed_ad(self, parser_id: int, href: str) -> bool:
        try:
            async with self.get_connection() as db:
                await db.execute(
                    "INSERT INTO parsed_ads (parser_id, href) VALUES (?, ?)",
                    (parser_id, href)
                )
                await db.commit()
                return True
        except aiosqlite.IntegrityError:
            return False
    
    async def get_parsed_ads(self, parser_id: int, limit: int = 50) -> List[str]:
        async with self.get_connection() as db:
            async with db.execute(
                "SELECT href FROM parsed_ads WHERE parser_id = ? ORDER BY parsed_at DESC LIMIT ?",
                (parser_id, limit)
            ) as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]
    
    async def is_ad_parsed(self, parser_id: int, href: str) -> bool:
        async with self.get_connection() as db:
            async with db.execute(
                "SELECT 1 FROM parsed_ads WHERE parser_id = ? AND href = ?",
                (parser_id, href)
            ) as cursor:
                row = await cursor.fetchone()
                return row is not None
    
    async def get_last_known_href(self, parser_id: int) -> Optional[str]:
        async with self.get_connection() as db:
            async with db.execute(
                "SELECT last_known_href FROM parsers WHERE id = ?",
                (parser_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None
    
    async def set_last_known_href(self, parser_id: int, href: str):
        async with self.get_connection() as db:
            await db.execute(
                "UPDATE parsers SET last_known_href = ? WHERE id = ?",
                (href, parser_id)
            )
            await db.commit()