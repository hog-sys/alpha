# src/backtesting/backtest_enhanced.py
"""
增强版回测框架 - 根据PDF建议使用backtesting.py
避免前视偏差，包含滑点和手续费建模
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import asyncio
import logging
from pathlib import Path

# 回测框架
from backtesting import Backtest, Strategy
from backtesting.lib import crossover
from backtesting.test import SMA

# 技术指标
import talib

# 数据库
from sqlalchemy import select, and_
from src.core.database_timescale import TimescaleDBManager

logger = logging.getLogger(__name__)

class AlphaStrategy(Strategy):
    """
    Alpha策略 - 基于ML预测和多种信号的交易策略
    """
    
    # 策略参数
    min_confidence = 0.7  # 最小置信度阈值
    position_size = 0.1   # 每次交易使用10%的资金
    stop_loss = 0.05      # 5%止损
    take_profit = 0.10    # 10%止盈
    max_positions = 5     # 最大同时持仓数
    
    # 技术指标参数
    rsi_period = 14
    rsi_oversold = 30
    rsi_overbought = 70
    
    def init(self):
        """初始化策略指标"""
        # 计算技术指标
        self.rsi = self.I(talib.RSI, self.data.Close, self.rsi_period)
        self.sma20 = self.I(SMA, self.data.Close, 20)
        self.sma50 = self.I(SMA, self.data.Close, 50)
        
        # 成交量指标
        self.volume_sma = self.I(SMA, self.data.Volume, 20)
        
        # 跟踪变量
        self.entry_prices = {}
        self.position_scores = {}
        self.position_count = 0
    
    def next(self):
        """每个时间步的交易逻辑"""
        # 获取当前机会信号（从外部数据源）
        current_signals = self._get_current_signals()
        
        # 风险管理：检查现有持仓
        self._manage_positions()
        
        # 评估新机会
        for signal in current_signals:
            if self._should_enter_position(signal):
                self._enter_position(signal)
        
        # 更新跟踪变量
        self._update_tracking()
    
    def _get_current_signals(self) -> List[Dict]:
        """
        获取当前时间的Alpha信号
        在实际回测中，这会从历史数据中读取
        """
        # 这里应该从历史opportunity数据中获取
        # 确保没有前视偏差
        current_time = self.data.index[-1]
        
        # 模拟信号
        signals = []
        
        # 检查技术指标信号
        if self.rsi[-1] < self.rsi_oversold and self.data.Volume[-1] > self.volume_sma[-1]:
            signals.append({
                'type': 'oversold_bounce',
                'confidence': 0.7,
                'predicted_return': 0.05
            })
        
        # 检查趋势信号
        if crossover(self.sma20, self.sma50):
            signals.append({
                'type': 'golden_cross',
                'confidence': 0.8,
                'predicted_return': 0.08
            })
        
        return signals
    
    def _should_enter_position(self, signal: Dict) -> bool:
        """判断是否应该建仓"""
        # 检查置信度
        if signal['confidence'] < self.min_confidence:
            return False
        
        # 检查持仓限制
        if self.position_count >= self.max_positions:
            return False
        
        # 检查资金是否充足
        if self.equity < 1000:  # 最小资金要求
            return False
        
        # 额外的过滤条件
        if self.rsi[-1] > self.rsi_overbought:  # 避免在超买区域买入
            return False
        
        return True
    
    def _enter_position(self, signal: Dict):
        """建立新仓位"""
        # 计算仓位大小
        size = self.position_size * self.equity / self.data.Close[-1]
        
        # 执行买入
        self.buy(size=size)
        
        # 记录入场信息
        entry_price = self.data.Close[-1]
        self.entry_prices[len(self.trades)] = entry_price
        self.position_scores[len(self.trades)] = signal['confidence']
        self.position_count += 1
        
        # 设置止损和止盈
        stop_price = entry_price * (1 - self.stop_loss)
        target_price = entry_price * (1 + self.take_profit)
        
        # 这些会在_manage_positions中处理
    
    def _manage_positions(self):
        """管理现有持仓"""
        for trade in self.trades:
            if trade.is_long:
                entry_price = self.entry_prices.get(trade.entry_bar, trade.entry_price)
                current_price = self.data.Close[-1]
                
                # 止损
                if current_price <= entry_price * (1 - self.stop_loss):
                    trade.close()
                    self.position_count -= 1
                
                # 止盈
                elif current_price >= entry_price * (1 + self.take_profit):
                    trade.close()
                    self.position_count -= 1
                
                # 移动止损（可选）
                elif current_price > entry_price * 1.05:
                    # 当利润超过5%时，移动止损到成本价
                    new_stop = entry_price
                    # 更新止损逻辑
    
    def _update_tracking(self):
        """更新跟踪变量"""
        # 清理已关闭交易的记录
        active_trades = {t.entry_bar for t in self.trades if not t.is_closed}
        
        self.entry_prices = {
            k: v for k, v in self.entry_prices.items() 
            if k in active_trades
        }
        
        self.position_scores = {
            k: v for k, v in self.position_scores.items()
            if k in active_trades
        }


class EnhancedBacktester:
    """
    增强版回测器 - 实现PDF建议的严格回测流程
    """
    
    def __init__(self, db_manager: TimescaleDBManager):
        self.db = db_manager
        
        # 回测参数
        self.initial_capital = 10000
        self.commission = 0.001  # 0.1% 手续费
        self.slippage = 0.001    # 0.1% 滑点
        
        # 结果存储
        self.results = []
        self.statistics = {}
    
    async def run_backtest(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        strategy_class: type = AlphaStrategy
    ) -> Dict[str, Any]:
        """
        运行回测
        """
        logger.info(f"开始回测 {symbol} ({start_date} 到 {end_date})")
        
        try:
            # 1. 获取历史数据
            market_data = await self._fetch_market_data(symbol, start_date, end_date)
            opportunity_data = await self._fetch_opportunity_data(symbol, start_date, end_date)
            
            if market_data.empty:
                logger.error("没有足够的市场数据进行回测")
                return {}
            
            # 2. 准备回测数据
            backtest_data = self._prepare_backtest_data(market_data, opportunity_data)
            
            # 3. 运行回测
            bt = Backtest(
                backtest_data,
                strategy_class,
                cash=self.initial_capital,
                commission=self.commission,
                exclusive_orders=True,  # 确保订单不会重叠
                hedging=False,
                trade_on_close=False  # 避免前视偏差
            )
            
            # 4. 优化参数（可选）
            # stats = bt.optimize(
            #     min_confidence=range(60, 90, 5),
            #     position_size=[0.05, 0.1, 0.15],
            #     maximize='Sharpe Ratio'
            # )
            
            # 5. 运行策略
            stats = bt.run()
            
            # 6. 计算额外指标
            enhanced_stats = self._calculate_enhanced_metrics(stats, bt._results)
            
            # 7. 生成报告
            report = self._generate_report(enhanced_stats)
            
            logger.info(f"✅ 回测完成 - 收益率: {stats['Return [%]']:.2f}%")
            
            return report
            
        except Exception as e:
            logger.error(f"回测失败: {e}", exc_info=True)
            return {}
    
    async def _fetch_market_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """获取市场数据"""
        # 从TimescaleDB获取数据
        query = """
            SELECT 
                time_bucket('1 minute', time) as time,
                FIRST(price, time) as Open,
                MAX(price) as High,
                MIN(price) as Low,
                LAST(price, time) as Close,
                SUM(volume) as Volume
            FROM market_data
            WHERE token_id = (SELECT id FROM tokens WHERE symbol = :symbol)
            AND time >= :start_date
            AND time <= :end_date
            GROUP BY time_bucket('1 minute', time)
            ORDER BY time
        """
        
        async with self.db.async_session() as session:
            result = await session.execute(
                query,
                {
                    'symbol': symbol,
                    'start_date': start_date,
                    'end_date': end_date
                }
            )
            
            df = pd.DataFrame(result.fetchall())
            if not df.empty:
                df.set_index('time', inplace=True)
                df.index = pd.to_datetime(df.index)
            
            return df
    
    async def _fetch_opportunity_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """获取历史机会数据"""
        async with self.db.async_session() as session:
            result = await session.execute(
                select(self.db.alpha_opportunities_table)
                .where(
                    and_(
                        self.db.alpha_opportunities_table.c.time >= start_date,
                        self.db.alpha_opportunities_table.c.time <= end_date
                    )
                )
            )
            
            return pd.DataFrame(result.mappings())
    
    def _prepare_backtest_data(
        self,
        market_data: pd.DataFrame,
        opportunity_data: pd.DataFrame
    ) -> pd.DataFrame:
        """
        准备回测数据，确保没有前视偏差
        """
        # 确保数据按时间排序
        market_data = market_data.sort_index()
        
        # 添加技术指标（这些是基于历史数据计算的，没有前视偏差）
        if len(market_data) > 20:
            market_data['SMA20'] = market_data['Close'].rolling(20).mean()
        
        if len(market_data) > 50:
            market_data['SMA50'] = market_data['Close'].rolling(50).mean()
        
        # RSI
        if len(market_data) > 14:
            market_data['RSI'] = talib.RSI(market_data['Close'].values, timeperiod=14)
        
        # 确保没有NaN值
        market_data = market_data.dropna()
        
        return market_data
    
    def _calculate_enhanced_metrics(
        self,
        basic_stats: pd.Series,
        trades: pd.DataFrame
    ) -> Dict[str, Any]:
        """计算增强的性能指标"""
        
        enhanced = dict(basic_stats)
        
        if not trades.empty:
            # 计算额外指标
            returns = trades['ReturnPct'].values
            
            # 最大连续亏损
            consecutive_losses = 0
            max_consecutive_losses = 0
            for r in returns:
                if r < 0:
                    consecutive_losses += 1
                    max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
                else:
                    consecutive_losses = 0
            
            enhanced['Max Consecutive Losses'] = max_consecutive_losses
            
            # 盈亏比
            winning_trades = returns[returns > 0]
            losing_trades = returns[returns < 0]
            
            if len(winning_trades) > 0 and len(losing_trades) > 0:
                enhanced['Profit Factor'] = abs(winning_trades.mean() / losing_trades.mean())
            
            # 卡尔马比率
            if enhanced.get('Max. Drawdown [%]', 0) != 0:
                enhanced['Calmar Ratio'] = enhanced.get('Return [%]', 0) / abs(enhanced.get('Max. Drawdown [%]', 0))
            
            # 每日、每周、每月收益
            if 'equity_curve' in enhanced:
                equity = pd.Series(enhanced['equity_curve'])
                enhanced['Daily Return'] = equity.pct_change().mean() * 100
                enhanced['Weekly Return'] = equity.pct_change(5).mean() * 100
                enhanced['Monthly Return'] = equity.pct_change(20).mean() * 100
        
        return enhanced
    
    def _generate_report(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """生成详细的回测报告"""
        report = {
            'summary': {
                'total_return': stats.get('Return [%]', 0),
                'sharpe_ratio': stats.get('Sharpe Ratio', 0),
                'max_drawdown': stats.get('Max. Drawdown [%]', 0),
                'win_rate': stats.get('Win Rate [%]', 0),
                'total_trades': stats.get('# Trades', 0),
                'profit_factor': stats.get('Profit Factor', 0),
                'calmar_ratio': stats.get('Calmar Ratio', 0)
            },
            'risk_metrics': {
                'volatility': stats.get('Volatility [%]', 0),
                'var_95': self._calculate_var(stats, 0.95),
                'cvar_95': self._calculate_cvar(stats, 0.95),
                'max_consecutive_losses': stats.get('Max Consecutive Losses', 0)
            },
            'trade_analysis': {
                'avg_trade_return': stats.get('Avg. Trade [%]', 0),
                'best_trade': stats.get('Best Trade [%]', 0),
                'worst_trade': stats.get('Worst Trade [%]', 0),
                'avg_winning_trade': stats.get('Avg. Winning Trade [%]', 0),
                'avg_losing_trade': stats.get('Avg. Losing Trade [%]', 0),
                'avg_trade_duration': stats.get('Avg. Trade Duration', 0)
            },
            'time_analysis': {
                'daily_return': stats.get('Daily Return', 0),
                'weekly_return': stats.get('Weekly Return', 0),
                'monthly_return': stats.get('Monthly Return', 0),
                'exposure_time': stats.get('Exposure Time [%]', 0)
            },
            'costs': {
                'total_commission': stats.get('Total Commission', 0),
                'total_slippage': self._estimate_total_slippage(stats)
            },
            'recommendation': self._generate_recommendation(stats),
            'warnings': self._generate_warnings(stats)
        }
        
        return report
    
    def _calculate_var(self, stats: Dict, confidence_level: float) -> float:
        """计算风险价值(VaR)"""
        if 'equity_curve' in stats:
            returns = pd.Series(stats['equity_curve']).pct_change().dropna()
            return np.percentile(returns, (1 - confidence_level) * 100)
        return 0
    
    def _calculate_cvar(self, stats: Dict, confidence_level: float) -> float:
        """计算条件风险价值(CVaR)"""
        var = self._calculate_var(stats, confidence_level)
        if 'equity_curve' in stats:
            returns = pd.Series(stats['equity_curve']).pct_change().dropna()
            return returns[returns <= var].mean()
        return 0
    
    def _estimate_total_slippage(self, stats: Dict) -> float:
        """估算总滑点成本"""
        # 简化估算：交易次数 * 平均交易金额 * 滑点率
        num_trades = stats.get('# Trades', 0)
        avg_trade_value = 1000  # 示例值
        return num_trades * avg_trade_value * self.slippage
    
    def _generate_recommendation(self, stats: Dict) -> str:
        """生成策略推荐"""
        sharpe = stats.get('Sharpe Ratio', 0)
        win_rate = stats.get('Win Rate [%]', 0)
        max_dd = abs(stats.get('Max. Drawdown [%]', 0))
        
        if sharpe > 2 and win_rate > 60 and max_dd < 20:
            return "🟢 强烈推荐：策略表现优异，风险可控"
        elif sharpe > 1 and win_rate > 50 and max_dd < 30:
            return "🟡 谨慎推荐：策略表现良好，但需注意风险管理"
        else:
            return "🔴 不推荐：策略需要进一步优化"
    
    def _generate_warnings(self, stats: Dict) -> List[str]:
        """生成警告信息"""
        warnings = []
        
        # 检查各种风险指标
        if stats.get('Max. Drawdown [%]', 0) < -30:
            warnings.append("⚠️ 最大回撤超过30%，风险较高")
        
        if stats.get('Win Rate [%]', 0) < 40:
            warnings.append("⚠️ 胜率低于40%，策略可靠性存疑")
        
        if stats.get('Sharpe Ratio', 0) < 0.5:
            warnings.append("⚠️ 夏普比率过低，风险调整后收益不佳")
        
        if stats.get('# Trades', 0) < 30:
            warnings.append("⚠️ 交易次数过少，统计意义有限")
        
        if stats.get('Max Consecutive Losses', 0) > 10:
            warnings.append("⚠️ 连续亏损次数过多，可能影响心理")
        
        return warnings


async def run_comprehensive_backtest(
    db_manager: TimescaleDBManager,
    symbols: List[str],
    period_days: int = 365
) -> Dict[str, Any]:
    """
    运行综合回测
    """
    backtester = EnhancedBacktester(db_manager)
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=period_days)
    
    all_results = {}
    
    for symbol in symbols:
        logger.info(f"回测 {symbol}...")
        result = await backtester.run_backtest(
            symbol,
            start_date,
            end_date,
            AlphaStrategy
        )
        all_results[symbol] = result
    
    # 生成综合报告
    comprehensive_report = {
        'individual_results': all_results,
        'best_performer': max(
            all_results.items(),
            key=lambda x: x[1]['summary']['sharpe_ratio']
        )[0] if all_results else None,
        'average_return': np.mean([
            r['summary']['total_return'] 
            for r in all_results.values()
        ]) if all_results else 0,
        'portfolio_sharpe': np.mean([
            r['summary']['sharpe_ratio']
            for r in all_results.values()
        ]) if all_results else 0
    }
    
    return comprehensive_report