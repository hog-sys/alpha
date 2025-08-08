# src/backtesting/backtest_strategy.py
"""
基于 TimescaleDB + ML 预测器的回测策略框架
使用 backtesting.py 库进行策略回测
"""
import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from pathlib import Path

# backtesting.py 库
from backtesting import Backtest, Strategy
from backtesting.lib import crossover
import talib

# 项目内部导入
from src.core.db import init_db, db
from src.analysis.ml_predictor import EnhancedMLPredictor
from config.settings import get_config

logger = logging.getLogger(__name__)

class TimescaleDataAdapter:
    """
    TimescaleDB 数据适配器 - 为 backtesting.py 提供标准化的 OHLCV 数据
    """
    
    def __init__(self):
        self.db_manager = None
    
    async def initialize(self):
        """初始化数据库连接"""
        await init_db()
        self.db_manager = db
        logger.info("✅ TimescaleDB 数据适配器初始化完成")
    
    async def fetch_ohlcv_data(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
        timeframe: str = '1m'
    ) -> pd.DataFrame:
        """
        从 TimescaleDB 获取 OHLCV 数据
        
        Args:
            symbol: 交易对符号 (e.g., 'BTC/USDT')
            start_time: 开始时间
            end_time: 结束时间  
            timeframe: 时间框架 ('1m', '5m', '1h', '1d')
        
        Returns:
            标准化的 OHLCV DataFrame，列名为: Open, High, Low, Close, Volume
        """
        try:
            # 根据时间框架选择聚合级别
            time_bucket = self._get_time_bucket(timeframe)
            
            query = f"""
            SELECT 
                time_bucket('{time_bucket}', timestamp) as time,
                first(price, timestamp) as open,
                max(price) as high,
                min(price) as low,
                last(price, timestamp) as close,
                sum(volume) as volume
            FROM market_data 
            WHERE symbol = %s 
                AND timestamp >= %s 
                AND timestamp <= %s
            GROUP BY time
            ORDER BY time ASC
            """
            
            async with self.db_manager.async_session() as session:
                result = await session.execute(
                    query, 
                    (symbol, start_time, end_time)
                )
                rows = result.fetchall()
            
            if not rows:
                logger.warning(f"未找到 {symbol} 在 {start_time} - {end_time} 的数据")
                return pd.DataFrame()
            
            # 转换为 DataFrame
            df = pd.DataFrame(rows, columns=['time', 'Open', 'High', 'Low', 'Close', 'Volume'])
            df['time'] = pd.to_datetime(df['time'])
            df.set_index('time', inplace=True)
            
            # 确保数据类型正确
            for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # 删除任何包含 NaN 的行
            df.dropna(inplace=True)
            
            logger.info(f"✅ 获取到 {len(df)} 条 {symbol} OHLCV 数据")
            return df
            
        except Exception as e:
            logger.error(f"获取 OHLCV 数据失败: {e}", exc_info=True)
            return pd.DataFrame()
    
    def _get_time_bucket(self, timeframe: str) -> str:
        """将时间框架转换为 TimescaleDB time_bucket 参数"""
        mapping = {
            '1m': '1 minute',
            '5m': '5 minutes', 
            '15m': '15 minutes',
            '1h': '1 hour',
            '4h': '4 hours',
            '1d': '1 day'
        }
        return mapping.get(timeframe, '1 minute')
    
    async def fetch_alpha_opportunities(
        self,
        start_time: datetime,
        end_time: datetime,
        min_confidence: float = 0.6
    ) -> pd.DataFrame:
        """
        获取历史 Alpha 机会信号
        """
        try:
            query = """
            SELECT 
                timestamp,
                symbol,
                signal_type,
                confidence,
                prediction_details,
                data
            FROM alpha_opportunities 
            WHERE timestamp >= %s 
                AND timestamp <= %s
                AND confidence >= %s
            ORDER BY timestamp ASC
            """
            
            async with self.db_manager.async_session() as session:
                result = await session.execute(
                    query,
                    (start_time, end_time, min_confidence)
                )
                rows = result.fetchall()
            
            if not rows:
                return pd.DataFrame()
            
            df = pd.DataFrame(rows, columns=[
                'timestamp', 'symbol', 'signal_type', 
                'confidence', 'prediction_details', 'data'
            ])
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            
            return df
            
        except Exception as e:
            logger.error(f"获取 Alpha 机会失败: {e}")
            return pd.DataFrame()

