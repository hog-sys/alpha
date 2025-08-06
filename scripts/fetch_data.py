# fetch_data_secure.py
"""
安全版本的数据获取脚本 - 移除所有硬编码的API密钥
"""
import asyncio
import aiohttp
import pandas as pd
from datetime import datetime, timedelta
import time
import os
from typing import List, Dict, Optional
from pathlib import Path
import logging
from cryptography.fernet import Fernet
import json

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==============================================================================
# 安全配置加载
# ==============================================================================

class SecureConfig:
    """安全的配置管理器"""
    
    def __init__(self):
        self.config_file = Path.home() / '.crypto_scout' / 'config.enc'
        self.key_file = Path.home() / '.crypto_scout' / 'key.key'
        self._ensure_config_dir()
        self._load_or_create_key()
        
    def _ensure_config_dir(self):
        """确保配置目录存在"""
        config_dir = self.config_file.parent
        config_dir.mkdir(parents=True, exist_ok=True)
        # 设置严格的权限
        os.chmod(config_dir, 0o700)
    
    def _load_or_create_key(self):
        """加载或创建加密密钥"""
        if self.key_file.exists():
            with open(self.key_file, 'rb') as f:
                self.key = f.read()
        else:
            self.key = Fernet.generate_key()
            with open(self.key_file, 'wb') as f:
                f.write(self.key)
            os.chmod(self.key_file, 0o600)
        self.cipher = Fernet(self.key)
    
    def save_credentials(self, credentials: dict):
        """安全保存凭证"""
        encrypted = self.cipher.encrypt(json.dumps(credentials).encode())
        with open(self.config_file, 'wb') as f:
            f.write(encrypted)
        os.chmod(self.config_file, 0o600)
        logger.info("凭证已安全保存")
    
    def load_credentials(self) -> dict:
        """加载凭证"""
        if not self.config_file.exists():
            logger.warning("未找到凭证文件，请先配置API密钥")
            return self._prompt_for_credentials()
        
        try:
            with open(self.config_file, 'rb') as f:
                encrypted = f.read()
            decrypted = self.cipher.decrypt(encrypted)
            return json.loads(decrypted)
        except Exception as e:
            logger.error(f"加载凭证失败: {e}")
            return {}
    
    def _prompt_for_credentials(self) -> dict:
        """提示用户输入凭证"""
        print("\n首次运行，请配置API密钥（留空使用默认值）：")
        credentials = {
            'BINANCE_API_KEY': input("Binance API Key: ").strip() or "",
            'BINANCE_SECRET_KEY': input("Binance Secret Key: ").strip() or "",
            'COINGECKO_API_KEY': input("CoinGecko API Key: ").strip() or "",
            'POLYGON_API_KEY': input("Polygon API Key: ").strip() or "",
            'ALPHAVANTAGE_API_KEY': input("AlphaVantage API Key: ").strip() or ""
        }
        
        if any(credentials.values()):
            self.save_credentials(credentials)
        
        return credentials

# 初始化安全配置
secure_config = SecureConfig()
credentials = secure_config.load_credentials()

# ==============================================================================
# 安全的API配置
# ==============================================================================

# 从环境变量或安全存储加载，绝不硬编码
API_KEYS = {
    'BINANCE_API_KEY': os.getenv('BINANCE_API_KEY', credentials.get('BINANCE_API_KEY', '')),
    'BINANCE_SECRET_KEY': os.getenv('BINANCE_SECRET_KEY', credentials.get('BINANCE_SECRET_KEY', '')),
    'COINGECKO_API_KEY': os.getenv('COINGECKO_API_KEY', credentials.get('COINGECKO_API_KEY', '')),
    'POLYGON_API_KEY': os.getenv('POLYGON_API_KEY', credentials.get('POLYGON_API_KEY', '')),
    'ALPHAVANTAGE_API_KEY': os.getenv('ALPHAVANTAGE_API_KEY', credentials.get('ALPHAVANTAGE_API_KEY', ''))
}

# 数据配置
START_DATE = os.getenv('FETCH_START_DATE', "2022-01-01")
END_DATE = datetime.now().strftime("%Y-%m-%d")

TARGET_PAIRS = [
    "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT",
    "DOGE/USDT", "ADA/USDT", "AVAX/USDT", "LINK/USDT", "MATIC/USDT"
]
TIMEFRAME = "1h"
SAVE_PATH = "historical_data"
REQUEST_TIMEOUT = 20
RATE_LIMIT_DELAY = 1.2

# ==============================================================================
# 输入验证
# ==============================================================================

def validate_symbol(symbol: str) -> bool:
    """验证交易对符号格式"""
    import re
    pattern = r'^[A-Z]{2,10}/[A-Z]{2,10}$'
    return bool(re.match(pattern, symbol))

def validate_date(date_str: str) -> bool:
    """验证日期格式"""
    try:
        datetime.fromisoformat(date_str)
        return True
    except:
        return False

