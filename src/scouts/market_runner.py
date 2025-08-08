# src/scouts/market_runner.py
"""市场 Scout 运行入口 (异步)——替代旧 scout_manager 调度方式。
使用环境变量调整扫描周期等参数，独立启动后自动循环扫描并通过
MessageBus 发布机会到 RabbitMQ。

Docker 启动示例：
  python -m src.scouts.market_runner
"""
import asyncio
import os
import logging

from src.scouts.market_scout import MarketScout

logger = logging.getLogger(__name__)

async def main():
    scan_interval = int(os.getenv("SCAN_INTERVAL", "30"))
    min_profit_pct = float(os.getenv("MIN_PROFIT_PCT", "0.1"))

    config = {
        "scan_interval": scan_interval,
        "min_profit_pct": min_profit_pct,
        # 其它可从环境变量注入的参数...
    }

    scout = MarketScout(config)
    await scout.initialize()

    try:
        while True:
            opportunities = await scout.scan()
            await scout.publish_opportunities(opportunities)
            await asyncio.sleep(scan_interval)
    except KeyboardInterrupt:
        logger.info("MarketRunner 停止中 (Ctrl+C)")
    finally:
        await scout.cleanup()

if __name__ == "__main__":
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    asyncio.run(main())