class MLAlphaStrategy(Strategy):
    """
    基于 ML 预测器的 Alpha 策略
    """
    
    # 策略参数
    ml_threshold = 0.7  # ML 预测阈值
    stop_loss_pct = 0.05  # 止损百分比
    take_profit_pct = 0.15  # 止盈百分比
    position_size = 0.1  # 每次交易的资金比例
    
    def init(self):
        """策略初始化"""
        # 计算技术指标
        self.rsi = self.I(talib.RSI, self.data.Close, 14)
        self.macd, self.macd_signal, _ = self.I(
            talib.MACD, self.data.Close, 12, 26, 9
        )
        self.bb_upper, self.bb_middle, self.bb_lower = self.I(
            talib.BBANDS, self.data.Close, 20, 2, 2
        )
        
        # ML 预测信号（需要在策略运行前预计算）
        self.ml_signals = getattr(self.data, 'ml_prediction', pd.Series(index=self.data.index, data=0.5))
        self.alpha_signals = getattr(self.data, 'alpha_confidence', pd.Series(index=self.data.index, data=0.0))
        
        logger.info("✅ ML Alpha 策略初始化完成")
    
    def next(self):
        """每个时间步的策略逻辑"""
        current_price = self.data.Close[-1]
        current_ml_signal = self.ml_signals[-1]
        current_alpha_confidence = self.alpha_signals[-1]
        
        # 组合信号强度
        signal_strength = self._calculate_signal_strength(
            current_ml_signal,
            current_alpha_confidence,
            self.rsi[-1],
            self.macd[-1] - self.macd_signal[-1]
        )
        
        # 做多信号
        if (signal_strength > self.ml_threshold and 
            not self.position and
            self.rsi[-1] < 70):  # 避免超买
            
            # 计算止损和止盈价格
            stop_loss = current_price * (1 - self.stop_loss_pct)
            take_profit = current_price * (1 + self.take_profit_pct)
            
            # 开仓
            self.buy(
                size=self.position_size,
                sl=stop_loss,
                tp=take_profit
            )
            
            logger.debug(f"开多仓: 价格={current_price:.4f}, 信号强度={signal_strength:.3f}")
        
        # 做空信号（如果支持）
        elif (signal_strength < -self.ml_threshold and 
              not self.position and
              self.rsi[-1] > 30):  # 避免超卖
            
            stop_loss = current_price * (1 + self.stop_loss_pct)
            take_profit = current_price * (1 - self.take_profit_pct)
            
            self.sell(
                size=self.position_size,
                sl=stop_loss,
                tp=take_profit
            )
            
            logger.debug(f"开空仓: 价格={current_price:.4f}, 信号强度={signal_strength:.3f}")
        
        # 提前平仓逻辑
        elif self.position:
            self._check_early_exit(current_price, signal_strength)
    
    def _calculate_signal_strength(
        self,
        ml_prediction: float,
        alpha_confidence: float,
        rsi: float,
        macd_diff: float
    ) -> float:
        """
        计算综合信号强度
        
        Returns:
            信号强度 [-1, 1]，正值看多，负值看空
        """
        # ML 预测权重 (60%)
        ml_component = (ml_prediction - 0.5) * 2 * 0.6
        
        # Alpha 信号权重 (25%)
        alpha_component = alpha_confidence * 0.25
        
        # 技术指标权重 (15%)
        tech_component = 0
        
        # RSI 贡献
        if rsi < 30:  # 超卖，看多
            tech_component += 0.1
        elif rsi > 70:  # 超买，看空
            tech_component -= 0.1
        
        # MACD 贡献
        if macd_diff > 0:  # 金叉，看多
            tech_component += 0.05
        else:  # 死叉，看空
            tech_component -= 0.05
        
        total_strength = ml_component + alpha_component + tech_component
        
        # 限制在 [-1, 1] 范围内
        return max(-1, min(1, total_strength))
    
    def _check_early_exit(self, current_price: float, signal_strength: float):
        """检查是否需要提前平仓"""
        if not self.position:
            return
        
        # 信号反转，提前平仓
        if self.position.is_long and signal_strength < -0.3:
            self.position.close()
            logger.debug(f"多仓信号反转平仓: 价格={current_price:.4f}")
        elif self.position.is_short and signal_strength > 0.3:
            self.position.close()
            logger.debug(f"空仓信号反转平仓: 价格={current_price:.4f}")

