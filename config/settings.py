"""
配置管理模块
"""
import os
from typing import Dict, Any
from dataclasses import dataclass
from pathlib import Path

@dataclass
class DatabaseConfig:
    """数据库配置"""
    url: str = "sqlite:///data/crypto_scout.db"
    pool_size: int = 10
    max_overflow: int = 20
    echo: bool = False

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
        self.redis = RedisConfig()
        self.telegram = TelegramConfig()
        self.ml = MLConfig()
        self.scout = ScoutConfig()
        self.web = WebConfig()
        
        self._load_from_env()
    
    def _load_from_env(self):
        """从环境变量加载配置"""
        # 数据库配置
        if os.getenv("DATABASE_URL"):
            self.database.url = os.getenv("DATABASE_URL")
        
        # Redis配置
        if os.getenv("REDIS_URL"):
            self.redis.url = os.getenv("REDIS_URL")
        
        # Telegram配置
        if os.getenv("TELEGRAM_TOKEN"):
            self.telegram.token = os.getenv("TELEGRAM_TOKEN")
        if os.getenv("TELEGRAM_CHAT_ID"):
            self.telegram.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        
        # Web配置
        if os.getenv("PORT"):
            self.web.port = int(os.getenv("PORT"))
        if os.getenv("HOST"):
            self.web.host = os.getenv("HOST")
    
    def validate(self) -> bool:
        """验证配置"""
        if not self.telegram.token:
            raise ValueError("TELEGRAM_TOKEN 环境变量未设置")
        return True
    
    def get_scout_settings(self) -> Dict[str, Any]:
        """获取扫描器设置"""
        return {
            "market": {
                "scan_interval": self.scout.scan_interval,
                "max_workers": self.scout.max_workers,
                "timeout": self.scout.timeout,
                "retry_attempts": self.scout.retry_attempts
            }
        }
    
    def get_enabled_scouts(self) -> Dict[str, Dict[str, Any]]:
        """获取启用的扫描器"""
        return {
            "market": {
                "enabled": True,
                "workers": self.scout.max_workers
            }
        }

# 全局配置实例
settings = Settings()
