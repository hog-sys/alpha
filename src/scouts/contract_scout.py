# contract_scout.py
# 作用：作为一个独立的微服务，持续监听智能合约扫描任务。

import json
import time
import random
from messaging_client import MessagingClient
from database import Database

# 定义这个 Scout 监听的队列名称和其在数据库中的源名称
QUEUE_NAME = 'contract_scan_tasks'
SOURCE_NAME = 'contract_scout'

class ContractAnalyzer:
    """
    封装了智能合约分析的核心逻辑。
    在实际应用中，这里会包含使用 GoPlus/Dextools 等API
    进行安全审计分析。
    """
    def __init__(self):
        print("ContractAnalyzer initialized.")

    def analyze(self, task: dict):
        """
        执行合约分析任务并返回结果列表。
        这是一个模拟实现。
        """
        print(f"Analyzing contract task: {task}")
        contract_address = task.get('address', '0x...')
        results = []

        # 模拟合约分析过程
        time.sleep(random.uniform(0.5, 1.5))
        
        # 模拟发现一个值得关注的合约事件
        is_honeypot = random.choice([True, False])
        
        if not is_honeypot:
            result = {
                'symbol': contract_address,
                'signal_type': 'LOW_RISK_CONTRACT',
                'price': None,
                'source': SOURCE_NAME,
                'metadata': {
                    'is_honeypot': is_honeypot,
                    'buy_tax': round(random.uniform(0, 5), 2),
                    'sell_tax': round(random.uniform(0, 5), 2),
                    'chain': task.get('chain')
                }
            }
            results.append(result)
        
        print(f"Contract analysis complete. Found {len(results)} signals.")
        return results

def process_task_message(ch, method, properties, body):
    """ RabbitMQ 的核心回调函数 """
    try:
        # 假设任务是一个地址列表
        tasks = json.loads(body)
        print(f"\n[+] Received contract task for {len(tasks)} addresses")
        
        analyzer = ContractAnalyzer()
        db = Database()

        for task in tasks:
            signals = analyzer.analyze(task)
            if signals:
                for signal_data in signals:
                    db.save_signal(signal_data)
        
        ch.basic_ack(delivery_tag=method.delivery_tag)
        print(f"[✔] Contract task processed successfully.")

    except Exception as e:
        print(f"[!] An error occurred in contract scout: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

def main():
    """ 启动 Contract Scout 服务 """
    print(f"--- Contract Scout Service starting ---")
    print(f"--- Listening for tasks on queue: '{QUEUE_NAME}' ---")
    
    messaging_client = MessagingClient()
    messaging_client.declare_queue(QUEUE_NAME)
    messaging_client.consume_messages(QUEUE_NAME, process_task_message)

if __name__ == '__main__':
    main()