class BacktestRunner:
    """
    回测运行器 - 协调数据获取、ML 预测和策略回测
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.data_adapter = TimescaleDataAdapter()
        self.ml_predictor = None
        
    async def initialize(self):
        """初始化回测环境"""
        await self.data_adapter.initialize()
        
        # 初始化 ML 预测器
        self.ml_predictor = EnhancedMLPredictor(self.config)
        await self.ml_predictor.initialize()
        
        logger.info("✅ 回测运行器初始化完成")
    
    async def run_backtest(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        timeframe: str = '1h',
        initial_cash: float = 10000,
        commission: float = 0.001
    ) -> Dict[str, Any]:
        """
        运行完整的回测流程
        
        Args:
            symbol: 交易对符号
            start_date: 回测开始日期
            end_date: 回测结束日期
            timeframe: 时间框架
            initial_cash: 初始资金
            commission: 手续费率
        
        Returns:
            回测结果字典
        """
        try:
            logger.info(f"开始回测 {symbol} ({start_date} - {end_date})")
            
            # 1. 获取历史价格数据
            ohlcv_data = await self.data_adapter.fetch_ohlcv_data(
                symbol, start_date, end_date, timeframe
            )
            
            if ohlcv_data.empty:
                raise ValueError(f"无法获取 {symbol} 的历史数据")
            
            # 2. 获取 Alpha 信号
            alpha_data = await self.data_adapter.fetch_alpha_opportunities(
                start_date, end_date
            )
            
            # 3. 生成 ML 预测信号
            ml_predictions = await self._generate_ml_predictions(
                ohlcv_data, alpha_data, symbol
            )
            
            # 4. 合并数据
            backtest_data = self._prepare_backtest_data(
                ohlcv_data, ml_predictions, alpha_data
            )
            
            # 5. 运行回测
            bt = Backtest(
                backtest_data,
                MLAlphaStrategy,
                cash=initial_cash,
                commission=commission
            )
            
            # 运行回测并获取结果
            results = bt.run()
            
            # 6. 生成详细报告
            report = self._generate_backtest_report(
                results, symbol, start_date, end_date
            )
            
            # 7. 保存结果到数据库
            await self._save_backtest_results(report)
            
            logger.info(f"✅ 回测完成: {symbol}, 收益率: {results['Return [%]']:.2f}%")
            
            return report
            
        except Exception as e:
            logger.error(f"回测失败: {e}", exc_info=True)
            return {
                'error': str(e),
                'symbol': symbol,
                'start_date': start_date,
                'end_date': end_date
            }
    
    async def _generate_ml_predictions(
        self,
        ohlcv_data: pd.DataFrame,
        alpha_data: pd.DataFrame,
        symbol: str
    ) -> pd.DataFrame:
        """
        为每个时间点生成 ML 预测
        """
        predictions = []
        
        for timestamp, row in ohlcv_data.iterrows():
            try:
                # 构造机会数据格式
                opportunity = {
                    'symbol': symbol,
                    'timestamp': timestamp,
                    'price': row['Close'],
                    'volume': row['Volume'],
                    'signal_type': 'ml_backtest',
                    'confidence': 0.5,
                    'data': {
                        'open': row['Open'],
                        'high': row['High'],
                        'low': row['Low'],
                        'close': row['Close'],
                        'volume': row['Volume']
                    }
                }
                
                # 获取 ML 预测
                prediction = await self.ml_predictor.predict_opportunity_with_explanation(
                    opportunity
                )
                
                predictions.append({
                    'timestamp': timestamp,
                    'ml_prediction': prediction['prediction_score'],
                    'model_confidence': prediction.get('model_confidence', 0),
                    'explanation': prediction.get('explanation', '')
                })
                
            except Exception as e:
                logger.warning(f"ML 预测失败 {timestamp}: {e}")
                predictions.append({
                    'timestamp': timestamp,
                    'ml_prediction': 0.5,
                    'model_confidence': 0,
                    'explanation': 'prediction_failed'
                })
        
        pred_df = pd.DataFrame(predictions)
        pred_df.set_index('timestamp', inplace=True)
        
        return pred_df
    
    def _prepare_backtest_data(
        self,
        ohlcv_data: pd.DataFrame,
        ml_predictions: pd.DataFrame,
        alpha_data: pd.DataFrame
    ) -> pd.DataFrame:
        """
        合并所有数据为回测所需格式
        """
        # 以 OHLCV 为基础
        backtest_data = ohlcv_data.copy()
        
        # 添加 ML 预测
        backtest_data = backtest_data.join(ml_predictions, how='left')
        
        # 填充缺失的 ML 预测
        backtest_data['ml_prediction'].fillna(0.5, inplace=True)
        backtest_data['model_confidence'].fillna(0, inplace=True)
        
        # 添加 Alpha 信号置信度
        if not alpha_data.empty:
            # 将 alpha 数据重采样到 OHLCV 时间框架
            alpha_resampled = alpha_data.resample('1H')['confidence'].mean()
            backtest_data = backtest_data.join(alpha_resampled.rename('alpha_confidence'), how='left')
        else:
            backtest_data['alpha_confidence'] = 0.0
        
        # 填充缺失值
        backtest_data['alpha_confidence'].fillna(0, inplace=True)
        
        return backtest_data
    
    def _generate_backtest_report(
        self,
        results: pd.Series,
        symbol: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        生成详细的回测报告
        """
        return {
            'symbol': symbol,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'total_return_pct': float(results['Return [%]']),
            'buy_hold_return_pct': float(results['Buy & Hold Return [%]']),
            'max_drawdown_pct': float(results['Max. Drawdown [%]']),
            'volatility_pct': float(results['Volatility [%]']),
            'sharpe_ratio': float(results['Sharpe Ratio']),
            'calmar_ratio': float(results['Calmar Ratio']),
            'total_trades': int(results['# Trades']),
            'win_rate_pct': float(results['Win Rate [%]']),
            'avg_trade_pct': float(results['Avg. Trade [%]']),
            'max_trade_duration': str(results['Max. Trade Duration']),
            'avg_trade_duration': str(results['Avg. Trade Duration']),
            'profit_factor': float(results['Profit Factor']),
            'sqn': float(results['SQN']),
            'generated_at': datetime.now().isoformat()
        }
    
    async def _save_backtest_results(self, report: Dict[str, Any]):
        """
        保存回测结果到数据库
        """
        try:
            # 这里应该保存到专门的回测结果表
            # 目前先记录日志
            logger.info(f"回测结果: {report['symbol']} 收益率: {report['total_return_pct']:.2f}%")
            
            # TODO: 实现保存到数据库的逻辑
            # INSERT INTO backtest_results (symbol, start_date, end_date, results_json, created_at)
            
        except Exception as e:
            logger.error(f"保存回测结果失败: {e}")

