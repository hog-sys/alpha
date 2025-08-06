# src/base_scout.py

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import asyncio
import logging
import aiohttp
from dataclasses import dataclass, asdict
import uuid
import json

# 修复：使用绝对路径导入，解决模块查找问题
from src.core.messaging import Publisher
from config.settings import settings

logger = logging.getLogger(__name__)

@dataclass
class OpportunitySignal:
    """机会信号数据类"""
    id: str
    scout_name: str
    signal_type: str
    symbol: str
    confidence: float
    data: Dict[str, Any]
    timestamp: datetime
    expires_at: Optional[datetime] = None

    def to_dict(self):
        """将对象转换为字典，处理日期时间格式"""
        d = asdict(self)
        d['timestamp'] = d['timestamp'].isoformat()
        if d.get('expires_at'):
            d['expires_at'] = d['expires_at'].isoformat()
        return d

    def to_json(self):
        """将对象转换为JSON字符串"""
        return json.dumps(self.to_dict())

class BaseScout(ABC):
    """所有Scout的基类"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = self.__class__.__name__.replace('Scout', '').lower()
        self.session: Optional[aiohttp.ClientSession] = None
        self.running = False
        self.publisher = Publisher(settings.RABBITMQ_URL)

    async def initialize(self):
        """初始化Scout"""
        timeout = aiohttp.ClientTimeout(total=30)
        connector = aiohttp.TCPConnector(limit=100, ttl_dns_cache=300)
        self.session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        await self._initialize()
        self.running = True
        logger.info(f"✅ {self.name} Scout 初始化完成")

    @abstractmethod
    async def _initialize(self):
        """子类特定的初始化逻辑"""
        pass

    @abstractmethod
    async def scan(self) -> List[OpportunitySignal]:
        """执行扫描，返回发现的机会信号列表"""
        pass

    async def publish_opportunities(self, opportunities: List[OpportunitySignal]):
        """将一批机会发布到消息队列"""
        if not opportunities:
            return
        queue_name = "opportunities_raw"
        tasks = [self.publisher.publish(queue_name, opp.to_dict()) for opp in opportunities]
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.debug(f"发布了 {len(opportunities)} 个机会到队列 '{queue_name}'")

    def create_opportunity(
        self,
        signal_type: str,
        symbol: str,
        confidence: float,
        data: Dict[str, Any],
        expires_in_minutes: int = 5
    ) -> OpportunitySignal:
        """创建机会信号对象"""
        return OpportunitySignal(
            id=str(uuid.uuid4()),
            scout_name=self.name,
            signal_type=signal_type,
            symbol=symbol,
            confidence=min(max(confidence, 0), 1),
            data=data,
            timestamp=datetime.now(),
            expires_at=datetime.now() + timedelta(minutes=expires_in_minutes)
        )

    async def cleanup(self):
        """清理资源"""
        self.running = False
        if self.session:
            await self.session.close()
        if self.publisher:
            await self.publisher.close()
        logger.info(f"✅ {self.name} Scout 已清理")