def sanitize_filename(filename: str) -> str:
    """清理文件名，防止路径遍历攻击"""
    import re
    # 移除潜在危险字符
    filename = re.sub(r'[^\w\-_\.]', '_', filename)
    # 防止路径遍历
    filename = filename.replace('..', '')
    return filename

# ==============================================================================
# 安全的数据拉取器基类
# ==============================================================================

class SecureDataFetcher:
    """安全的数据拉取器基类"""
    
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.request_count = 0
        self.last_request_time = 0
    
    async def _rate_limit(self):
        """速率限制"""
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            await asyncio.sleep(RATE_LIMIT_DELAY - elapsed)
        self.last_request_time = time.time()
        self.request_count += 1
    
    async def _safe_request(self, url: str, params: dict = None, headers: dict = None) -> Optional[dict]:
        """安全的HTTP请求"""
        await self._rate_limit()
        
        try:
            # 添加超时和重试逻辑
            timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
            
            # 清理headers，确保不泄露敏感信息
            safe_headers = headers or {}
            if 'Authorization' in safe_headers:
                # 不在日志中记录完整的认证信息
                logger.debug(f"请求 {url} (已认证)")
            else:
                logger.debug(f"请求 {url}")
            
            async with self.session.get(url, params=params, headers=safe_headers, timeout=timeout) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 429:
                    # 速率限制，等待后重试
                    logger.warning("触发速率限制，等待60秒...")
                    await asyncio.sleep(60)
                    return await self._safe_request(url, params, headers)
                else:
                    logger.error(f"请求失败: {response.status}")
                    return None
                    
        except asyncio.TimeoutError:
            logger.error(f"请求超时: {url}")
            return None
        except Exception as e:
            logger.error(f"请求异常: {type(e).__name__}")
            return None
    
    def _structure_dataframe_ohlcv(self, data: List[List]) -> pd.DataFrame:
        """安全地构建DataFrame"""
        if not data or not isinstance(data, list):
            return pd.DataFrame()
        
        # 验证数据格式
        for row in data:
            if not isinstance(row, list) or len(row) < 6:
                logger.warning("数据格式无效，跳过")
                continue
        
        processed_data = [row[:6] for row in data if len(row) >= 6]
        
        if not processed_data:
            return pd.DataFrame()
        
        df = pd.DataFrame(processed_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        # 数据验证
        try:
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            df = df.astype(float)
            
            # 检查数据合理性
            if (df['high'] < df['low']).any():
                logger.warning("发现异常数据：最高价低于最低价")
                df = df[df['high'] >= df['low']]
            
            if (df['close'] <= 0).any():
                logger.warning("发现异常数据：价格为零或负数")
                df = df[df['close'] > 0]
            
        except Exception as e:
            logger.error(f"数据处理错误: {e}")
            return pd.DataFrame()
        
        return df

# ==============================================================================
# 币安数据拉取器（安全版）
# ==============================================================================

class SecureBinanceFetcher(SecureDataFetcher):
    """安全的币安数据拉取器"""
    BASE_URL = "https://api.binance.com/api/v3/klines"
    
    async def fetch(self, symbol: str, start_date: str, end_date: str, timeframe: str) -> Optional[pd.DataFrame]:
        # 输入验证
        if not validate_symbol(symbol):
            logger.error(f"无效的交易对符号: {symbol}")
            return None
        
        if not validate_date(start_date) or not validate_date(end_date):
            logger.error("无效的日期格式")
            return None
        
        symbol_formatted = symbol.replace("/", "")
        
        try:
            start_ts = int(datetime.fromisoformat(start_date).timestamp() * 1000)
            end_ts = int(datetime.fromisoformat(end_date).timestamp() * 1000)
        except Exception as e:
            logger.error(f"日期转换错误: {e}")
            return None
        
        all_data = []
        current_ts = start_ts
        
        logger.info(f"开始从币安拉取 {symbol} 的数据...")
        
        while current_ts < end_ts:
            params = {
                "symbol": symbol_formatted,
                "interval": timeframe,
                "startTime": current_ts,
                "limit": 1000
            }
            
            data = await self._safe_request(self.BASE_URL, params)
            
            if not data:
                break
            
            all_data.extend(data)
            
            if len(data) < 1000:
                break
            
            current_ts = data[-1][0] + 1
            logger.debug(f"已拉取到 {pd.to_datetime(current_ts, unit='ms')}")
        
        if all_data:
            return self._structure_dataframe_ohlcv(all_data)
        return None

# ==============================================================================
# CoinGecko数据拉取器（安全版）
# ==============================================================================

class SecureCoinGeckoFetcher(SecureDataFetcher):
    """安全的CoinGecko数据拉取器"""
    BASE_URL = "https://api.coingecko.com/api/v3/coins/{id}/market_chart/range"
    
    SYMBOL_TO_ID = {
        "BTC/USDT": "bitcoin",
        "ETH/USDT": "ethereum",
        "BNB/USDT": "binancecoin",
        "SOL/USDT": "solana",
        "XRP/USDT": "ripple",
        "DOGE/USDT": "dogecoin",
        "ADA/USDT": "cardano",
        "AVAX/USDT": "avalanche-2",
        "LINK/USDT": "chainlink",
        "MATIC/USDT": "matic-network",
    }
    
    async def fetch(self, symbol: str, start_date: str, end_date: str, timeframe: str) -> Optional[pd.DataFrame]:
        if not validate_symbol(symbol):
            logger.error(f"无效的交易对符号: {symbol}")
            return None
        
        coin_id = self.SYMBOL_TO_ID.get(symbol)
        if not coin_id:
            logger.warning(f"CoinGecko不支持 {symbol}")
            return None
        
        # CoinGecko限制：只获取最近360天
        cg_end_date = datetime.now()
        cg_start_date = cg_end_date - timedelta(days=360)
        
        try:
            start_ts = int(cg_start_date.timestamp())
            end_ts = int(cg_end_date.timestamp())
        except Exception as e:
            logger.error(f"时间戳转换错误: {e}")
            return None
        
        logger.info(f"开始从CoinGecko拉取 {symbol} ({coin_id}) 的数据...")
        
        url = self.BASE_URL.format(id=coin_id)
        params = {
            "vs_currency": "usd",
            "from": start_ts,
            "to": end_ts
        }
        
        # 如果有API密钥，添加到headers
        headers = {}
        if API_KEYS.get('COINGECKO_API_KEY'):
            headers['X-Cg-Pro-Api-Key'] = API_KEYS['COINGECKO_API_KEY']
        
        data = await self._safe_request(url, params, headers)
        
        if not data or 'prices' not in data:
            return None
        
        try:
            # 安全地处理数据
            df = pd.DataFrame(data['prices'], columns=['timestamp', 'price'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # 重采样到指定时间框架
            ohlc = df['price'].resample('1h').ohlc()
            
            if 'total_volumes' in data:
                volume = pd.DataFrame(data['total_volumes'], columns=['timestamp', 'volume'])
                volume['timestamp'] = pd.to_datetime(volume['timestamp'], unit='ms')
                volume.set_index('timestamp', inplace=True)
                volume = volume['volume'].resample('1h').sum()
                
                final_df = ohlc.join(volume).dropna()
            else:
                final_df = ohlc.dropna()
            
            logger.info(f"CoinGecko数据处理完成，共 {len(final_df)} 条记录")
            return final_df
            
        except Exception as e:
            logger.error(f"数据处理失败: {e}")
            return None

# ==============================================================================
# 安全的主程序
# ==============================================================================

async def secure_main():
    """安全的主函数"""
    
    # 确保保存路径存在且安全
    save_path = Path(SAVE_PATH)
    save_path.mkdir(exist_ok=True, parents=True)
    
    # 创建安全的会话
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
    connector = aiohttp.TCPConnector(
        limit=10,  # 限制并发连接数
        ttl_dns_cache=300,
        ssl=True  # 强制使用SSL
    )
    
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        fetchers = {
            "binance": SecureBinanceFetcher(session),
            "coingecko": SecureCoinGeckoFetcher(session),
        }
        
        # 检查是否有可用的API密钥
        if not any(API_KEYS.values()):
            logger.warning("未配置API密钥，某些数据源可能无法使用")
        
        for pair in TARGET_PAIRS:
            for source_name, fetcher in fetchers.items():
                logger.info(f"\n--- 使用 {source_name.upper()} 拉取 {pair} ---")
                
                try:
                    df = await fetcher.fetch(pair, START_DATE, END_DATE, TIMEFRAME)
                    
                    if df is not None and not df.empty:
                        # 安全的文件名
                        filename = sanitize_filename(f"{pair.replace('/', '_')}_{source_name}_{TIMEFRAME}.csv")
                        filepath = save_path / filename
                        
                        # 保存前验证数据
                        if len(df) > 0 and df.index.is_monotonic_increasing:
                            df.to_csv(filepath)
                            logger.info(f"✅ 数据成功保存到: {filepath}")
                            
                            # 设置文件权限
                            os.chmod(filepath, 0o644)
                        else:
                            logger.warning(f"数据验证失败，跳过保存")
                    else:
                        logger.warning(f"❌ 未能从 {source_name.upper()} 获取 {pair} 的数据")
                        
                except Exception as e:
                    logger.error(f"处理 {pair} 时发生错误: {e}")
                    continue
                
                # 添加延迟避免速率限制
                await asyncio.sleep(RATE_LIMIT_DELAY)

def main():
    """入口函数"""
    try:
        # 设置事件循环策略
        if hasattr(asyncio, 'WindowsProactorEventLoopPolicy'):
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
        start_time = time.time()
        asyncio.run(secure_main())
        end_time = time.time()
        
        logger.info(f"\n🎉 所有任务完成，总耗时: {end_time - start_time:.2f} 秒")
        
    except KeyboardInterrupt:
        logger.info("\n用户中断执行")
    except Exception as e:
        logger.error(f"程序执行失败: {e}")
        raise

if __name__ == "__main__":
    main()
