"""
实时数据分析器
"""
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from collections import deque
import logging
import json

logger = logging.getLogger(__name__)

class RealtimeAnalyzer:
    """实时数据分析器"""
    
    def __init__(self, config):
        self.config = config
        
        # 数据缓冲区
        self.price_buffer = {}  # symbol -> deque of prices
        self.opportunity_buffer = deque(maxlen=1000)  # 最近的机会
        self.metrics_buffer = {}  # 各种指标的缓冲
        
        # 分析参数
        self.window_size = 100  # 滑动窗口大小
        self.update_interval = 5  # 更新间隔（秒）
        
        # 统计数据
        self.stats = {
            'total_opportunities': 0,
            'successful_opportunities': 0,
            'total_profit': 0,
            'win_rate': 0,
            'best_performing_scout': None,
            'most_profitable_symbol': None
        }
        
    async def initialize(self):
        """初始化分析器"""
        logger.info("初始化实时分析器...")
        
        # 启动定期分析任务
        asyncio.create_task(self._periodic_analysis())
        
    async def add_price_data(self, symbol: str, price: float, timestamp: datetime):
        """添加价格数据"""
        if symbol not in self.price_buffer:
            self.price_buffer[symbol] = deque(maxlen=self.window_size)
            
        self.price_buffer[symbol].append({
            'price': price,
            'timestamp': timestamp
        })
    
    async def add_opportunity(self, opportunity: Dict):
        """添加新机会进行分析"""
        self.opportunity_buffer.append(opportunity)
        self.stats['total_opportunities'] += 1
        
        # 实时分析
        await self._analyze_opportunity(opportunity)
    
    async def _analyze_opportunity(self, opportunity: Dict):
        """分析单个机会"""
        # 计算技术指标
        symbol = opportunity.get('symbol')
        if symbol and symbol in self.price_buffer:
            prices = [p['price'] for p in self.price_buffer[symbol]]
            if len(prices) >= 20:
                # 计算简单指标
                sma_20 = np.mean(prices[-20:])
                current_price = prices[-1]
                
                # 价格相对于均线的位置
                price_position = (current_price - sma_20) / sma_20 * 100
                
                # 波动率
                volatility = np.std(prices[-20:]) / sma_20 * 100
                
                # 添加分析结果
                opportunity['analysis'] = {
                    'price_position': price_position,
                    'volatility': volatility,
                    'trend': 'up' if current_price > sma_20 else 'down'
                }
    
    async def _periodic_analysis(self):
        """定期执行综合分析"""
        while True:
            try:
                await asyncio.sleep(self.update_interval)
                
                # 分析最近的机会
                await self._analyze_recent_opportunities()
                
                # 计算市场指标
                await self._calculate_market_indicators()
                
                # 更新统计数据
                await self._update_statistics()
                
            except Exception as e:
                logger.error(f"定期分析失败: {e}")
    
    async def _analyze_recent_opportunities(self):
        """分析最近的机会"""
        if not self.opportunity_buffer:
            return
            
        # 转换为DataFrame进行分析
        df = pd.DataFrame(list(self.opportunity_buffer))
        
        # 按Scout分组统计
        scout_performance = df.groupby('scout_name').agg({
            'confidence': 'mean',
            'signal_type': 'count'
        }).rename(columns={'signal_type': 'count'})
        
        # 找出表现最好的Scout
        if not scout_performance.empty:
            best_scout = scout_performance['confidence'].idxmax()
            self.stats['best_performing_scout'] = best_scout
        
        # 按交易对分组统计
        if 'symbol' in df.columns:
            symbol_stats = df.groupby('symbol').agg({
                'confidence': 'mean',
                'signal_type': 'count'
            })
            
            if not symbol_stats.empty:
                most_active = symbol_stats['signal_type'].idxmax()
                self.stats['most_profitable_symbol'] = most_active
    
    async def _calculate_market_indicators(self):
        """计算市场指标"""
        indicators = {}
        
        # 计算各交易对的技术指标
        for symbol, price_data in self.price_buffer.items():
            if len(price_data) >= 20:
                prices = [p['price'] for p in price_data]
                
                # RSI
                rsi = self._calculate_rsi(prices)
                
                # MACD
                macd = self._calculate_macd(prices)
                
                # 布林带
                bb = self._calculate_bollinger_bands(prices)
                
                indicators[symbol] = {
                    'rsi': rsi,
                    'macd': macd,
                    'bollinger_bands': bb,
                    'last_price': prices[-1]
                }
        
        self.metrics_buffer['market_indicators'] = indicators
    
    def _calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """计算RSI指标"""
        if len(prices) < period + 1:
            return 50.0
            
        deltas = np.diff(prices)
        seed = deltas[:period]
        up = seed[seed >= 0].sum() / period
        down = -seed[seed < 0].sum() / period
        
        if down == 0:
            return 100.0
            
        rs = up / down
        rsi = 100 - (100 / (1 + rs))
        
        return float(rsi)
    
    def _calculate_macd(self, prices: List[float]) -> Dict[str, float]:
        """计算MACD指标"""
        if len(prices) < 26:
            return {'macd': 0, 'signal': 0, 'histogram': 0}
            
        # 简化的MACD计算
        ema_12 = self._calculate_ema(prices, 12)
        ema_26 = self._calculate_ema(prices, 26)
        
        macd_line = ema_12 - ema_26
        signal_line = self._calculate_ema([macd_line], 9)
        histogram = macd_line - signal_line
        
        return {
            'macd': float(macd_line),
            'signal': float(signal_line),
            'histogram': float(histogram)
        }
    
    def _calculate_ema(self, prices: List[float], period: int) -> float:
        """计算指数移动平均"""
        if len(prices) < period:
            return prices[-1] if prices else 0
            
        multiplier = 2 / (period + 1)
        ema = prices[0]
        
        for price in prices[1:]:
            ema = (price - ema) * multiplier + ema
            
        return ema
    
    def _calculate_bollinger_bands(self, prices: List[float], period: int = 20, std_dev: int = 2) -> Dict[str, float]:
        """计算布林带"""
        if len(prices) < period:
            current_price = prices[-1] if prices else 0
            return {
                'upper': current_price,
                'middle': current_price,
                'lower': current_price
            }
            
        sma = np.mean(prices[-period:])
        std = np.std(prices[-period:])
        
        return {
            'upper': float(sma + std_dev * std),
            'middle': float(sma),
            'lower': float(sma - std_dev * std)
        }
    
    async def _update_statistics(self):
        """更新统计数据"""
        if self.opportunity_buffer:
            # 计算成功率（这里需要实际的执行结果）
            # 暂时使用置信度作为成功概率的估计
            avg_confidence = np.mean([opp.get('confidence', 0) for opp in self.opportunity_buffer])
            self.stats['win_rate'] = avg_confidence
    
    async def get_market_summary(self) -> Dict[str, Any]:
        """获取市场摘要"""
        return {
            'stats': self.stats,
            'market_indicators': self.metrics_buffer.get('market_indicators', {}),
            'active_opportunities': len(self.opportunity_buffer),
            'monitored_symbols': list(self.price_buffer.keys()),
            'last_update': datetime.now().isoformat()
        }
    
    async def get_opportunity_metrics(self) -> Dict[str, Any]:
        """获取机会指标"""
        if not self.opportunity_buffer:
            return {}
            
        df = pd.DataFrame(list(self.opportunity_buffer))
        
        # 按类型统计
        type_stats = df['signal_type'].value_counts().to_dict()
        
        # 按Scout统计
        scout_stats = df['scout_name'].value_counts().to_dict()
        
        # 时间分布
        df['hour'] = pd.to_datetime(df['timestamp']).dt.hour
        hourly_dist = df['hour'].value_counts().sort_index().to_dict()
        
        return {
            'by_type': type_stats,
            'by_scout': scout_stats,
            'hourly_distribution': hourly_dist,
            'total_opportunities': len(self.opportunity_buffer)
        }