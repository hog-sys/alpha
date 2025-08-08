#!/usr/bin/env python3
# scripts/setup-secrets.py
"""
Infisical 密钥设置脚本 - 自动创建项目和密钥
"""
import asyncio
import aiohttp
import json
import logging
import os
import sys
from typing import Dict, Any, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class InfisicalClient:
    """Infisical API 客户端"""
    
    def __init__(self, base_url: str = "http://localhost:8090"):
        self.base_url = base_url
        self.session = None
        self.token = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def login(self, email: str, password: str) -> bool:
        """登录获取访问令牌"""
        try:
            async with self.session.post(
                f"{self.base_url}/api/v1/auth/login",
                json={"email": email, "password": password}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self.token = data.get("token")
                    logger.info("✅ 成功登录 Infisical")
                    return True
                else:
                    logger.error(f"登录失败: {response.status}")
                    return False
        except Exception as e:
            logger.error(f"登录异常: {e}")
            return False
    
    async def create_project(self, name: str, description: str = "") -> Optional[str]:
        """创建项目"""
        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            async with self.session.post(
                f"{self.base_url}/api/v1/projects",
                json={
                    "name": name,
                    "description": description
                },
                headers=headers
            ) as response:
                if response.status == 201:
                    data = await response.json()
                    project_id = data.get("project", {}).get("id")
                    logger.info(f"✅ 创建项目成功: {name} (ID: {project_id})")
                    return project_id
                else:
                    logger.error(f"创建项目失败: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"创建项目异常: {e}")
            return None
    
    async def create_secret(
        self, 
        project_id: str, 
        environment: str, 
        key: str, 
        value: str,
        description: str = ""
    ) -> bool:
        """创建密钥"""
        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            async with self.session.post(
                f"{self.base_url}/api/v1/secrets",
                json={
                    "projectId": project_id,
                    "environment": environment,
                    "key": key,
                    "value": value,
                    "comment": description
                },
                headers=headers
            ) as response:
                if response.status == 201:
                    logger.info(f"✅ 创建密钥成功: {key} (环境: {environment})")
                    return True
                else:
                    logger.error(f"创建密钥失败: {response.status}")
                    return False
        except Exception as e:
            logger.error(f"创建密钥异常: {e}")
            return False
    
    async def get_projects(self) -> list:
        """获取项目列表"""
        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            async with self.session.get(
                f"{self.base_url}/api/v1/projects",
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("projects", [])
                else:
                    logger.error(f"获取项目列表失败: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"获取项目列表异常: {e}")
            return []

async def setup_crypto_scout_secrets():
    """设置 Crypto Alpha Scout 的密钥"""
    
    # 配置
    infisical_url = os.getenv("INFISICAL_URL", "http://localhost:8090")
    admin_email = os.getenv("INFISICAL_ADMIN_EMAIL", "admin@cryptoalphascout.com")
    admin_password = os.getenv("INFISICAL_ADMIN_PASSWORD", "SecureAdmin123!")
    
    # 等待 Infisical 启动
    logger.info("等待 Infisical 服务启动...")
    await asyncio.sleep(30)  # 给服务一些启动时间
    
    async with InfisicalClient(infisical_url) as client:
        # 登录
        if not await client.login(admin_email, admin_password):
            logger.error("无法登录，请检查管理员凭据")
            return False
        
        # 检查是否已存在项目
        projects = await client.get_projects()
        existing_project = None
        for project in projects:
            if project.get("name") == "crypto-alpha-scout":
                existing_project = project
                break
        
        if existing_project:
            project_id = existing_project["id"]
            logger.info(f"使用现有项目: {project_id}")
        else:
            # 创建主项目
            project_id = await client.create_project(
                name="crypto-alpha-scout",
                description="Crypto Alpha Scout 主项目 - 所有服务的密钥管理"
            )
            
            if not project_id:
                logger.error("无法创建项目")
                return False
        
        # 定义密钥配置
        secrets_config = {
            "production": {
                # 数据库配置
                "DATABASE_URL": "postgresql://crypto_user:crypto_pass@timescaledb:5432/crypto_scout",
                "REDIS_URL": "redis://redis:6379/0",
                
                # 消息队列
                "RABBITMQ_URL": "amqp://crypto_user:crypto_pass@rabbitmq:5672/",
                "RABBITMQ_USER": "crypto_user",
                "RABBITMQ_PASS": "crypto_pass",
                
                # API密钥
                "ETHERSCAN_API_KEY": os.getenv("ETHERSCAN_API_KEY", "YOUR_ETHERSCAN_API_KEY"),
                "GOPLUS_API_KEY": os.getenv("GOPLUS_API_KEY", "YOUR_GOPLUS_API_KEY"),
                "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN"),
                
                # 安全配置
                "JWT_SECRET": os.getenv("JWT_SECRET", "your-super-secret-jwt-key-here"),
                "ENCRYPTION_KEY": os.getenv("ENCRYPTION_KEY", "your-32-char-encryption-key-here"),
                
                # 服务配置
                "WEB_PORT": "8000",
                "LOG_LEVEL": "INFO",
                "ENVIRONMENT": "production"
            },
            "development": {
                # 开发环境配置
                "DATABASE_URL": "postgresql://crypto_user:crypto_pass@localhost:5432/crypto_scout_dev",
                "REDIS_URL": "redis://localhost:6379/1",
                "RABBITMQ_URL": "amqp://crypto_user:crypto_pass@localhost:5672/",
                "LOG_LEVEL": "DEBUG",
                "ENVIRONMENT": "development"
            }
        }
        
        # 创建密钥
        success_count = 0
        total_count = 0
        
        for environment, secrets in secrets_config.items():
            logger.info(f"设置 {environment} 环境的密钥...")
            
            for key, value in secrets.items():
                total_count += 1
                if await client.create_secret(
                    project_id=project_id,
                    environment=environment,
                    key=key,
                    value=value,
                    description=f"Crypto Alpha Scout - {key}"
                ):
                    success_count += 1
                
                # 避免请求过快
                await asyncio.sleep(0.5)
        
        logger.info(f"✅ 密钥设置完成: {success_count}/{total_count} 成功")
        
        # 输出访问信息
        print("\n" + "="*60)
        print("🔐 Infisical 密钥管理系统已设置完成")
        print("="*60)
        print(f"Web界面: {infisical_url}")
        print(f"管理员邮箱: {admin_email}")
        print(f"项目名称: crypto-alpha-scout")
        print(f"项目ID: {project_id}")
        print("\n请妥善保存这些信息！")
        print("="*60)
        
        return True

async def main():
    """主函数"""
    try:
        success = await setup_crypto_scout_secrets()
        if success:
            logger.info("🎉 密钥设置完成")
            sys.exit(0)
        else:
            logger.error("❌ 密钥设置失败")
            sys.exit(1)
    except Exception as e:
        logger.error(f"设置过程中发生错误: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
