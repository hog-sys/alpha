<<<<<<< HEAD
# crypto_scout.py
# 作用：作为一个独立的微服务，持续监听加密货币扫描任务，
# 执行分析，并将结果存入数据库。

import json
import time
import random # 用于模拟分析结果
from messaging_client import MessagingClient
from database import Database, Signal

# 定义这个 Scout 监听的队列名称和其在数据库中的源名称
QUEUE_NAME = 'crypto_scan_tasks'
SOURCE_NAME = 'crypto_scout'

class CryptoAnalyzer:
    """
    封装了加密货币分析的核心逻辑。
    在实际应用中，这里会包含连接交易所、获取数据、
    计算技术指标、运行机器学习模型等复杂操作。
    """
    def __init__(self):
        # 初始化可能需要的客户端或模型
        # from config import settings
        # self.exchange_client = ccxt.binance({ ... })
        print("CryptoAnalyzer initialized.")

    def analyze(self, task: dict):
        """
        执行分析任务并返回结果列表。
        这是一个模拟实现，实际中应替换为真实的分析逻辑。
        """
        print(f"Analyzing task: {task}")
        symbols = task.get('symbols', [])
        results = []

        for symbol in symbols:
            # --- 在这里插入您原来的核心分析逻辑 ---
            # 1. 从交易所获取K线数据 (e.g., using ccxt)
            # 2. 计算技术指标 (e.g., RSI, MACD)
            # 3. (可选) 调用 ML 模型进行预测
            # 4. 生成信号
            
            # 模拟分析过程
            time.sleep(random.uniform(0.5, 2.0)) 
            
            # 模拟生成一个信号
            mock_price = 60000 + random.uniform(-500, 500)
            mock_signal = random.choice(['BUY', 'SELL', 'HOLD'])
            
            if mock_signal != 'HOLD':
                result = {
                    'symbol': symbol,
                    'signal_type': mock_signal,
                    'price': round(mock_price, 2),
                    'source': SOURCE_NAME,
                    'metadata': { # 可以存储一些额外的分析依据
                        'rsi': round(random.uniform(20, 80), 2),
                        'macd_hist': round(random.uniform(-100, 100), 2)
                    }
                }
                results.append(result)
        
        print(f"Analysis complete. Found {len(results)} signals.")
        return results

def process_task_message(ch, method, properties, body):
    """
    这是 RabbitMQ 的核心回调函数。
    每当从队列中收到一条消息，这个函数就会被自动调用。
    """
    try:
        task = json.loads(body)
        print(f"\n[+] Received task: {task}")
        
        # 1. 执行分析
        analyzer = CryptoAnalyzer()
        signals = analyzer.analyze(task)
        
        # 2. 如果有信号，存入数据库
        if signals:
            db = Database()
            for signal_data in signals:
                db.save_signal(signal_data)
        
        # 3. 确认消息处理完毕
        # 这会告诉 RabbitMQ 可以安全地从队列中删除这条消息了。
        ch.basic_ack(delivery_tag=method.delivery_tag)
        print(f"[✔] Task processed successfully. Acknowledged message.")

    except json.JSONDecodeError as e:
        print(f"[!] Failed to decode message body: {e}")
        # 拒绝消息，并且不要重新排队，因为它格式错误
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except Exception as e:
        print(f"[!] An unexpected error occurred: {e}")
        # 发生未知错误，拒绝消息但允许其重新排队，以便稍后重试
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


def main():
    """
    启动 Crypto Scout 服务。
    """
    print(f"--- Crypto Scout Service starting ---")
    print(f"--- Listening for tasks on queue: '{QUEUE_NAME}' ---")
    
    messaging_client = MessagingClient()
    messaging_client.declare_queue(QUEUE_NAME)
    messaging_client.consume_messages(QUEUE_NAME, process_task_message)

if __name__ == '__main__':
    main()
=======
import asyncio
import sys
import os
from pathlib import Path
import logging
from datetime import datetime
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from src.core.scout_manager import ScoutManager
from src.core.performance_optimizer import PerformanceOptimizer
from src.telegram.bot import TelegramBot
from src.analysis.realtime_analyzer import RealtimeAnalyzer
from src.web.dashboard_server import DashboardServer
from config.high_performance import HighPerformanceConfig

