#!/usr/bin/env python3
# scripts/infisical-integration.py
"""
Infisical 集成模块 - 在运行时从 Infisical 获取密钥
"""
import os
import asyncio
import aiohttp
import logging
import json
from typing import Dict, Any, Optional
from pathlib import Path
import sys

# 添加项目根目录到路径
sys.path.append(str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)

class InfisicalSecretManager:
    """Infisical 密钥管理器"""
    
    def __init__(
        self,
        infisical_url: str = None,
        project_id: str = None,
        environment: str = "production",
        service_token: str = None
    ):
        self.infisical_url = infisical_url or os.getenv("INFISICAL_URL", "http://infisical:8080")
        self.project_id = project_id or os.getenv("INFISICAL_PROJECT_ID")
        self.environment = environment or os.getenv("ENVIRONMENT", "production")
        self.service_token = service_token or os.getenv("INFISICAL_SERVICE_TOKEN")
        
        self.session = None
        self.secrets_cache = {}
        self.cache_ttl = 300  # 5分钟缓存
        self.last_fetch = 0
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def fetch_secrets(self, force_refresh: bool = False) -> Dict[str, str]:
        """从 Infisical 获取密钥"""
        import time
        current_time = time.time()
        
        # 检查缓存
        if not force_refresh and (current_time - self.last_fetch) < self.cache_ttl:
            if self.secrets_cache:
                logger.debug("使用缓存的密钥")
                return self.secrets_cache
        
        try:
            if not self.service_token:
                logger.warning("未提供 Infisical service token，使用环境变量")
                return dict(os.environ)
            
            headers = {
                "Authorization": f"Bearer {self.service_token}",
                "Content-Type": "application/json"
            }
            
            url = f"{self.infisical_url}/api/v1/secrets"
            params = {
                "projectId": self.project_id,
                "environment": self.environment
            }
            
            async with self.session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    secrets = {}
                    
                    for secret in data.get("secrets", []):
                        key = secret.get("key")
                        value = secret.get("value")
                        if key and value:
                            secrets[key] = value
                    
                    # 更新缓存
                    self.secrets_cache = secrets
                    self.last_fetch = current_time
                    
                    logger.info(f"✅ 从 Infisical 获取到 {len(secrets)} 个密钥")
                    return secrets
                    
                elif response.status == 401:
                    logger.error("Infisical 认证失败，检查 service token")
                    return dict(os.environ)
                    
                else:
                    logger.error(f"获取密钥失败: HTTP {response.status}")
                    return dict(os.environ)
                    
        except aiohttp.ClientConnectorError:
            logger.warning("无法连接到 Infisical，使用环境变量")
            return dict(os.environ)
            
        except Exception as e:
            logger.error(f"获取密钥异常: {e}")
            return dict(os.environ)
    
    async def get_secret(self, key: str, default: str = None) -> Optional[str]:
        """获取单个密钥"""
        secrets = await self.fetch_secrets()
        return secrets.get(key, default)
    
    async def inject_secrets_to_env(self) -> int:
        """将密钥注入到环境变量中"""
        secrets = await self.fetch_secrets()
        count = 0
        
        for key, value in secrets.items():
            if key not in os.environ:  # 不覆盖已存在的环境变量
                os.environ[key] = value
                count += 1
        
        logger.info(f"✅ 注入 {count} 个密钥到环境变量")
        return count

class InfisicalConfig:
    """基于 Infisical 的配置管理器"""
    
    def __init__(self, secret_manager: InfisicalSecretManager = None):
        self.secret_manager = secret_manager or InfisicalSecretManager()
        self._config_cache = {}
    
    async def get(self, key: str, default: Any = None, cast_type: type = str) -> Any:
        """获取配置值"""
        if key in self._config_cache:
            return self._config_cache[key]
        
        # 首先尝试从环境变量获取
        value = os.getenv(key)
        
        # 如果环境变量中没有，从 Infisical 获取
        if value is None:
            value = await self.secret_manager.get_secret(key, default)
        
        # 类型转换
        if value is not None and cast_type != str:
            try:
                if cast_type == bool:
                    value = value.lower() in ('true', '1', 'yes', 'on')
                elif cast_type == int:
                    value = int(value)
                elif cast_type == float:
                    value = float(value)
                elif cast_type == list:
                    value = value.split(',') if isinstance(value, str) else value
            except (ValueError, TypeError):
                logger.warning(f"无法将 {key}={value} 转换为 {cast_type}")
                value = default
        
        # 缓存结果
        self._config_cache[key] = value
        return value
    
    async def get_database_url(self) -> str:
        """获取数据库连接URL"""
        return await self.get("DATABASE_URL", "sqlite:///crypto_scout.db")
    
    async def get_rabbitmq_url(self) -> str:
        """获取RabbitMQ连接URL"""
        return await self.get("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
    
    async def get_redis_url(self) -> str:
        """获取Redis连接URL"""
        return await self.get("REDIS_URL", "redis://localhost:6379/0")
    
    async def get_telegram_token(self) -> str:
        """获取Telegram Bot Token"""
        return await self.get("TELEGRAM_BOT_TOKEN")
    
    async def get_api_keys(self) -> Dict[str, str]:
        """获取所有API密钥"""
        return {
            "etherscan": await self.get("ETHERSCAN_API_KEY"),
            "goplus": await self.get("GOPLUS_API_KEY"),
        }

# 全局配置实例
_global_config = None

async def get_config() -> InfisicalConfig:
    """获取全局配置实例"""
    global _global_config
    if _global_config is None:
        secret_manager = InfisicalSecretManager()
        async with secret_manager:
            await secret_manager.inject_secrets_to_env()
        _global_config = InfisicalConfig(secret_manager)
    return _global_config

async def init_secrets():
    """初始化密钥管理 - 在应用启动时调用"""
    try:
        secret_manager = InfisicalSecretManager()
        async with secret_manager:
            count = await secret_manager.inject_secrets_to_env()
            logger.info(f"🔐 密钥管理初始化完成，注入 {count} 个密钥")
            return True
    except Exception as e:
        logger.error(f"密钥管理初始化失败: {e}")
        logger.info("将使用环境变量作为备选方案")
        return False

# 便捷函数
async def get_secret(key: str, default: str = None) -> Optional[str]:
    """便捷函数：获取单个密钥"""
    config = await get_config()
    return await config.get(key, default)

if __name__ == "__main__":
    # 测试脚本
    async def test():
        print("🔐 测试 Infisical 集成...")
        
        await init_secrets()
        
        config = await get_config()
        
        # 测试获取配置
        db_url = await config.get_database_url()
        print(f"数据库URL: {db_url}")
        
        mq_url = await config.get_rabbitmq_url()
        print(f"消息队列URL: {mq_url}")
        
        api_keys = await config.get_api_keys()
        print(f"API密钥数量: {len([k for k, v in api_keys.items() if v])}")
        
        print("✅ 测试完成")
    
    asyncio.run(test())
