<<<<<<< HEAD
#!/usr/bin/env python
# start.py

import asyncio
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config.settings import settings
from src.core.database import create_tables
from src.services.persistence_service import PersistenceService
from src.core.scout_manager import ScoutManager
from src.core.performance_optimizer import PerformanceOptimizer
from src.telegram.bot import TelegramBot
from src.web.dashboard_server import DashboardServer

def setup_logging():
    # (此函数保持不变)
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(log_format))
    file_handler = logging.FileHandler(
        settings.LOG_DIR / 'crypto_scout.log',
        encoding='utf-8'
    )
    file_handler.setFormatter(logging.Formatter(log_format))
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL),
        handlers=[console_handler, file_handler]
    )

async def main():
    """主函数"""
    logger = logging.getLogger("Main")
    
    logger.info("=" * 60)
    logger.info("   Crypto Alpha Scout - 架构重构版")
    logger.info("=" * 60)
    
    await create_tables()
    
    scout_manager = ScoutManager(settings)
    await scout_manager.initialize()
    
    persistence_service = PersistenceService()
    
    telegram_bot = None
    if settings.TELEGRAM_BOT_TOKEN:
        # 修复：移除多余的 scout_manager 和 redis_client 参数
        telegram_bot = TelegramBot(token=settings.TELEGRAM_BOT_TOKEN)
    
    # 修复：移除多余的 scout_manager 参数
    dashboard = DashboardServer(settings)
    
    tasks = {
        "scouts": asyncio.create_task(scout_manager.start_scouts(settings.SCOUT_SETTINGS)),
        "persistence": asyncio.create_task(persistence_service.run()),
        "dashboard": asyncio.create_task(dashboard.start())
    }
    
    if telegram_bot:
        tasks["telegram"] = asyncio.create_task(telegram_bot.initialize())

    logger.info(f"✅ {len(tasks)}个核心服务正在启动...")
    
    try:
        await asyncio.gather(*tasks.values())
    except KeyboardInterrupt:
        logger.info("\n正在优雅关闭...")
        for task in tasks.values():
            task.cancel()
        await asyncio.gather(*tasks.values(), return_exceptions=True)
        await scout_manager.stop()
        if telegram_bot:
            await telegram_bot.stop()
        logger.info("✅ 程序已安全退出")

if __name__ == "__main__":
    setup_logging()
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序被手动中断")
=======
#!/usr/bin/env python
# start.py

import asyncio
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config.settings import settings
from src.core.database import create_tables
from src.services.persistence_service import PersistenceService
from src.core.scout_manager import ScoutManager
from src.core.performance_optimizer import PerformanceOptimizer
from src.telegram.bot import TelegramBot
from src.web.dashboard_server import DashboardServer

def setup_logging():
    # (此函数保持不变)
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(log_format))
    file_handler = logging.FileHandler(
        settings.LOG_DIR / 'crypto_scout.log',
        encoding='utf-8'
    )
    file_handler.setFormatter(logging.Formatter(log_format))
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL),
        handlers=[console_handler, file_handler]
    )

async def main():
    """主函数"""
    logger = logging.getLogger("Main")
    
    logger.info("=" * 60)
    logger.info("   Crypto Alpha Scout - 架构重构版")
    logger.info("=" * 60)
    
    await create_tables()
    
    scout_manager = ScoutManager(settings)
    await scout_manager.initialize()
    
    persistence_service = PersistenceService()
    
    telegram_bot = None
    if settings.TELEGRAM_BOT_TOKEN:
        # 修复：移除多余的 scout_manager 和 redis_client 参数
        telegram_bot = TelegramBot(token=settings.TELEGRAM_BOT_TOKEN)
    
    # 修复：移除多余的 scout_manager 参数
    dashboard = DashboardServer(settings)
    
    tasks = {
        "scouts": asyncio.create_task(scout_manager.start_scouts(settings.SCOUT_SETTINGS)),
        "persistence": asyncio.create_task(persistence_service.run()),
        "dashboard": asyncio.create_task(dashboard.start())
    }
    
    if telegram_bot:
        tasks["telegram"] = asyncio.create_task(telegram_bot.initialize())

    logger.info(f"✅ {len(tasks)}个核心服务正在启动...")
    
    try:
        await asyncio.gather(*tasks.values())
    except KeyboardInterrupt:
        logger.info("\n正在优雅关闭...")
        for task in tasks.values():
            task.cancel()
        await asyncio.gather(*tasks.values(), return_exceptions=True)
        await scout_manager.stop()
        if telegram_bot:
            await telegram_bot.stop()
        logger.info("✅ 程序已安全退出")

if __name__ == "__main__":
    setup_logging()
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序被手动中断")
>>>>>>> e5cf058720e42a15be9be28747f9f02b5d15a885
