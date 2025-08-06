"""
数据收集器模块
"""
import asyncio
import aiohttp
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import pandas as pd
from pathlib import Path
import numpy as np

logger = logging.getLogger(__name__)

class DataCollector:
    """数据收集器"""
    
    def __init__(self, config):
        self.config = config
        self.session = None
        self.data_dir = Path("data")
        self.data_dir.mkdir(exist_ok=True)
        
        # API配置
        self.apis = {
            'binance': {
                'base_url': 'https://api.binance.com',
                'rate_limit': 1200,  # 每分钟请求数
                'last_request': 0
            },
            'coingecko': {
                'base_url': 'https://api.coingecko.com/api/v3',
                'rate_limit': 50,  # 每分钟请求数
                'last_request': 0
            }
        }
        
    async def initialize(self):
        """初始化数据收集器"""
        logger.info("初始化数据收集器...")
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30)
        )
        logger.info("✅ 数据收集器初始化完成")
    
    async def close(self):
        """关闭数据收集器"""
        if self.session:
            await self.session.close()
    
    async def get_market_data(self, symbol: str, interval: str = '1h', limit: int = 100) -> List[Dict]:
        """获取市场数据"""
        try:
            # 从Binance获取K线数据
            url = f"{self.apis['binance']['base_url']}/api/v3/klines"
            params = {
                'symbol': symbol,
                'interval': interval,
                'limit': limit
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_kline_data(data)
                else:
                    logger.error(f"获取市场数据失败: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"获取市场数据异常: {e}")
            return []
    
    def _parse_kline_data(self, data: List) -> List[Dict]:
        """解析K线数据"""
        parsed_data = []
        for item in data:
            parsed_data.append({
                'timestamp': datetime.fromtimestamp(item[0] / 1000),
                'open': float(item[1]),
                'high': float(item[2]),
                'low': float(item[3]),
                'close': float(item[4]),
                'volume': float(item[5]),
                'close_time': datetime.fromtimestamp(item[6] / 1000),
                'quote_volume': float(item[7]),
                'trades': int(item[8]),
                'taker_buy_base': float(item[9]),
                'taker_buy_quote': float(item[10])
            })
        return parsed_data
    
    async def get_ticker_24h(self, symbol: str) -> Optional[Dict]:
        """获取24小时价格统计"""
        try:
            url = f"{self.apis['binance']['base_url']}/api/v3/ticker/24hr"
            params = {'symbol': symbol}
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        'symbol': data['symbol'],
                        'price_change': float(data['priceChange']),
                        'price_change_percent': float(data['priceChangePercent']),
                        'weighted_avg_price': float(data['weightedAvgPrice']),
                        'prev_close_price': float(data['prevClosePrice']),
                        'last_price': float(data['lastPrice']),
                        'last_qty': float(data['lastQty']),
                        'bid_price': float(data['bidPrice']),
                        'ask_price': float(data['askPrice']),
                        'open_price': float(data['openPrice']),
                        'high_price': float(data['highPrice']),
                        'low_price': float(data['lowPrice']),
                        'volume': float(data['volume']),
                        'quote_volume': float(data['quoteVolume']),
                        'open_time': datetime.fromtimestamp(data['openTime'] / 1000),
                        'close_time': datetime.fromtimestamp(data['closeTime'] / 1000),
                        'count': int(data['count'])
                    }
                else:
                    logger.error(f"获取24小时统计失败: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"获取24小时统计异常: {e}")
            return None
    
    async def get_order_book(self, symbol: str, limit: int = 100) -> Optional[Dict]:
        """获取订单簿数据"""
        try:
            url = f"{self.apis['binance']['base_url']}/api/v3/depth"
            params = {
                'symbol': symbol,
                'limit': limit
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        'last_update_id': data['lastUpdateId'],
                        'bids': [[float(price), float(qty)] for price, qty in data['bids']],
                        'asks': [[float(price), float(qty)] for price, qty in data['asks']]
                    }
                else:
                    logger.error(f"获取订单簿失败: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"获取订单簿异常: {e}")
            return None
    
    async def get_recent_trades(self, symbol: str, limit: int = 100) -> List[Dict]:
        """获取最近交易"""
        try:
            url = f"{self.apis['binance']['base_url']}/api/v3/trades"
            params = {
                'symbol': symbol,
                'limit': limit
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return [{
                        'id': trade['id'],
                        'price': float(trade['price']),
                        'qty': float(trade['qty']),
                        'quote_qty': float(trade['quoteQty']),
                        'time': datetime.fromtimestamp(trade['time'] / 1000),
                        'is_buyer_maker': trade['isBuyerMaker'],
                        'is_best_match': trade.get('isBestMatch', False)
                    } for trade in data]
                else:
                    logger.error(f"获取最近交易失败: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"获取最近交易异常: {e}")
            return []
    
    async def save_market_data(self, symbol: str, data: List[Dict]):
        """保存市场数据到文件"""
        try:
            df = pd.DataFrame(data)
            filename = f"{symbol.replace('/', '_')}_{datetime.now().strftime('%Y%m%d')}.csv"
            filepath = self.data_dir / filename
            
            df.to_csv(filepath, index=False)
            logger.info(f"保存市场数据到: {filepath}")
            
        except Exception as e:
            logger.error(f"保存市场数据失败: {e}")
    
    async def collect_opportunity_data(self, symbol: str) -> Dict[str, Any]:
        """收集机会分析所需的数据"""
        try:
            # 获取各种数据
            market_data = await self.get_market_data(symbol, limit=100)
            ticker_24h = await self.get_ticker_24h(symbol)
            order_book = await self.get_order_book(symbol)
            recent_trades = await self.get_recent_trades(symbol)
            
            if not market_data or not ticker_24h:
                return {}
            
            # 计算技术指标
            technical_indicators = self._calculate_technical_indicators(market_data)
            
            # 计算订单簿指标
            order_book_metrics = self._calculate_order_book_metrics(order_book) if order_book else {}
            
            # 计算交易指标
            trade_metrics = self._calculate_trade_metrics(recent_trades)
            
            return {
                'symbol': symbol,
                'timestamp': datetime.now(),
                'market_data': market_data[-20:],  # 最近20个数据点
                'ticker_24h': ticker_24h,
                'technical_indicators': technical_indicators,
                'order_book_metrics': order_book_metrics,
                'trade_metrics': trade_metrics
            }
            
        except Exception as e:
            logger.error(f"收集机会数据失败: {e}")
            return {}
    
    def _calculate_technical_indicators(self, market_data: List[Dict]) -> Dict[str, float]:
        """计算技术指标"""
        try:
            if len(market_data) < 20:
                return {}
            
            df = pd.DataFrame(market_data)
            closes = df['close'].values
            
            # RSI
            rsi = self._calculate_rsi(closes)
            
            # MACD
            macd, signal = self._calculate_macd(closes)
            
            # 布林带
            bb_upper, bb_middle, bb_lower = self._calculate_bollinger_bands(closes)
            
            # 支撑和阻力
            support, resistance = self._calculate_support_resistance(closes)
            
            return {
                'rsi': rsi,
                'macd': macd,
                'macd_signal': signal,
                'bb_upper': bb_upper,
                'bb_middle': bb_middle,
                'bb_lower': bb_lower,
                'support': support,
                'resistance': resistance
            }
            
        except Exception as e:
            logger.error(f"计算技术指标失败: {e}")
            return {}
    
    def _calculate_rsi(self, prices: np.ndarray, period: int = 14) -> float:
        """计算RSI"""
        try:
            deltas = np.diff(prices)
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)
            
            avg_gains = np.mean(gains[-period:])
            avg_losses = np.mean(losses[-period:])
            
            if avg_losses == 0:
                return 100
            
            rs = avg_gains / avg_losses
            rsi = 100 - (100 / (1 + rs))
            return float(rsi)
            
        except Exception:
            return 50.0
    
    def _calculate_macd(self, prices: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple:
        """计算MACD"""
        try:
            ema_fast = self._calculate_ema(prices, fast)
            ema_slow = self._calculate_ema(prices, slow)
            macd_line = ema_fast - ema_slow
            signal_line = self._calculate_ema(macd_line, signal)
            
            return float(macd_line[-1]), float(signal_line[-1])
            
        except Exception:
            return 0.0, 0.0
    
    def _calculate_ema(self, prices: np.ndarray, period: int) -> np.ndarray:
        """计算指数移动平均"""
        alpha = 2 / (period + 1)
        ema = np.zeros_like(prices)
        ema[0] = prices[0]
        
        for i in range(1, len(prices)):
            ema[i] = alpha * prices[i] + (1 - alpha) * ema[i-1]
        
        return ema
    
    def _calculate_bollinger_bands(self, prices: np.ndarray, period: int = 20, std_dev: int = 2) -> tuple:
        """计算布林带"""
        try:
            sma = np.mean(prices[-period:])
            std = np.std(prices[-period:])
            
            upper = sma + (std_dev * std)
            lower = sma - (std_dev * std)
            
            return float(upper), float(sma), float(lower)
            
        except Exception:
            return 0.0, 0.0, 0.0
    
    def _calculate_support_resistance(self, prices: np.ndarray) -> tuple:
        """计算支撑和阻力位"""
        try:
            # 简单的支撑阻力计算
            recent_prices = prices[-20:]
            support = np.min(recent_prices)
            resistance = np.max(recent_prices)
            
            return float(support), float(resistance)
            
        except Exception:
            return 0.0, 0.0
    
    def _calculate_order_book_metrics(self, order_book: Dict) -> Dict[str, float]:
        """计算订单簿指标"""
        try:
            bids = order_book['bids']
            asks = order_book['asks']
            
            # 买卖价差
            spread = asks[0][0] - bids[0][0]
            spread_percent = (spread / bids[0][0]) * 100
            
            # 订单簿不平衡
            bid_volume = sum(qty for _, qty in bids[:10])
            ask_volume = sum(qty for _, qty in asks[:10])
            imbalance = (bid_volume - ask_volume) / (bid_volume + ask_volume)
            
            return {
                'spread': spread,
                'spread_percent': spread_percent,
                'imbalance': imbalance,
                'bid_volume': bid_volume,
                'ask_volume': ask_volume
            }
            
        except Exception as e:
            logger.error(f"计算订单簿指标失败: {e}")
            return {}
    
    def _calculate_trade_metrics(self, trades: List[Dict]) -> Dict[str, float]:
        """计算交易指标"""
        try:
            if not trades:
                return {}
            
            # 计算买卖比例
            buy_trades = sum(1 for trade in trades if not trade['is_buyer_maker'])
            sell_trades = len(trades) - buy_trades
            buy_ratio = buy_trades / len(trades)
            
            # 计算平均交易量
            avg_qty = np.mean([trade['qty'] for trade in trades])
            
            # 计算价格波动
            prices = [trade['price'] for trade in trades]
            price_volatility = np.std(prices) / np.mean(prices)
            
            return {
                'buy_ratio': buy_ratio,
                'sell_ratio': 1 - buy_ratio,
                'avg_qty': avg_qty,
                'price_volatility': price_volatility,
                'trade_count': len(trades)
            }
            
        except Exception as e:
            logger.error(f"计算交易指标失败: {e}")
            return {} 