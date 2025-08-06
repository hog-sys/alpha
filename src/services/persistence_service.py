# src/services/persistence_service.py
import asyncio
import json
import logging
from typing import Dict, Any

import aio_pika
from aio_pika.abc import AbstractIncomingMessage
from sqlalchemy import insert

from config.settings import settings
from src.core.database import engine, opportunities_table

logger = logging.getLogger(__name__)

class PersistenceService:
    """
    负责从RabbitMQ消费机会数据，并将其持久化到TimescaleDB。
    """
    def __init__(self):
        self.amqp_url = settings.RABBITMQ_URL
        self.db_engine = engine
        self.connection = None
        self.channel = None
        self.queue_name = "opportunities_raw"

    async def run(self):
        """启动服务并持续运行"""
        logger.info("🚀 持久化服务启动中...")
        if not self.db_engine:
            logger.critical("❌ 数据库引擎未初始化，持久化服务无法启动。")
            return
            
        while True:
            try:
                self.connection = await aio_pika.connect_robust(self.amqp_url)
                async with self.connection:
                    self.channel = await self.connection.channel()
                    # 设置QoS，确保一次只处理一条消息，处理完再取下一条
                    await self.channel.set_qos(prefetch_count=1)

                    queue = await self.channel.declare_queue(
                        self.queue_name,
                        durable=True # 确保队列持久化
                    )
                    
                    logger.info(f"✅ 持久化服务已连接到RabbitMQ，正在监听队列 '{self.queue_name}'...")
                    
                    async with queue.iterator() as queue_iter:
                        async for message in queue_iter:
                            await self.on_message(message)

            except aio_pika.exceptions.AMQPConnectionError as e:
                logger.error(f"RabbitMQ连接失败，将在10秒后重试... 错误: {e}")
                await asyncio.sleep(10)
            except Exception as e:
                logger.critical(f"持久化服务发生严重错误: {e}", exc_info=True)
                await asyncio.sleep(10) # 发生未知错误后等待

    async def on_message(self, message: AbstractIncomingMessage):
        """处理收到的每一条消息"""
        async with message.process(): # 使用上下文管理器确保消息最终被应答
            try:
                body = message.body.decode()
                data = json.loads(body)

                # 验证数据（可以添加更复杂的验证逻辑）
                if not all(k in data for k in ['id', 'scout_name', 'symbol', 'timestamp']):
                    logger.warning(f"收到格式错误的消息，已忽略: {data}")
                    return # 消息格式不对，直接确认并丢弃

                # 准备插入数据库
                stmt = insert(opportunities_table).values(
                    id=data['id'],
                    scout_name=data['scout_name'],
                    signal_type=data['signal_type'],
                    symbol=data['symbol'],
                    confidence=data['confidence'],
                    data=data['data'], # 直接将字典存入JSONB字段
                    timestamp=data['timestamp'],
                    expires_at=data.get('expires_at')
                )
                
                # 执行插入操作
                async with self.db_engine.connect() as conn:
                    await conn.execute(stmt)
                    await conn.commit()
                
                logger.debug(f"成功将机会 {data['id']} 存入数据库。")

            except json.JSONDecodeError:
                logger.error(f"无法解析JSON消息: {message.body.decode()}")
            except Exception as e:
                logger.error(f"处理消息时发生数据库错误: {e}", exc_info=True)
                # 这里可以选择不应答消息，让它稍后被重新投递
                # 但为了避免无限循环，暂时还是确认掉
                pass


async def start_persistence_service():
    """服务的独立启动入口"""
    service = PersistenceService()
    await service.run()

if __name__ == "__main__":
    # 这个部分允许你独立运行这个服务进行测试
    logging.basicConfig(level=logging.INFO)
    asyncio.run(start_persistence_service())
