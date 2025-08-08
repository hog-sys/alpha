# src/core/db.py
"""全局 TimescaleDB 访问器

用法：
    from src.core.db import db
    await db.initialize()  # 在应用启动时调用一次
    async with db.async_session() as session:
        ...
"""
import os
import asyncio
from typing import Optional
import logging

from src.core.database import TimescaleDBManager

logger = logging.getLogger(__name__)

database_url = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://crypto_user:SecureDBPass123!@localhost:5432/crypto_scout",
)

db = TimescaleDBManager(database_url)

_initialized: bool = False

async def init_db() -> None:
    global _initialized
    if _initialized:
        return
    await db.initialize()
    _initialized = True
    logger.info("TimescaleDB global manager initialized")

# For synchronous contexts where event loop exists, provide helper
def init_db_sync() -> None:
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # schedule in running loop
            loop.create_task(init_db())
        else:
            loop.run_until_complete(init_db())
    except RuntimeError:
        # No event loop, create new
        asyncio.run(init_db())

