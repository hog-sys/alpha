# crypto_scout.py
# 作用：作为一个独立的微服务，持续监听加密货币扫描任务，
# 执行分析，并将结果存入数据库。

import json
import time
import random # 用于模拟分析结果
from messaging_client import MessagingClient
from database import Database, Signal

# 定义这个 Scout 监听的队列名称和其在数据库中的源名称
QUEUE_NAME = 'crypto_scan_tasks'
SOURCE_NAME = 'crypto_scout'

class CryptoAnalyzer:
    """
    封装了加密货币分析的核心逻辑。
    在实际应用中，这里会包含连接交易所、获取数据、
    计算技术指标、运行机器学习模型等复杂操作。
    """
    def __init__(self):
        # 初始化可能需要的客户端或模型
        # from config import settings
        # self.exchange_client = ccxt.binance({ ... })
        print("CryptoAnalyzer initialized.")

    def analyze(self, task: dict):
        """
        执行分析任务并返回结果列表。
        这是一个模拟实现，实际中应替换为真实的分析逻辑。
        """
        print(f"Analyzing task: {task}")
        symbols = task.get('symbols', [])
        results = []

        for symbol in symbols:
            # --- 在这里插入您原来的核心分析逻辑 ---
            # 1. 从交易所获取K线数据 (e.g., using ccxt)
            # 2. 计算技术指标 (e.g., RSI, MACD)
            # 3. (可选) 调用 ML 模型进行预测
            # 4. 生成信号
            
            # 模拟分析过程
            time.sleep(random.uniform(0.5, 2.0)) 
            
            # 模拟生成一个信号
            mock_price = 60000 + random.uniform(-500, 500)
            mock_signal = random.choice(['BUY', 'SELL', 'HOLD'])
            
            if mock_signal != 'HOLD':
                result = {
                    'symbol': symbol,
                    'signal_type': mock_signal,
                    'price': round(mock_price, 2),
                    'source': SOURCE_NAME,
                    'metadata': { # 可以存储一些额外的分析依据
                        'rsi': round(random.uniform(20, 80), 2),
                        'macd_hist': round(random.uniform(-100, 100), 2)
                    }
                }
                results.append(result)
        
        print(f"Analysis complete. Found {len(results)} signals.")
        return results

def process_task_message(ch, method, properties, body):
    """
    这是 RabbitMQ 的核心回调函数。
    每当从队列中收到一条消息，这个函数就会被自动调用。
    """
    try:
        task = json.loads(body)
        print(f"\n[+] Received task: {task}")
        
        # 1. 执行分析
        analyzer = CryptoAnalyzer()
        signals = analyzer.analyze(task)
        
        # 2. 如果有信号，存入数据库
        if signals:
            db = Database()
            for signal_data in signals:
                db.save_signal(signal_data)
        
        # 3. 确认消息处理完毕
        # 这会告诉 RabbitMQ 可以安全地从队列中删除这条消息了。
        ch.basic_ack(delivery_tag=method.delivery_tag)
        print(f"[✔] Task processed successfully. Acknowledged message.")

    except json.JSONDecodeError as e:
        print(f"[!] Failed to decode message body: {e}")
        # 拒绝消息，并且不要重新排队，因为它格式错误
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except Exception as e:
        print(f"[!] An unexpected error occurred: {e}")
        # 发生未知错误，拒绝消息但允许其重新排队，以便稍后重试
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


def main():
    """
    启动 Crypto Scout 服务。
    """
    print(f"--- Crypto Scout Service starting ---")
    print(f"--- Listening for tasks on queue: '{QUEUE_NAME}' ---")
    
    messaging_client = MessagingClient()
    messaging_client.declare_queue(QUEUE_NAME)
    messaging_client.consume_messages(QUEUE_NAME, process_task_message)

if __name__ == '__main__':
    main()