# 便捷函数
async def run_single_backtest(
    symbol: str,
    days_back: int = 30,
    timeframe: str = '1h'
) -> Dict[str, Any]:
    """
    运行单个币种的回测
    """
    config = get_config()
    runner = BacktestRunner(config)
    
    await runner.initialize()
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    
    return await runner.run_backtest(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        timeframe=timeframe
    )

async def run_portfolio_backtest(
    symbols: List[str],
    days_back: int = 30,
    timeframe: str = '1h'
) -> Dict[str, Any]:
    """
    运行多币种组合回测
    """
    config = get_config()
    runner = BacktestRunner(config)
    
    await runner.initialize()
    
    results = {}
    
    for symbol in symbols:
        logger.info(f"回测 {symbol}...")
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        result = await runner.run_backtest(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            timeframe=timeframe
        )
        
        results[symbol] = result
    
    # 计算组合统计
    portfolio_stats = _calculate_portfolio_stats(results)
    
    return {
        'individual_results': results,
        'portfolio_stats': portfolio_stats,
        'symbols': symbols,
        'timeframe': timeframe,
        'days_back': days_back
    }

def _calculate_portfolio_stats(results: Dict[str, Dict]) -> Dict[str, float]:
    """
    计算投资组合统计指标
    """
    valid_results = {k: v for k, v in results.items() if 'error' not in v}
    
    if not valid_results:
        return {'error': 'no_valid_results'}
    
    returns = [r['total_return_pct'] for r in valid_results.values()]
    sharpe_ratios = [r['sharpe_ratio'] for r in valid_results.values()]
    max_drawdowns = [r['max_drawdown_pct'] for r in valid_results.values()]
    
    return {
        'avg_return_pct': np.mean(returns),
        'median_return_pct': np.median(returns),
        'best_return_pct': max(returns),
        'worst_return_pct': min(returns),
        'avg_sharpe_ratio': np.mean(sharpe_ratios),
        'avg_max_drawdown_pct': np.mean(max_drawdowns),
        'success_rate_pct': len([r for r in returns if r > 0]) / len(returns) * 100,
        'total_symbols': len(valid_results)
    }

if __name__ == "__main__":
    # 示例使用
    async def main():
        # 单个回测
        result = await run_single_backtest('BTC/USDT', days_back=7, timeframe='1h')
        print("单个回测结果:", result)
        
        # 组合回测
        portfolio_result = await run_portfolio_backtest(
            ['BTC/USDT', 'ETH/USDT', 'BNB/USDT'],
            days_back=7,
            timeframe='1h'
        )
        print("组合回测结果:", portfolio_result)
    
    asyncio.run(main())
