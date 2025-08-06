
"""
市场Scout - 高性能加密货币市场扫描器
"""
import asyncio
import aiohttp
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timedelta
import ccxt.async_support as ccxt
import numpy as np
import logging
from collections import defaultdict
from .base_scout import BaseScout, OpportunitySignal

logger = logging.getLogger(_name_)

class MarketScout(BaseScout):
    """高性能市场扫描器"""
    
    async def _initialize(self):
        """初始化市场Scout"""
        # 配置参数
        self.exchanges_config = self.config.get('exchanges', ['binance', 'okx', 'bybit'])
        self.min_profit_pct = self.config.get('min_profit_pct', 0.1)
        self.scan_interval = self.config.get('scan_interval', 30)
        
        # 交易所实例
        self.exchanges = {}
        
        # 并发控制
        self.semaphore = asyncio.Semaphore(100)  # 限制并发请求数
        self.rate_limiters = {}  # 每个交易所的速率限制器
        
        # 缓存
        self.market_cache = {}  # 市场信息缓存
        self.ticker_cache = {}  # ticker缓存
        self.cache_ttl = 60  # 缓存生存时间（秒）
        
        # 监控的交易对
        self.common_symbols = [
            'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 
            'XRP/USDT', 'DOGE/USDT', 'ADA/USDT', 'AVAX/USDT',
            'DOT/USDT', 'MATIC/USDT', 'LINK/USDT', 'UNI/USDT'
        ]
        
        # 价格历史（用于分析）
        self.price_history = defaultdict(lambda: defaultdict(list))
        self.volume_history = defaultdict(lambda: defaultdict(list))
        
        # 统计数据
        self.exchange_stats = defaultdict(lambda: {
            'requests': 0,
            'errors': 0,
            'opportunities': 0,
            'avg_response_time': 0
        })
        
        # 初始化所有交易所
        await self._init_exchanges()
    
    async def _init_exchanges(self):
        """并发初始化所有交易所"""
        tasks = []
        for exchange_id in self.exchanges_config:
            tasks.append(self._init_single_exchange(exchange_id))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"初始化交易所失败: {self.exchanges_config[i]} - {result}")
    
    async def _init_single_exchange(self, exchange_id: str):
        """初始化单个交易所"""
        try:
            exchange_class = getattr(ccxt, exchange_id)
            exchange = exchange_class({
                'enableRateLimit': True,
                'rateLimit': 50,  # 更激进的速率
                'session': self.session,  # 复用aiohttp session
                'options': {
                    'defaultType': 'spot',
                    'adjustForTimeDifference': True
                }
            })
            
            # 预加载市场数据
            await exchange.load_markets()
            self.exchanges[exchange_id] = exchange
            
            # 初始化速率限制器
            self.rate_limiters[exchange_id] = asyncio.Semaphore(10)  # 每个交易所的并发限制
            
            # 缓存市场数据
            self.market_cache[exchange_id] = {
                'markets': exchange.markets,
                'symbols': exchange.symbols,
                'timestamp': datetime.now()
            }
            
            logger.info(f"✅ 初始化交易所 {exchange_id} - 支持 {len(exchange.symbols)} 个交易对")
            
        except Exception as e:
            logger.error(f"初始化 {exchange_id} 失败: {e}")
            raise
    
    async def scan(self) -> List[OpportunitySignal]:
        """执行扫描，返回发现的机会"""
        self.scan_count += 1
        start_time = asyncio.get_event_loop().time()
        
        opportunities = []
        
        # 并发执行多种扫描策略
        tasks = [
            self._scan_arbitrage_opportunities(),
            self._scan_volume_spikes(),
            self._scan_price_movements(),
            self._scan_orderbook_imbalances(),
            self._scan_new_listings()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, list):
                opportunities.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"扫描错误: {result}")
                self.error_count += 1
        
        # 记录扫描时间
        self.last_scan_time = asyncio.get_event_loop().time() - start_time
        logger.info(f"📊 市场扫描完成 - 发现 {len(opportunities)} 个机会 (耗时: {self.last_scan_time:.2f}秒)")
        
        return opportunities
    
    async def _scan_arbitrage_opportunities(self) -> List[OpportunitySignal]:
        """扫描套利机会 - 使用矩阵运算加速"""
        opportunities = []
        
        # 获取所有交易所的价格矩阵
        price_matrix = await self._build_price_matrix(self.common_symbols)
        
        # 快速计算套利机会
        for symbol, prices in price_matrix.items():
            if len(prices) < 2:
                continue
            
            # 找出最高买价和最低卖价
            best_bid = max(prices.items(), key=lambda x: x[1]['bid'] or 0)
            best_ask = min(prices.items(), key=lambda x: x[1]['ask'] or float('inf'))
            
            if best_bid[1]['bid'] and best_ask[1]['ask'] and best_bid[1]['bid'] > best_ask[1]['ask']:
                profit_pct = (best_bid[1]['bid'] - best_ask[1]['ask']) / best_ask[1]['ask'] * 100
                
                if profit_pct >= self.min_profit_pct:
                    # 计算置信度（基于利润率和交易量）
                    volume_factor = min(best_bid[1]['volume'] / 100000, 1) if best_bid[1]['volume'] else 0.5
                    confidence = min(profit_pct * 10 * volume_factor, 0.95)
                    
                    opportunity = self.create_opportunity(
                        signal_type='arbitrage',
                        symbol=symbol,
                        confidence=confidence,
                        data={
                            'buy_exchange': best_ask[0],
                            'sell_exchange': best_bid[0],
                            'buy_price': best_ask[1]['ask'],
                            'sell_price': best_bid[1]['bid'],
                            'profit_pct': profit_pct,
                            'volume_24h': best_bid[1]['volume'],
                            'estimated_profit_usd': self._estimate_profit_usd(
                                symbol, profit_pct, best_bid[1]['volume']
                            )
                        }
                    )
                    opportunities.append(opportunity)
                    
                    logger.info(f"💰 套利机会: {symbol} - {best_ask[0]}→{best_bid[0]} "
                               f"利润: {profit_pct:.2f}%")
        
        return opportunities
    
    async def _build_price_matrix(self, symbols: List[str]) -> Dict[str, Dict[str, Dict]]:
        """构建价格矩阵"""
        price_matrix = defaultdict(dict)
        
        # 创建所有获取价格的任务
        tasks = []
        task_info = []  # 保存任务信息
        
        for symbol in symbols:
            for exchange_id, exchange in self.exchanges.items():
                if symbol in exchange.symbols:
                    tasks.append(self._fetch_ticker_with_cache(exchange, symbol, exchange_id))
                    task_info.append((symbol, exchange_id))
        
        # 并发执行所有任务
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        for i, result in enumerate(results):
            symbol, exchange_id = task_info[i]
            if isinstance(result, dict) and result:
                price_matrix[symbol][exchange_id] = result
        
        return price_matrix
    
    async def _fetch_ticker_with_cache(self, exchange, symbol: str, exchange_id: str) -> Optional[Dict]:
        """获取ticker数据（带缓存）"""
        cache_key = f"{exchange_id}:{symbol}"
        now = datetime.now()
        
        # 检查缓存
        if cache_key in self.ticker_cache:
            cached_data, timestamp = self.ticker_cache[cache_key]
            if (now - timestamp).seconds < self.cache_ttl:
                return cached_data
        
        # 获取新数据
        async with self.semaphore:
            async with self.rate_limiters[exchange_id]:
                try:
                    start_time = asyncio.get_event_loop().time()
                    ticker = await exchange.fetch_ticker(symbol)
                    
                    # 更新统计
                    response_time = asyncio.get_event_loop().time() - start_time
                    self._update_exchange_stats(exchange_id, response_time)
                    
                    result = {
                        'bid': ticker['bid'],
                        'ask': ticker['ask'],
                        'volume': ticker['baseVolume'],
                        'last': ticker['last'],
                        'change': ticker['percentage']
                    }
                    
                    # 更新缓存
                    self.ticker_cache[cache_key] = (result, now)
                    
                    # 更新价格历史
                    self.price_history[symbol][exchange_id].append({
                        'price': ticker['last'],
                        'timestamp': now
                    })
                    
                    # 限制历史数据大小
                    if len(self.price_history[symbol][exchange_id]) > 100:
                        self.price_history[symbol][exchange_id] = \
                            self.price_history[symbol][exchange_id][-100:]
                    
                    return result
                    
                except Exception as e:
                    self.exchange_stats[exchange_id]['errors'] += 1
                    logger.debug(f"获取 {exchange_id} {symbol} 失败: {e}")
                    return None
    
    async def _scan_volume_spikes(self) -> List[OpportunitySignal]:
        """扫描成交量激增"""
        opportunities = []
        
        # 获取所有交易对的当前和历史成交量
        tasks = []
        for exchange_id, exchange in self.exchanges.items():
            # 选择要扫描的交易对
            symbols_to_scan = [s for s in self.common_symbols if s in exchange.symbols][:20]
            
            for symbol in symbols_to_scan:
                tasks.append(self._analyze_volume_spike(exchange, symbol, exchange_id))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, OpportunitySignal):
                opportunities.append(result)
        
        return opportunities
    
    async def _analyze_volume_spike(self, exchange, symbol: str, exchange_id: str) -> Optional[OpportunitySignal]:
        """分析单个交易对的成交量激增"""
        try:
            # 获取当前ticker
            ticker = await self._fetch_ticker_with_cache(exchange, symbol, exchange_id)
            if not ticker or not ticker['volume']:
                return None
            
            # 获取历史成交量数据
            history = self.volume_history[symbol][exchange_id]
            
            # 如果历史数据不足，只保存当前数据
            if len(history) < 10:
                history.append({
                    'volume': ticker['volume'],
                    'timestamp': datetime.now()
                })
                return None
            
            # 计算平均成交量
            avg_volume = np.mean([h['volume'] for h in history[-10:]])
            current_volume = ticker['volume']
            
            # 计算成交量比率
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
            
            # 检测成交量激增（超过平均值的3倍）
            if volume_ratio >= 3:
                # 获取价格变化
                price_change = ticker.get('change', 0)
                
                # 计算置信度
                confidence = min(0.5 + (volume_ratio - 3) * 0.1, 0.9)
                
                opportunity = self.create_opportunity(
                    signal_type='volume_spike',
                    symbol=symbol,
                    confidence=confidence,
                    data={
                        'exchange': exchange_id,
                        'volume_ratio': volume_ratio,
                        'current_volume': current_volume,
                        'avg_volume': avg_volume,
                        'price_change_24h': price_change,
                        'current_price': ticker['last'],
                        'alert_type': 'bullish' if price_change > 0 else 'bearish'
                    }
                )
                
                logger.info(f"📊 成交量激增: {symbol}@{exchange_id} - "
                           f"倍数: {volume_ratio:.1f}x, 价格变化: {price_change:+.2f}%")
                
                return opportunity
                
        except Exception as e:
            logger.debug(f"分析成交量失败 {symbol}@{exchange_id}: {e}")
            return None
    
    async def _scan_price_movements(self) -> List[OpportunitySignal]:
        """扫描异常价格波动"""
        opportunities = []
        
        for symbol, exchange_data in self.price_history.items():
            for exchange_id, history in exchange_data.items():
                if len(history) >= 5:
                    # 分析价格趋势
                    prices = [h['price'] for h in history[-5:]]
                    
                    # 计算短期变化率
                    price_change = (prices[-1] - prices[0]) / prices[0] * 100
                    
                    # 检测快速上涨或下跌（5分钟内超过2%）
                    if abs(price_change) >= 2:
                        # 计算方向和强度
                        direction = 'up' if price_change > 0 else 'down'
                        volatility = np.std(prices) / np.mean(prices) * 100
                        
                        confidence = min(abs(price_change) / 10 + volatility / 20, 0.85)
                        
                        opportunity = self.create_opportunity(
                            signal_type='price_movement',
                            symbol=symbol,
                            confidence=confidence,
                            data={
                                'exchange': exchange_id,
                                'direction': direction,
                                'change_pct': price_change,
                                'volatility': volatility,
                                'current_price': prices[-1],
                                'support_level': min(prices),
                                'resistance_level': max(prices),
                                'momentum': 'strong' if abs(price_change) > 5 else 'moderate'
                            }
                        )
                        opportunities.append(opportunity)
                        
                        logger.info(f"📈 价格{'上涨' if direction == 'up' else '下跌'}: "
                                   f"{symbol}@{exchange_id} - {price_change:+.2f}%")
        
        return opportunities
    
    async def _scan_orderbook_imbalances(self) -> List[OpportunitySignal]:
        """扫描订单簿失衡"""
        opportunities = []
        
        # 选择流动性较好的交易对进行深度分析
        symbols_to_scan = self.common_symbols[:5]  # 限制数量以提高性能
        
        tasks = []
        for symbol in symbols_to_scan:
            for exchange_id, exchange in self.exchanges.items():
                if symbol in exchange.symbols:
                    tasks.append(self._analyze_orderbook(exchange, symbol, exchange_id))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, OpportunitySignal):
                opportunities.append(result)
        
        return opportunities
    
    async def _analyze_orderbook(self, exchange, symbol: str, exchange_id: str) -> Optional[OpportunitySignal]:
        """分析订单簿"""
        try:
            async with self.semaphore:
                # 获取订单簿
                orderbook = await exchange.fetch_order_book(symbol, limit=50)
                
                if not orderbook['bids'] or not orderbook['asks']:
                    return None
                
                # 计算买卖压力
                bid_volume = sum(bid[1] for bid in orderbook['bids'][:20])
                ask_volume = sum(ask[1] for ask in orderbook['asks'][:20])
                
                # 计算失衡率
                total_volume = bid_volume + ask_volume
                if total_volume == 0:
                    return None
                
                imbalance_ratio = (bid_volume - ask_volume) / total_volume
                
                # 检测显著失衡（超过30%）
                if abs(imbalance_ratio) >= 0.3:
                    # 分析价格压力
                    best_bid = orderbook['bids'][0][0]
                    best_ask = orderbook['asks'][0][0]
                    spread = (best_ask - best_bid) / best_bid * 100
                    
                    confidence = min(abs(imbalance_ratio) * 2, 0.8)
                    
                    opportunity = self.create_opportunity(
                        signal_type='orderbook_imbalance',
                        symbol=symbol,
                        confidence=confidence,
                        data={
                            'exchange': exchange_id,
                            'imbalance_ratio': imbalance_ratio,
                            'bid_volume': bid_volume,
                            'ask_volume': ask_volume,
                            'spread_pct': spread,
                            'pressure': 'buy' if imbalance_ratio > 0 else 'sell',
                            'best_bid': best_bid,
                            'best_ask': best_ask,
                            'depth': len(orderbook['bids']) + len(orderbook['asks'])
                        }
                    )
                    
                    logger.info(f"⚖ 订单簿失衡: {symbol}@{exchange_id} - "
                               f"{'买' if imbalance_ratio > 0 else '卖'}压: {abs(imbalance_ratio):.1%}")
                    
                    return opportunity
                    
        except Exception as e:
            logger.debug(f"分析订单簿失败 {symbol}@{exchange_id}: {e}")
            return None
    
    async def _scan_new_listings(self) -> List[OpportunitySignal]:
        """扫描新上市代币"""
        opportunities = []
        
        # 这个功能需要维护一个已知交易对的数据库
        # 这里简化处理，只检查缓存中的新交易对
        
        for exchange_id, exchange in self.exchanges.items():
            try:
                # 重新加载市场数据
                await exchange.load_markets()
                
                # 比较新旧市场数据
                old_symbols = set(self.market_cache[exchange_id]['symbols'])
                new_symbols = set(exchange.symbols)
                
                # 找出新增的交易对
                added_symbols = new_symbols - old_symbols
                
                for symbol in added_symbols:
                    if symbol.endswith('/USDT'):  # 只关注USDT交易对
                        opportunity = self.create_opportunity(
                            signal_type='new_listing',
                            symbol=symbol,
                            confidence=0.9,  # 新上市通常有较高的波动性
                            data={
                                'exchange': exchange_id,
                                'listing_time': datetime.now().isoformat(),
                                'market_info': exchange.markets.get(symbol, {})
                            }
                        )
                        opportunities.append(opportunity)
                        
                        logger.info(f"🆕 新上市: {symbol} 在 {exchange_id}")
                
                # 更新缓存
                self.market_cache[exchange_id]['symbols'] = list(new_symbols)
                
            except Exception as e:
                logger.debug(f"扫描新上市失败 {exchange_id}: {e}")
        
        return opportunities
    
    def _estimate_profit_usd(self, symbol: str, profit_pct: float, volume: float) -> float:
        """估算USD利润"""
        # 简化计算：假设可以交易10%的日成交量
        tradeable_volume = volume * 0.1
        
        # 根据交易对估算USD价值
        if symbol == 'BT