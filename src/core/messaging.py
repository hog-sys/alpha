# src/core/messaging_enhanced.py
"""
增强版消息队列系统 - 根据PDF建议实现完整的发布/订阅模式
支持优先级队列、路由和消息持久化
"""
import asyncio
import json
import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from enum import Enum

import aio_pika
from aio_pika import Message, DeliveryMode, ExchangeType
from aio_pika.abc import AbstractRobustConnection, AbstractChannel
from aio_pika.pool import Pool

logger = logging.getLogger(__name__)

class MessagePriority(Enum):
    """消息优先级"""
    LOW = 0
    NORMAL = 5
    HIGH = 10
    CRITICAL = 15

class MessageBus:
    """
    增强版消息总线 - 实现PDF中建议的解耦架构
    支持多种交换机类型和高级路由
    """
    
    def __init__(self, amqp_url: str):
        self.amqp_url = amqp_url
        self.connection_pool: Pool = Pool(self.get_connection, max_size=10)
        self.channel_pool: Pool = Pool(self.get_channel, max_size=20)
        self.exchanges = {}
        self.queues = {}
        logger.info("🚀 增强版消息总线初始化")

    async def get_connection(self) -> AbstractRobustConnection:
        """获取健壮的RabbitMQ连接"""
        return await aio_pika.connect_robust(
            self.amqp_url,
            connection_class=aio_pika.RobustConnection,
            reconnect_interval=5,
            fail_fast=False
        )

    async def get_channel(self) -> AbstractChannel:
        """获取通道并设置QoS"""
        async with self.connection_pool.acquire() as connection:
            channel = await connection.channel()
            # 设置预取数量，避免单个消费者被大量消息淹没
            await channel.set_qos(prefetch_count=10)
            return channel

    async def setup_infrastructure(self):
        """
        设置消息基础设施 - 根据PDF建议创建不同的交换机和队列
        """
        async with self.channel_pool.acquire() as channel:
            # 1. 创建主题交换机用于路由不同类型的Alpha信号
            self.exchanges['alpha_signals'] = await channel.declare_exchange(
                'alpha_signals',
                ExchangeType.TOPIC,
                durable=True
            )
            
            # 2. 创建直连交换机用于特定任务
            self.exchanges['tasks'] = await channel.declare_exchange(
                'tasks',
                ExchangeType.DIRECT,
                durable=True
            )
            
            # 3. 创建扇出交换机用于广播
            self.exchanges['broadcasts'] = await channel.declare_exchange(
                'broadcasts',
                ExchangeType.FANOUT,
                durable=True
            )
            
            # 4. 创建优先级队列用于高价值机会
            self.queues['high_priority_opportunities'] = await channel.declare_queue(
                'high_priority_opportunities',
                durable=True,
                arguments={
                    'x-max-priority': 10,  # 支持10级优先级
                    'x-message-ttl': 300000  # 5分钟TTL
                }
            )
            
            # 5. 创建不同类型机会的专用队列
            opportunity_types = ['arbitrage', 'volume_spike', 'new_pool', 'whale_movement']
            for opp_type in opportunity_types:
                queue = await channel.declare_queue(
                    f'opportunities.{opp_type}',
                    durable=True,
                    arguments={'x-message-ttl': 600000}  # 10分钟TTL
                )
                # 绑定到主题交换机
                await queue.bind(
                    self.exchanges['alpha_signals'],
                    routing_key=f'opportunity.{opp_type}.*'
                )
                self.queues[f'opportunities.{opp_type}'] = queue
            
            logger.info("✅ 消息基础设施设置完成")

    async def publish_opportunity(
        self, 
        opportunity: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL
    ):
        """
        发布机会到消息总线，支持智能路由
        """
        async with self.channel_pool.acquire() as channel:
            try:
                signal_type = opportunity.get('signal_type', 'unknown')
                confidence = opportunity.get('confidence', 0)
                
                # 添加元数据
                opportunity['published_at'] = datetime.now().isoformat()
                opportunity['message_id'] = f"{signal_type}_{datetime.now().timestamp()}"
                
                # 智能路由决策
                routing_key = f"opportunity.{signal_type}.{opportunity.get('symbol', 'unknown')}"
                
                # 根据置信度调整优先级
                if confidence > 0.9:
                    priority = MessagePriority.CRITICAL
                elif confidence > 0.7:
                    priority = MessagePriority.HIGH
                
                # 创建持久化消息
                message = Message(
                    body=json.dumps(opportunity, default=str).encode(),
                    delivery_mode=DeliveryMode.PERSISTENT,
                    priority=priority.value,
                    content_type='application/json',
                    headers={
                        'signal_type': signal_type,
                        'confidence': confidence,
                        'scout': opportunity.get('scout_name', 'unknown')
                    }
                )
                
                # 发布到主题交换机
                exchange = self.exchanges.get('alpha_signals')
                if exchange:
                    await exchange.publish(message, routing_key=routing_key)
                    
                    # 高优先级机会同时发送到优先级队列
                    if priority.value >= MessagePriority.HIGH.value:
                        await channel.default_exchange.publish(
                            message,
                            routing_key='high_priority_opportunities'
                        )
                    
                    logger.debug(f"📤 发布机会: {signal_type} (优先级: {priority.name})")
                
            except Exception as e:
                logger.error(f"发布机会失败: {e}", exc_info=True)

    async def subscribe(
        self,
        queue_name: str,
        callback: Callable,
        auto_ack: bool = False
    ):
        """
        订阅队列消息
        """
        async with self.channel_pool.acquire() as channel:
            queue = await channel.declare_queue(queue_name, durable=True)
            
            async def process_message(message: aio_pika.IncomingMessage):
                async with message.process(requeue=not auto_ack):
                    try:
                        body = json.loads(message.body.decode())
                        await callback(body, message.headers)
                    except Exception as e:
                        logger.error(f"处理消息失败: {e}")
                        if not auto_ack:
                            # 重新入队失败的消息
                            await message.nack(requeue=True)
            
            await queue.consume(process_message)
            logger.info(f"✅ 开始订阅队列: {queue_name}")

    async def get_queue_stats(self) -> Dict[str, Any]:
        """
        获取队列统计信息
        """
        stats = {}
        async with self.channel_pool.acquire() as channel:
            for queue_name, queue in self.queues.items():
                try:
                    declaration = await channel.declare_queue(
                        queue.name,
                        passive=True  # 只查询，不创建
                    )
                    stats[queue_name] = {
                        'messages': declaration.declaration_result.message_count,
                        'consumers': declaration.declaration_result.consumer_count
                    }
                except Exception as e:
                    logger.error(f"获取队列 {queue_name} 统计失败: {e}")
        
        return stats

    async def close(self):
        """关闭所有连接"""
        await self.channel_pool.close()
        await self.connection_pool.close()
        logger.info("消息总线已关闭")


