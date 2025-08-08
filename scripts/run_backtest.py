#!/usr/bin/env python3
# scripts/run_backtest.py
"""
回测脚本 - 便捷地运行各种回测场景
"""
import asyncio
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import json
import logging

# 添加项目根目录到路径
sys.path.append(str(Path(__file__).parent.parent))

from src.backtesting.backtest_strategy import (
    run_single_backtest,
    run_portfolio_backtest,
    BacktestRunner
)
from config.settings import get_config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def run_single_symbol_backtest(args):
    """运行单个币种回测"""
    logger.info(f"开始回测 {args.symbol}...")
    
    result = await run_single_backtest(
        symbol=args.symbol,
        days_back=args.days,
        timeframe=args.timeframe
    )
    
    if 'error' in result:
        logger.error(f"回测失败: {result['error']}")
        return
    
    # 打印结果
    print("\n" + "="*60)
    print(f"回测结果: {args.symbol}")
    print("="*60)
    print(f"总收益率: {result['total_return_pct']:.2f}%")
    print(f"买入持有收益率: {result['buy_hold_return_pct']:.2f}%")
    print(f"最大回撤: {result['max_drawdown_pct']:.2f}%")
    print(f"夏普比率: {result['sharpe_ratio']:.3f}")
    print(f"卡尔马比率: {result['calmar_ratio']:.3f}")
    print(f"总交易次数: {result['total_trades']}")
    print(f"胜率: {result['win_rate_pct']:.1f}%")
    print(f"平均交易收益: {result['avg_trade_pct']:.2f}%")
    print(f"盈利因子: {result['profit_factor']:.2f}")
    print("="*60)
    
    # 保存详细结果
    if args.output:
        output_file = Path(args.output)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        logger.info(f"详细结果已保存到: {output_file}")

async def run_portfolio_backtest_cmd(args):
    """运行投资组合回测"""
    symbols = args.symbols.split(',')
    logger.info(f"开始组合回测: {symbols}")
    
    result = await run_portfolio_backtest(
        symbols=symbols,
        days_back=args.days,
        timeframe=args.timeframe
    )
    
    # 打印组合统计
    portfolio_stats = result['portfolio_stats']
    
    print("\n" + "="*60)
    print("投资组合回测结果")
    print("="*60)
    print(f"平均收益率: {portfolio_stats['avg_return_pct']:.2f}%")
    print(f"中位数收益率: {portfolio_stats['median_return_pct']:.2f}%")
    print(f"最佳表现: {portfolio_stats['best_return_pct']:.2f}%")
    print(f"最差表现: {portfolio_stats['worst_return_pct']:.2f}%")
    print(f"平均夏普比率: {portfolio_stats['avg_sharpe_ratio']:.3f}")
    print(f"平均最大回撤: {portfolio_stats['avg_max_drawdown_pct']:.2f}%")
    print(f"成功率: {portfolio_stats['success_rate_pct']:.1f}%")
    print(f"总币种数: {portfolio_stats['total_symbols']}")
    print("="*60)
    
    # 打印个别结果
    print("\n个别币种表现:")
    print("-"*40)
    for symbol, res in result['individual_results'].items():
        if 'error' not in res:
            print(f"{symbol:12} | {res['total_return_pct']:+6.2f}% | 夏普: {res['sharpe_ratio']:5.2f}")
        else:
            print(f"{symbol:12} | ERROR: {res['error']}")
    
    # 保存结果
    if args.output:
        output_file = Path(args.output)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        logger.info(f"详细结果已保存到: {output_file}")

