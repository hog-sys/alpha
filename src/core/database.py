# src/core/database_timescale.py
"""
TimescaleDB数据库架构 - 根据PDF建议实现时间序列数据库
支持超表、连续聚合和数据生命周期管理
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import (
    create_engine, MetaData, Table, Column, 
    Text, Float, DateTime, JSON, Integer, 
    BigInteger, Boolean, Index, select, text
)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import JSONB, UUID
import uuid

logger = logging.getLogger(__name__)

class TimescaleDBManager:
    """
    TimescaleDB管理器 - 实现PDF中建议的时间序列数据架构
    """
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = None
        self.async_session = None
        self.metadata = MetaData()
        
        # 定义表结构
        self._define_tables()
    
    def _define_tables(self):
        """根据PDF建议定义数据库表结构"""
        
        # 1. 代币静态元数据表（普通表）
        self.tokens_table = Table(
            'tokens',
            self.metadata,
            Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            Column('symbol', Text, unique=True, nullable=False),
            Column('name', Text),
            Column('contract_address', Text),
            Column('chain', Text),
            Column('github_repo_url', Text),
            Column('website_url', Text),
            Column('twitter_handle', Text),
            Column('created_at', DateTime(timezone=True), default=datetime.utcnow),
            Column('updated_at', DateTime(timezone=True), onupdate=datetime.utcnow)
        )
        
        # 2. 市场数据超表（Hypertable）
        self.market_data_table = Table(
            'market_data',
            self.metadata,
            Column('time', DateTime(timezone=True), nullable=False),
            Column('token_id', UUID(as_uuid=True), nullable=False),
            Column('exchange', Text, nullable=False),
            Column('price', Float, nullable=False),
            Column('volume', Float),
            Column('bid', Float),
            Column('ask', Float),
            Column('spread', Float),
            Column('open', Float),
            Column('high', Float),
            Column('low', Float),
            Column('close', Float),
            Index('idx_market_data_time', 'time'),
            Index('idx_market_data_token', 'token_id'),
            Index('idx_market_data_exchange', 'exchange')
        )
        
        # 3. 链上事件超表
        self.onchain_events_table = Table(
            'onchain_events',
            self.metadata,
            Column('time', DateTime(timezone=True), nullable=False),
            Column('token_id', UUID(as_uuid=True)),
            Column('chain', Text, nullable=False),
            Column('event_type', Text, nullable=False),
            Column('tx_hash', Text, unique=True),
            Column('block_number', BigInteger),
            Column('from_address', Text),
            Column('to_address', Text),
            Column('value', Float),
            Column('gas_used', BigInteger),
            Column('event_details', JSONB),
            Index('idx_onchain_time', 'time'),
            Index('idx_onchain_event_type', 'event_type'),
            Index('idx_onchain_chain', 'chain')
        )
        
        # 4. Alpha机会超表（包含SHAP值）
        self.alpha_opportunities_table = Table(
            'alpha_opportunities',
            self.metadata,
            Column('time', DateTime(timezone=True), nullable=False),
            Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
            Column('token_id', UUID(as_uuid=True)),
            Column('scout_type', Text, nullable=False),
            Column('signal_type', Text, nullable=False),
            Column('alpha_score', Float, nullable=False),
            Column('confidence', Float),
            Column('prediction_details', JSONB),  # 存储SHAP值
            Column('opportunity_data', JSONB),
            Column('expires_at', DateTime(timezone=True)),
            Column('executed', Boolean, default=False),
            Column('execution_result', JSONB),
            Index('idx_alpha_time', 'time'),
            Index('idx_alpha_score', 'alpha_score'),
            Index('idx_alpha_scout', 'scout_type')
        )
        
        # 5. 社交情绪数据超表（新增）
        self.social_sentiment_table = Table(
            'social_sentiment',
            self.metadata,
            Column('time', DateTime(timezone=True), nullable=False),
            Column('token_id', UUID(as_uuid=True)),
            Column('platform', Text, nullable=False),  # twitter, reddit, telegram
            Column('mentions_count', Integer),
            Column('sentiment_score', Float),  # -1 到 1
            Column('positive_count', Integer),
            Column('negative_count', Integer),
            Column('neutral_count', Integer),
            Column('influencer_mentions', Integer),
            Column('trending_rank', Integer),
            Column('raw_data', JSONB),
            Index('idx_sentiment_time', 'time'),
            Index('idx_sentiment_platform', 'platform')
        )
        
        # 6. 开发者活动数据超表（新增）
        self.developer_activity_table = Table(
            'developer_activity',
            self.metadata,
            Column('time', DateTime(timezone=True), nullable=False),
            Column('token_id', UUID(as_uuid=True)),
            Column('github_repo', Text),
            Column('commits_count', Integer),
            Column('pull_requests_open', Integer),
            Column('pull_requests_closed', Integer),
            Column('issues_open', Integer),
            Column('issues_closed', Integer),
            Column('contributors_count', Integer),
            Column('stars_count', Integer),
            Column('forks_count', Integer),
            Column('activity_score', Float),  # 综合活跃度分数
            Index('idx_dev_activity_time', 'time'),
            Index('idx_dev_activity_repo', 'github_repo')
        )
    
    async def initialize(self):
        """初始化数据库连接并创建表"""
        try:
            # 创建异步引擎
            self.engine = create_async_engine(
                self.database_url,
                echo=False,
                pool_size=20,
                max_overflow=40,
                pool_pre_ping=True,
                pool_recycle=3600
            )
            
            # 创建会话工厂
            self.async_session = sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # 创建表
            async with self.engine.begin() as conn:
                await conn.run_sync(self.metadata.create_all)
                
                # 将表转换为TimescaleDB超表
                await self._create_hypertables(conn)
                
                # 创建连续聚合
                await self._create_continuous_aggregates(conn)
                
                # 设置数据保留策略
                await self._setup_retention_policies(conn)
            
            logger.info("✅ TimescaleDB初始化完成")
            
        except Exception as e:
            logger.error(f"TimescaleDB初始化失败: {e}")
            raise
    
    async def _create_hypertables(self, conn):
        """创建TimescaleDB超表"""
        hypertables = [
            ('market_data', 'time'),
            ('onchain_events', 'time'),
            ('alpha_opportunities', 'time'),
            ('social_sentiment', 'time'),
            ('developer_activity', 'time')
        ]
        
        for table_name, time_column in hypertables:
            try:
                # 检查是否已经是超表
                result = await conn.execute(
                    text(
                        "SELECT * FROM timescaledb_information.hypertables "
                        "WHERE hypertable_name = :table_name"
                    ),
                    {"table_name": table_name}
                )
                
                if not result.fetchone():
                    # 创建超表
                    await conn.execute(
                        text(f"SELECT create_hypertable('{table_name}', '{time_column}');")
                    )
                    logger.info(f"✅ 创建超表: {table_name}")
                    
                    # 设置分区间隔（7天）
                    await conn.execute(
                        text(
                            f"SELECT set_chunk_time_interval('{table_name}', "
                            f"INTERVAL '7 days');"
                        )
                    )
                    
            except Exception as e:
                logger.warning(f"创建超表 {table_name} 失败: {e}")
    
    async def _create_continuous_aggregates(self, conn):
        """创建连续聚合视图 - 提高查询性能"""
        try:
            # 1分钟OHLCV聚合
            await conn.execute(text("""
                CREATE MATERIALIZED VIEW IF NOT EXISTS market_data_1m
                WITH (timescaledb.continuous) AS
                SELECT
                    time_bucket('1 minute', time) AS bucket,
                    token_id,
                    exchange,
                    FIRST(price, time) AS open,
                    MAX(price) AS high,
                    MIN(price) AS low,
                    LAST(price, time) AS close,
                    SUM(volume) AS volume,
                    COUNT(*) AS tick_count
                FROM market_data
                GROUP BY bucket, token_id, exchange
                WITH NO DATA;
            """))
            
            # 添加刷新策略
            await conn.execute(text("""
                SELECT add_continuous_aggregate_policy('market_data_1m',
                    start_offset => INTERVAL '1 hour',
                    end_offset => INTERVAL '1 minute',
                    schedule_interval => INTERVAL '1 minute');
            """))
            
            # 小时级社交情绪聚合
            await conn.execute(text("""
                CREATE MATERIALIZED VIEW IF NOT EXISTS sentiment_hourly
                WITH (timescaledb.continuous) AS
                SELECT
                    time_bucket('1 hour', time) AS bucket,
                    token_id,
                    platform,
                    AVG(sentiment_score) AS avg_sentiment,
                    SUM(mentions_count) AS total_mentions,
                    MAX(trending_rank) AS best_rank
                FROM social_sentiment
                GROUP BY bucket, token_id, platform
                WITH NO DATA;
            """))
            
            logger.info("✅ 连续聚合视图创建完成")
            
        except Exception as e:
            logger.warning(f"创建连续聚合失败: {e}")
    
    async def _setup_retention_policies(self, conn):
        """设置数据保留策略"""
        policies = [
            ('market_data', 90),  # 保留90天的原始数据
            ('onchain_events', 180),  # 保留180天
            ('alpha_opportunities', 365),  # 保留1年
            ('social_sentiment', 30),  # 保留30天
            ('developer_activity', 365)  # 保留1年
        ]
        
        for table_name, days in policies:
            try:
                await conn.execute(
                    text(
                        f"SELECT add_retention_policy('{table_name}', "
                        f"INTERVAL '{days} days');"
                    )
                )
                logger.info(f"✅ 设置 {table_name} 保留策略: {days}天")
            except Exception as e:
                logger.warning(f"设置保留策略失败 {table_name}: {e}")
    
    async def insert_opportunity(self, opportunity: Dict[str, Any]):
        """插入Alpha机会"""
        async with self.async_session() as session:
            try:
                await session.execute(
                    self.alpha_opportunities_table.insert().values(
                        time=opportunity.get('timestamp', datetime.utcnow()),
                        token_id=opportunity.get('token_id'),
                        scout_type=opportunity.get('scout_name'),
                        signal_type=opportunity.get('signal_type'),
                        alpha_score=opportunity.get('confidence', 0),
                        confidence=opportunity.get('confidence'),
                        prediction_details=opportunity.get('shap_values'),
                        opportunity_data=opportunity.get('data'),
                        expires_at=opportunity.get('expires_at')
                    )
                )
                await session.commit()
            except Exception as e:
                logger.error(f"插入机会失败: {e}")
                await session.rollback()
    
    async def get_recent_opportunities(
        self, 
        hours: int = 24,
        min_score: float = 0.7
    ) -> List[Dict]:
        """获取最近的高分机会"""
        async with self.async_session() as session:
            since = datetime.utcnow() - timedelta(hours=hours)
            
            result = await session.execute(
                select(self.alpha_opportunities_table)
                .where(self.alpha_opportunities_table.c.time >= since)
                .where(self.alpha_opportunities_table.c.alpha_score >= min_score)
                .order_by(self.alpha_opportunities_table.c.alpha_score.desc())
                .limit(100)
            )
            
            return [dict(row) for row in result.mappings()]
    
    async def get_market_stats(self, token_id: UUID, hours: int = 24) -> Dict:
        """获取市场统计数据"""
        async with self.async_session() as session:
            since = datetime.utcnow() - timedelta(hours=hours)
            
            # 使用time_bucket进行时间聚合
            query = text("""
                SELECT 
                    time_bucket('1 hour', time) AS hour,
                    AVG(price) as avg_price,
                    MAX(price) as high,
                    MIN(price) as low,
                    SUM(volume) as total_volume
                FROM market_data
                WHERE token_id = :token_id 
                AND time >= :since
                GROUP BY hour
                ORDER BY hour DESC
            """)
            
            result = await session.execute(
                query,
                {"token_id": str(token_id), "since": since}
            )
            
            return {
                "hourly_data": [dict(row) for row in result.mappings()],
                "token_id": str(token_id),
                "period_hours": hours
            }
    
    async def close(self):
        """关闭数据库连接"""
        if self.engine:
            await self.engine.dispose()
            logger.info("TimescaleDB连接已关闭")