class OpportunityRouter:
    """
    机会路由器 - 实现PDF中建议的智能路由逻辑
    """
    
    def __init__(self, message_bus: MessageBus):
        self.message_bus = message_bus
        self.routing_rules = self._setup_routing_rules()
    
    def _setup_routing_rules(self) -> Dict[str, Callable]:
        """设置路由规则"""
        return {
            'arbitrage': self._route_arbitrage,
            'volume_spike': self._route_volume_spike,
            'new_pool': self._route_new_pool,
            'whale_movement': self._route_whale_movement,
            'gas_anomaly': self._route_gas_anomaly
        }
    
    async def route_opportunity(self, opportunity: Dict[str, Any]):
        """
        根据机会类型进行智能路由
        """
        signal_type = opportunity.get('signal_type', 'unknown')
        
        if signal_type in self.routing_rules:
            await self.routing_rules[signal_type](opportunity)
        else:
            # 默认路由
            await self.message_bus.publish_opportunity(
                opportunity,
                MessagePriority.NORMAL
            )
    
    async def _route_arbitrage(self, opportunity: Dict[str, Any]):
        """路由套利机会 - 高优先级"""
        profit_pct = opportunity.get('data', {}).get('profit_pct', 0)
        
        # 根据利润率设置优先级
        if profit_pct > 1.0:
            priority = MessagePriority.CRITICAL
        elif profit_pct > 0.5:
            priority = MessagePriority.HIGH
        else:
            priority = MessagePriority.NORMAL
        
        await self.message_bus.publish_opportunity(opportunity, priority)
    
    async def _route_volume_spike(self, opportunity: Dict[str, Any]):
        """路由成交量激增机会"""
        volume_ratio = opportunity.get('data', {}).get('volume_ratio', 1)
        
        if volume_ratio > 5:
            priority = MessagePriority.HIGH
        else:
            priority = MessagePriority.NORMAL
        
        await self.message_bus.publish_opportunity(opportunity, priority)
    
    async def _route_new_pool(self, opportunity: Dict[str, Any]):
        """路由新池子机会 - 通常高优先级"""
        tvl = opportunity.get('data', {}).get('tvl_usd', 0)
        
        if tvl > 1000000:  # TVL > $1M
            priority = MessagePriority.HIGH
        else:
            priority = MessagePriority.NORMAL
        
        await self.message_bus.publish_opportunity(opportunity, priority)
    
    async def _route_whale_movement(self, opportunity: Dict[str, Any]):
        """路由巨鲸转账机会"""
        value_usd = opportunity.get('data', {}).get('value_usd', 0)
        
        if value_usd > 10000000:  # > $10M
            priority = MessagePriority.CRITICAL
        elif value_usd > 1000000:  # > $1M
            priority = MessagePriority.HIGH
        else:
            priority = MessagePriority.NORMAL
        
        await self.message_bus.publish_opportunity(opportunity, priority)
    
    async def _route_gas_anomaly(self, opportunity: Dict[str, Any]):
        """路由Gas异常机会"""
        deviation = opportunity.get('data', {}).get('deviation', 0)
        
        if abs(deviation) > 3:  # 超过3个标准差
            priority = MessagePriority.HIGH
        else:
            priority = MessagePriority.NORMAL
        
        await self.message_bus.publish_opportunity(opportunity, priority)