# 配置彩色日志（Windows）
import colorama
colorama.init()

class CryptoScoutPro:
    
    def __init__(self):
        self.config = HighPerformanceConfig()
        self.setup_logging()
        self.optimizer = PerformanceOptimizer()
        
        # 利用多核CPU
        self.cpu_count = mp.cpu_count()
        self.process_pool = ProcessPoolExecutor(max_workers=self.cpu_count - 1)
        self.thread_pool = ThreadPoolExecutor(max_workers=self.cpu_count * 2)
        
        self.logger.info(f"系统初始化 - CPU核心: {self.cpu_count}")
        
    def setup_logging(self):
        """配置日志系统"""
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        
        # 控制台日志（彩色）
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(log_format))
        
        # 文件日志
        file_handler = logging.FileHandler(
            f'logs/crypto_scout_{datetime.now().strftime("%Y%m%d")}.log'
        )
        file_handler.setFormatter(logging.Formatter(log_format))
        
        self.logger = logging.getLogger('CryptoScout')
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)
        self.logger.setLevel(logging.INFO)
    
    async def start(self):
        """启动所有服务"""
        self.logger.info("=" * 60)
        self.logger.info("   Crypto Alpha Scout - 高性能版")
        self.logger.info("=" * 60)
        
        # 系统优化
        await self.optimizer.optimize_windows_performance()
        
        # 启动Redis（如果安装了）
        await self.start_redis()
        
        # 初始化数据库
        await self.init_database()
        
        # 启动核心服务
        tasks = [
            self.start_scout_manager(),
            self.start_telegram_bot(),
            self.start_analyzer(),
            self.start_web_dashboard(),
            self.start_monitoring()
        ]
        
        # 并发启动所有服务
        await asyncio.gather(*tasks)
        
        self.logger.info("✅ 所有服务启动完成！")
        self.logger.info(f"📊 Web控制台: http://localhost:{self.config.WEB_PORT}")
        self.logger.info(f"📈 性能监控: http://localhost:{self.config.METRICS_PORT}")
        
    async def start_scout_manager(self):
        """启动Scout管理器"""
        self.scout_manager = ScoutManager(
            config=self.config,
            process_pool=self.process_pool,
            thread_pool=self.thread_pool
        )
        
        # 启动所有Scout
        scouts_config = {
            'market': {
                'class': 'MarketScout',
                'workers': 4,  # 多进程
                'priority': 'high'
            },
            'defi': {
                'class': 'DeFiScout',
                'workers': 2,
                'priority': 'medium'
            },
            'contract': {
                'class': 'ContractScout',
                'workers': 2,
                'priority': 'medium'
            },
            'chain': {
                'class': 'ChainScout',
                'workers': 3,
                'priority': 'high'
            }
        }
        
        await self.scout_manager.start_scouts(scouts_config)
        
    async def start_redis(self):
        """启动本地Redis服务"""
        import subprocess
        
        try:
            # 检查Redis是否已运行
            import redis
            r = redis.Redis()
            r.ping()
            self.logger.info("✅ Redis已在运行")
        except:
            self.logger.info("启动Redis服务...")
            # 启动Redis服务器
            redis_path = r"C:\Program Files\Redis\redis-server.exe"
            if os.path.exists(redis_path):
                subprocess.Popen([redis_path], 
                               creationflags=subprocess.CREATE_NO_WINDOW)
                await asyncio.sleep(2)
                self.logger.info("✅ Redis启动成功")
            else:
                self.logger.warning("⚠️ 未找到Redis，使用内存缓存")
    
    async def init_database(self):
        """初始化数据库"""
        try:
            # 确保数据目录存在
            data_dir = Path('data')
            data_dir.mkdir(exist_ok=True)
            
            # 初始化SQLite数据库
            import sqlite3
            db_path = data_dir / 'crypto_scout.db'
            conn = sqlite3.connect(str(db_path))
            
            # 创建必要的表
            conn.execute('''
                CREATE TABLE IF NOT EXISTS opportunities (
                    id TEXT PRIMARY KEY,
                    scout_name TEXT,
                    signal_type TEXT,
                    symbol TEXT,
                    confidence REAL,
                    data TEXT,
                    timestamp TEXT,
                    expires_at TEXT
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS system_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    opportunities_found INTEGER,
                    errors_count INTEGER,
                    memory_usage REAL,
                    cpu_usage REAL
                )
            ''')
            
            conn.commit()
            conn.close()
            
            self.logger.info("✅ 数据库初始化完成")
            
        except Exception as e:
            self.logger.error(f"数据库初始化失败: {e}")
            self.logger.warning("⚠️ 数据库初始化失败，将使用内存模式")
    
    async def start_telegram_bot(self):
        """启动Telegram机器人"""
        try:
            if not self.config.TELEGRAM_BOT_TOKEN:
                self.logger.warning("⚠️ 未设置Telegram机器人TOKEN，跳过启动。")
                return
            self.telegram_bot = TelegramBot(token=self.config.TELEGRAM_BOT_TOKEN, scout_manager=self.scout_manager)
            await self.telegram_bot.initialize()
            self.logger.info("✅ Telegram机器人启动成功")
        except Exception as e:
            self.logger.error(f"启动Telegram机器人失败: {e}")
    
    async def start_analyzer(self):
        """启动实时分析器"""
        try:
            self.realtime_analyzer = RealtimeAnalyzer(self.config)
            await self.realtime_analyzer.initialize()
            self.logger.info("✅ 实时分析器启动成功")
        except Exception as e:
            self.logger.error(f"启动实时分析器失败: {e}")
    
    async def start_web_dashboard(self):
        """启动Web控制台"""
        try:
            self.dashboard_server = DashboardServer(
                config=self.config,
                scout_manager=self.scout_manager
            )
            await self.dashboard_server.start()
            self.logger.info("✅ Web控制台启动成功")
        except Exception as e:
            self.logger.error(f"启动Web控制台失败: {e}")
            self.logger.warning("⚠️ Web控制台启动失败，继续运行其他服务")
    
    async def start_monitoring(self):
        """启动系统监控"""
        try:
            # 启动性能监控任务
            asyncio.create_task(self._monitor_performance())
            self.logger.info("✅ 系统监控已启动")
        except Exception as e:
            self.logger.error(f"启动系统监控失败: {e}")
    
    async def _monitor_performance(self):
        """监控系统性能"""
        while True:
            try:
                # 获取系统信息
                system_info = self.optimizer.get_system_info()
                
                # 检查关键指标
                memory_usage = (system_info['memory_total'] - system_info['memory_available']) / system_info['memory_total'] * 100
                disk_usage = system_info['disk_usage']
                
                # 记录性能指标
                self.logger.info(f"📊 系统性能 - CPU: {system_info['cpu_freq']:.0f}MHz, "
                               f"内存: {memory_usage:.1f}%, 磁盘: {disk_usage:.1f}%")
                
                # 检查警告条件
                if memory_usage > 80:
                    self.logger.warning("⚠️ 内存使用率过高")
                if disk_usage > 90:
                    self.logger.warning("⚠️ 磁盘使用率过高")
                
                await asyncio.sleep(60)  # 每分钟检查一次
                
            except Exception as e:
                self.logger.error(f"性能监控错误: {e}")
                await asyncio.sleep(30)
    
    async def run_forever(self):
        """主运行循环"""
        await self.start()
        
        # 设置Ctrl+C处理
        import signal
        
        def signal_handler(sig, frame):
            self.logger.info("\n正在优雅关闭...")
            asyncio.create_task(self.shutdown())
        
        signal.signal(signal.SIGINT, signal_handler)
        
        # 保持运行
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            pass
    
    async def shutdown(self):
        """优雅关闭"""
        self.logger.info("关闭进程池...")
        self.process_pool.shutdown(wait=True)
        self.thread_pool.shutdown(wait=True)
        
        self.logger.info("保存状态...")
        await self.scout_manager.save_state()
        
        self.logger.info("✅ 程序已安全退出")
        sys.exit(0)

# Windows特定优化
if sys.platform == 'win32':
    # 使用更快的事件循环
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    # 多进程支持
    mp.set_start_method('spawn', force=True)

def main():
    """程序入口"""
    app = CryptoScoutPro()
    asyncio.run(app.run_forever())

if __name__ == "__main__":
    main()
>>>>>>> e5cf058720e42a15be9be28747f9f02b5d15a885
