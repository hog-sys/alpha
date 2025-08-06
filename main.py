<<<<<<< HEAD
import sys
import os
import asyncio
import logging
from pathlib import Path
from dotenv import load_dotenv

# --- 将项目根目录添加到Python的模块搜索路径中 ---
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# 在所有其他导入之前加载环境变量
load_dotenv()

# 导入核心模块
from config.settings import settings
from src.core import ScoutManager, PerformanceOptimizer
from src.telegram import TelegramBot
from src.web import DashboardServer
from src.analysis import MLPredictor

# 配置日志
def setup_logging():
    """配置日志系统"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # 文件处理器
    file_handler = logging.FileHandler(
        log_dir / f"crypto_scout_{asyncio.get_event_loop().time():.0f}.log",
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 根日志器配置
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

async def main():
    """主函数，启动所有服务"""
    # 设置日志
    setup_logging()
    logger = logging.getLogger("Main")
    
    try:
        # 验证配置
        settings.validate()
        logger.info("✅ 配置验证通过")
        
        # 创建必要的目录
        Path("data").mkdir(exist_ok=True)
        Path("ml_models").mkdir(exist_ok=True)
        Path("logs").mkdir(exist_ok=True)
        
        # 初始化机器学习预测器
        logger.info("正在初始化机器学习预测器...")
        ml_predictor = MLPredictor(settings)
        await ml_predictor.initialize()
        logger.info("✅ 机器学习预测器已加载！")
        
        # 性能优化
        optimizer = PerformanceOptimizer()
        await optimizer.optimize_performance()
        logger.info("✅ 性能优化完成")
        
        # 初始化扫描管理器
        scout_manager = ScoutManager(settings, ml_predictor=ml_predictor)
        await scout_manager.initialize()
        logger.info("✅ 扫描管理器已初始化")
        
        # 初始化Telegram机器人
        telegram_bot = TelegramBot(
            token=settings.telegram.token,
            scout_manager=scout_manager,
            redis_client=scout_manager.redis
        )
        logger.info("✅ Telegram机器人已初始化")
        
        # 初始化Web仪表板
        dashboard_server = DashboardServer(settings, scout_manager)
        logger.info("✅ Web仪表板已初始化")
        
        # 启动所有服务
        logger.info("🚀 开始启动所有服务...")
        await asyncio.gather(
            scout_manager.start_scouts(settings.get_enabled_scouts()),
            telegram_bot.initialize(),
            dashboard_server.start(),
            return_exceptions=True
        )
        
    except ValueError as e:
        logger.error(f"配置错误: {e}")
        return
    except Exception as e:
        logger.critical(f"主程序发生严重错误: {e}", exc_info=True)
    finally:
        logger.info("正在关闭所有服务...")
        try:
            await scout_manager.stop()
            if telegram_bot.app:
                await telegram_bot.stop()
        except Exception as e:
            logger.error(f"关闭服务时发生错误: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序被手动中断。")
    except Exception as e:
        print(f"程序启动失败: {e}")
=======
import sys
import os
import asyncio
import logging
from dotenv import load_dotenv

# --- 将项目根目录添加到Python的模块搜索路径中 ---
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# 在所有其他导入之前加载环境变量
load_dotenv()

# 导入核心模块
from src.core import ScoutManager, PerformanceOptimizer
from src.telegram import TelegramBot
from src.web import DashboardServer
from src.analysis import MLPredictor # <-- 新增：导入ML预测器

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 配置对象
class Config:
    def __init__(self):
        self.REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.REDIS_POOL_SIZE = 10
        self.TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
        self.WEB_PORT = int(os.getenv("PORT", 8080))
        self.ML_MODEL_PATH = "ml_models" # <-- 新增：模型路径
        
        self.SCOUT_SETTINGS = {
            "market": {"scan_interval": 30},
        }
        self.ENABLED_SCOUTS = {
            "market": {"enabled": True, "workers": 1},
        }

async def main():
    """主函数，启动所有服务"""
    logger = logging.getLogger("Main")
    
    config = Config()
    if not config.TELEGRAM_TOKEN:
        logger.error("错误：TELEGRAM_TOKEN环境变量未设置！")
        return

    # --- 唤醒机器学习模块 ---
    logger.info("正在初始化机器学习预测器...")
    ml_predictor = MLPredictor(config)
    await ml_predictor.initialize()
    logger.info("✅ 机器学习预测器已加载！")

    optimizer = PerformanceOptimizer()
    await optimizer.optimize_performance()

    # 将 ml_predictor 传递给 ScoutManager
    scout_manager = ScoutManager(config, ml_predictor=ml_predictor)
    await scout_manager.initialize()

    telegram_bot = TelegramBot(
        token=config.TELEGRAM_TOKEN, 
        scout_manager=scout_manager,
        redis_client=scout_manager.redis
    )
    
    dashboard_server = DashboardServer(config, scout_manager)

    try:
        logger.info("🚀 开始启动所有服务...")
        await asyncio.gather(
            scout_manager.start_scouts(config.ENABLED_SCOUTS),
            telegram_bot.initialize(),
            # dashboard_server.start() # 在main.py中不再需要启动web服务
        )
    except Exception as e:
        logger.critical(f"主程序发生严重错误: {e}", exc_info=True)
    finally:
        logger.info("正在关闭所有服务...")
        await scout_manager.stop()
        if telegram_bot.app:
            await telegram_bot.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("程序被手动中断。")
>>>>>>> e5cf058720e42a15be9be28747f9f02b5d15a885
