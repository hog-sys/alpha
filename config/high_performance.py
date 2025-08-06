import os
import multiprocessing as mp
from pathlib import Path

class HighPerformanceConfig:
    """高性能配置"""
    
    def __init__(self):
        # 基础路径
        self.BASE_DIR = Path(__file__).parent.parent
        self.DATA_DIR = self.BASE_DIR / "data"
        self.LOG_DIR = self.BASE_DIR / "logs"
        
        # 性能设置
        self.CPU_CORES = mp.cpu_count()
        self.MAX_WORKERS = self.CPU_CORES - 1  # 留一个核心给系统
        self.ASYNC_CONCURRENCY = 100  # 异步并发数
        
        # 数据库设置（使用PostgreSQL以获得最佳性能）
        self.DATABASE_URL = os.getenv(
            'DATABASE_URL',
            f'sqlite:///{self.DATA_DIR}/crypto_scout.db'
        )
        
        # Redis设置
        self.REDIS_URL = 'redis://localhost:6379'
        self.REDIS_POOL_SIZE = 50
        
        # Scout设置
        self.SCOUT_SETTINGS = {
            'market': {
                'scan_interval': 10,  # 10秒，高频扫描
                'batch_size': 100,
                'timeout': 30,
                'max_retries': 3,
                'exchanges': [
                    'binance', 'okx', 'bybit', 'coinbase',
                    'kraken', 'gateio', 'kucoin', 'huobi'
                ]
            },
            'defi': {
                'scan_interval': 30,
                'protocols': [
                    'uniswap_v3', 'uniswap_v2', 'sushiswap',
                    'pancakeswap', 'curve', 'aave', 'compound'
                ],
                'min_tvl': 100000,  # $100k最小TVL
                'parallel_queries': 10
            },
            'contract': {
                'scan_interval': 5,  # 5秒，捕捉新合约
                'chains': ['ethereum', 'bsc', 'polygon', 'arbitrum'],
                'block_confirmations': 1,
                'mempool_scan': True
            }
        }
        
        # 性能优化
        self.PERFORMANCE = {
            'connection_pool_size': 100,
            'connection_timeout': 30,
            'request_timeout': 10,
            'max_retries': 3,
            'backoff_factor': 0.3,
            'cache_ttl': 300,  # 5分钟
            'batch_processing': True,
            'compression': 'lz4'  # 快速压缩
        }
        
        # Web设置
        self.WEB_PORT = 8000
        self.METRICS_PORT = 9090
        
        # Telegram设置
        self.TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
        
        # 机器学习设置
        self.ML_ENABLED = True
        self.ML_MODEL_PATH = self.DATA_DIR / 'models'
        self.ML_RETRAIN_INTERVAL = 86400  # 每天重训练