async def run_custom_backtest(args):
    """运行自定义回测"""
    config = get_config()
    runner = BacktestRunner(config)
    
    await runner.initialize()
    
    # 解析时间
    if args.start_date:
        start_date = datetime.fromisoformat(args.start_date)
    else:
        start_date = datetime.now() - timedelta(days=args.days)
    
    if args.end_date:
        end_date = datetime.fromisoformat(args.end_date)
    else:
        end_date = datetime.now()
    
    logger.info(f"自定义回测: {args.symbol} ({start_date} - {end_date})")
    
    result = await runner.run_backtest(
        symbol=args.symbol,
        start_date=start_date,
        end_date=end_date,
        timeframe=args.timeframe,
        initial_cash=args.cash,
        commission=args.commission
    )
    
    if 'error' in result:
        logger.error(f"回测失败: {result['error']}")
        return
    
    # 打印结果
    print("\n" + "="*60)
    print(f"自定义回测结果: {args.symbol}")
    print("="*60)
    print(f"时间范围: {start_date.date()} - {end_date.date()}")
    print(f"初始资金: ${args.cash:,.2f}")
    print(f"手续费率: {args.commission:.4f}")
    print(f"时间框架: {args.timeframe}")
    print("-"*60)
    print(f"总收益率: {result['total_return_pct']:.2f}%")
    print(f"买入持有收益率: {result['buy_hold_return_pct']:.2f}%")
    print(f"超额收益: {result['total_return_pct'] - result['buy_hold_return_pct']:.2f}%")
    print(f"最大回撤: {result['max_drawdown_pct']:.2f}%")
    print(f"波动率: {result['volatility_pct']:.2f}%")
    print(f"夏普比率: {result['sharpe_ratio']:.3f}")
    print(f"卡尔马比率: {result['calmar_ratio']:.3f}")
    print(f"总交易次数: {result['total_trades']}")
    print(f"胜率: {result['win_rate_pct']:.1f}%")
    print(f"平均交易收益: {result['avg_trade_pct']:.2f}%")
    print(f"最大交易持续时间: {result['max_trade_duration']}")
    print(f"平均交易持续时间: {result['avg_trade_duration']}")
    print(f"盈利因子: {result['profit_factor']:.2f}")
    print(f"SQN: {result['sqn']:.2f}")
    print("="*60)
    
    # 保存结果
    if args.output:
        output_file = Path(args.output)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        logger.info(f"详细结果已保存到: {output_file}")

def main():
    parser = argparse.ArgumentParser(
        description='Crypto Alpha Scout 回测工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 单币种快速回测 (最近7天)
  python scripts/run_backtest.py single BTC/USDT --days 7
  
  # 投资组合回测
  python scripts/run_backtest.py portfolio "BTC/USDT,ETH/USDT,BNB/USDT" --days 30
  
  # 自定义回测
  python scripts/run_backtest.py custom BTC/USDT \\
    --start-date 2024-01-01 --end-date 2024-01-31 \\
    --cash 100000 --commission 0.001 --timeframe 1h
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='回测模式')
    
    # 单币种回测
    single_parser = subparsers.add_parser('single', help='单币种回测')
    single_parser.add_argument('symbol', help='交易对符号 (e.g., BTC/USDT)')
    single_parser.add_argument('--days', type=int, default=30, help='回测天数 (默认30天)')
    single_parser.add_argument('--timeframe', default='1h', help='时间框架 (默认1h)')
    single_parser.add_argument('--output', help='输出文件路径 (JSON格式)')
    
    # 投资组合回测
    portfolio_parser = subparsers.add_parser('portfolio', help='投资组合回测')
    portfolio_parser.add_argument('symbols', help='交易对列表，用逗号分隔 (e.g., BTC/USDT,ETH/USDT)')
    portfolio_parser.add_argument('--days', type=int, default=30, help='回测天数 (默认30天)')
    portfolio_parser.add_argument('--timeframe', default='1h', help='时间框架 (默认1h)')
    portfolio_parser.add_argument('--output', help='输出文件路径 (JSON格式)')
    
    # 自定义回测
    custom_parser = subparsers.add_parser('custom', help='自定义回测')
    custom_parser.add_argument('symbol', help='交易对符号 (e.g., BTC/USDT)')
    custom_parser.add_argument('--start-date', help='开始日期 (YYYY-MM-DD)')
    custom_parser.add_argument('--end-date', help='结束日期 (YYYY-MM-DD)')
    custom_parser.add_argument('--days', type=int, default=30, help='回测天数 (如果没有指定开始日期)')
    custom_parser.add_argument('--timeframe', default='1h', help='时间框架 (默认1h)')
    custom_parser.add_argument('--cash', type=float, default=10000, help='初始资金 (默认10000)')
    custom_parser.add_argument('--commission', type=float, default=0.001, help='手续费率 (默认0.001)')
    custom_parser.add_argument('--output', help='输出文件路径 (JSON格式)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # 运行对应的回测
    if args.command == 'single':
        asyncio.run(run_single_symbol_backtest(args))
    elif args.command == 'portfolio':
        asyncio.run(run_portfolio_backtest_cmd(args))
    elif args.command == 'custom':
        asyncio.run(run_custom_backtest(args))

if __name__ == '__main__':
    main()
