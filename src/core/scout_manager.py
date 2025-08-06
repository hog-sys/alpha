# scout_manager.py
# 作用：作为系统的“任务调度中心”，定期向消息队列发布各种分析任务。

import time
import json
from messaging_client import MessagingClient

# 定义不同类型的任务队列
# 每个队列都对应一种特定的侦察任务
TASK_QUEUES = {
    'crypto': 'crypto_scan_tasks',
    'defi': 'defi_scan_tasks',
    'market': 'market_scan_tasks',
    'contract': 'contract_scan_tasks'
}

def main():
    """
    主函数现在是一个持续运行的循环，
    它定期创建任务并将其发布到 RabbitMQ。
    """
    print("--- Scout Manager started ---")
    messaging_client = MessagingClient()

    # 在启动时，先声明所有需要的队列，确保它们存在
    for queue_name in TASK_QUEUES.values():
        messaging_client.declare_queue(queue_name)
    
    print("All task queues declared.")

    # 任务发布的循环
    while True:
        try:
            print(f"\n--- Publishing new batch of tasks at {time.ctime()} ---")

            # 1. 创建并发布加密货币扫描任务
            crypto_task = {
                'task_type': 'scan_binance_symbols',
                'symbols': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT'],
                'interval': '1h'
            }
            messaging_client.publish_message(TASK_QUEUES['crypto'], crypto_task)

            # 2. 创建并发布 DeFi 扫描任务 (示例)
            defi_task = {
                'task_type': 'scan_liquidity_pools',
                'protocol': 'UniswapV3',
                'chain': 'Ethereum',
                'min_tvl': 1000000
            }
            messaging_client.publish_message(TASK_QUEUES['defi'], defi_task)

            # 3. 创建并发布市场情绪分析任务 (示例)
            market_task = {
                'task_type': 'analyze_market_sentiment',
                'sources': ['twitter', 'reddit']
            }
            messaging_client.publish_message(TASK_QUEUES['market'], market_task)
            
            # ... 在这里可以添加更多不同类型的任务 ...

            # 等待下一个调度周期
            sleep_duration = 300 # 5 分钟
            print(f"--- All tasks published. Sleeping for {sleep_duration} seconds. ---")
            time.sleep(sleep_duration)

        except KeyboardInterrupt:
            print("Scout Manager shutting down.")
            break
        except Exception as e:
            print(f"An error occurred in the main loop: {e}")
            # 在出现错误时等待一段时间再重试，防止CPU占用过高
            time.sleep(60)
    
    messaging_client.close()
    print("--- Scout Manager stopped ---")


if __name__ == "__main__":
    main()

    