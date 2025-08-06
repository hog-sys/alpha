# defi_scout.py
# 作用：作为一个独立的微服务，持续监听 DeFi 协议扫描任务。

import json
import time
import random
from messaging_client import MessagingClient
from database import Database

# 定义这个 Scout 监听的队列名称和其在数据库中的源名称
QUEUE_NAME = 'defi_scan_tasks'
SOURCE_NAME = 'defi_scout'

class DeFiAnalyzer:
    """
    封装了 DeFi 分析的核心逻辑。
    在实际应用中，这里会包含连接链上数据API、分析流动性池、
    寻找套利机会等复杂操作。
    """
    def __init__(self):
        print("DeFiAnalyzer initialized.")

    def analyze(self, task: dict):
        """
        执行 DeFi 分析任务并返回结果列表。
        这是一个模拟实现。
        """
        print(f"Analyzing DeFi task: {task}")
        protocol = task.get('protocol', 'Unknown')
        results = []

        # 模拟发现一个有潜力的流动性池
        time.sleep(random.uniform(1, 3))
        
        mock_pool = f"{random.choice(['WETH', 'USDC', 'DAI'])}/{random.choice(['WBTC', 'LINK', 'UNI'])}"
        mock_tvl = random.randint(500000, 10000000)
        
        # 只有当TVL大于任务要求的最小值时，才生成信号
        if mock_tvl > task.get('min_tvl', 0):
            result = {
                'symbol': mock_pool,
                'signal_type': 'POTENTIAL_OPPORTUNITY',
                'price': None, # DeFi 机会通常没有单一价格
                'source': SOURCE_NAME,
                'metadata': {
                    'protocol': protocol,
                    'tvl': mock_tvl,
                    'apy': round(random.uniform(5, 50), 2),
                    'chain': task.get('chain')
                }
            }
            results.append(result)
        
        print(f"DeFi analysis complete. Found {len(results)} opportunities.")
        return results

def process_task_message(ch, method, properties, body):
    """ RabbitMQ 的核心回调函数 """
    try:
        task = json.loads(body)
        print(f"\n[+] Received DeFi task: {task}")
        
        analyzer = DeFiAnalyzer()
        signals = analyzer.analyze(task)
        
        if signals:
            db = Database()
            for signal_data in signals:
                db.save_signal(signal_data)
        
        ch.basic_ack(delivery_tag=method.delivery_tag)
        print(f"[✔] DeFi task processed successfully.")

    except Exception as e:
        print(f"[!] An error occurred in DeFi scout: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

def main():
    """ 启动 DeFi Scout 服务 """
    print(f"--- DeFi Scout Service starting ---")
    print(f"--- Listening for tasks on queue: '{QUEUE_NAME}' ---")
    
    messaging_client = MessagingClient()
    messaging_client.declare_queue(QUEUE_NAME)
    messaging_client.consume_messages(QUEUE_NAME, process_task_message)

if __name__ == '__main__':
    main()
