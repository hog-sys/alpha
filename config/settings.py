"""
配置管理模块（已适配微服务与 Infisical 注入的环境变量）

要点：
- 移除 SQLite 默认值，默认改为 TimescaleDB（PostgreSQL/asyncpg）
- 不直接依赖 .env；密钥/配置由 Infisical 在运行时注入到环境变量
- 提供 get_config() 供其他模块（如 ML/回测/服务）以 dict 形式获取配置
"""
import os
from typing import Dict, Any
from dataclasses import dataclass, asdict


@dataclass
class DatabaseConfig:
    """数据库配置"""
    # 默认 TimescaleDB（PostgreSQL + asyncpg 驱动）
    url: str = "postgresql+asyncpg://crypto_user:crypto_pass@localhost:5432/crypto_scout"
    pool_size: int = 10
    max_overflow: int = 20
    echo: bool = False

@dataclass
class RabbitMQConfig:
    """消息队列配置"""
    url: str = "amqp://guest:guest@localhost:5672/"

@dataclass
class RedisConfig:
    """Redis配置"""
    url: str = "redis://localhost:6379"
    pool_size: int = 10
    decode_responses: bool = True

@dataclass
class TelegramConfig:
    """Telegram配置"""
    token: str = ""
    chat_id: str = ""
    webhook_url: str = ""

@dataclass
class MLConfig:
    """机器学习配置"""
    model_path: str = "ml_models"
    feature_window: int = 20
    prediction_horizon: int = 5
    retrain_interval: int = 3600  # 1小时
    min_training_samples: int = 1000

@dataclass
class ScoutConfig:
    """扫描器配置"""
    scan_interval: int = 30
    max_workers: int = 5
    timeout: int = 30
    retry_attempts: int = 3

@dataclass
class WebConfig:
    """Web服务配置"""
    host: str = "0.0.0.0"
    port: int = 8080
    debug: bool = False
    reload: bool = False

class Settings:
    """主配置类"""
    
    def __init__(self):
        self.database = DatabaseConfig()
        self.rabbitmq = RabbitMQConfig()
        self.redis = RedisConfig()
        self.telegram = TelegramConfig()
        self.ml = MLConfig()
        self.scout = ScoutConfig()
        self.web = WebConfig()
        self.environment = os.getenv("ENVIRONMENT", "production")
        
        self._load_from_env()
    
    def _load_from_env(self):
        """从环境变量加载配置"""
        # 数据库配置
        if os.getenv("DATABASE_URL"):
            self.database.url = os.getenv("DATABASE_URL")
        # 兼容旧变量名
        if os.getenv("DB_URL") and not os.getenv("DATABASE_URL"):
            self.database.url = os.getenv("DB_URL")
        
        # RabbitMQ 配置
        if os.getenv("RABBITMQ_URL"):
            self.rabbitmq.url = os.getenv("RABBITMQ_URL")

        # Redis配置
        if os.getenv("REDIS_URL"):
            self.redis.url = os.getenv("REDIS_URL")
        
        # Telegram配置
        # 优先读取 TELEGRAM_BOT_TOKEN，其次 TELEGRAM_TOKEN（向后兼容）
        if os.getenv("TELEGRAM_BOT_TOKEN"):
            self.telegram.token = os.getenv("TELEGRAM_BOT_TOKEN")
        elif os.getenv("TELEGRAM_TOKEN"):
            self.telegram.token = os.getenv("TELEGRAM_TOKEN")
        if os.getenv("TELEGRAM_CHAT_ID"):
            self.telegram.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        
        # Web配置
        if os.getenv("PORT"):
            self.web.port = int(os.getenv("PORT"))
        if os.getenv("HOST"):
            self.web.host = os.getenv("HOST")
        
    def validate(self) -> bool:
        """轻量校验：不强制 Telegram Token，避免非 Bot 进程报错"""
        # 可按需扩展更多校验
        return True

# 全局配置实例
settings = Settings()

def get_config() -> Dict[str, Any]:
    """提供统一的字典配置（给 ML/回测/服务层使用）"""
    return {
        "environment": settings.environment,
        "database_url": settings.database.url,
        "redis_url": settings.redis.url,
        "rabbitmq_url": settings.rabbitmq.url,
        "telegram_token": settings.telegram.token,
        "ml": {
            "model_path": settings.ml.model_path,
            "feature_window": settings.ml.feature_window,
            "prediction_horizon": settings.ml.prediction_horizon,
            "retrain_interval": settings.ml.retrain_interval,
            "min_training_samples": settings.ml.min_training_samples,
        },
        "web": {
            "host": settings.web.host,
            "port": settings.web.port,
            "debug": settings.web.debug,
            "reload": settings.web.reload,
        },
        "scout": {
            "scan_interval": settings.scout.scan_interval,
            "max_workers": settings.scout.max_workers,
            "timeout": settings.scout.timeout,
            "retry_attempts": settings.scout.retry_attempts,
        },
    }
