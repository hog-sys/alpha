# src/scouts/contract_runner.py
"""Contract Scout Runner – 实时智能合约安全/质量检测。

数据来源：
1. GoPlus Web3 Security API  (https://docs.gopluslabs.io/)
2. Etherscan API            (https://docs.etherscan.io/)

读取任务来源：当前版本使用简单地址列表（环境变量 CONTRACT_ADDRESSES，逗号分隔）
或随机生成演示地址；后续可通过链上新合约事件 / RabbitMQ 任务队列注入。
"""
import asyncio
import os
import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta
import aiohttp

from src.scouts.base_scout import BaseScout, OpportunitySignal
from src.core.messaging import MessagePriority

logger = logging.getLogger(__name__)
GOPLUS_BASE = "https://api.gopluslabs.io/api/v1"
ETHERSCAN_BASE = "https://api.etherscan.io/api"

class ContractScout(BaseScout):
    async def _initialize(self):
        self.goplus_key = os.getenv("GOPLUS_API_KEY", "")
        self.etherscan_key = os.getenv("ETHERSCAN_API_KEY", "")
        # 监控的链与地址来源
        self.chain = os.getenv("CONTRACT_CHAIN", "eth")  # goplus chain short name
        addr_env = os.getenv("CONTRACT_ADDRESSES", "")
        self.addresses = [a.strip().lower() for a in addr_env.split(",") if a.strip()] or [
            # fallback demo addresses (USDT, LINK)
            "0xdAC17F958D2ee523a2206206994597C13D831ec7".lower(),
            "0x514910771AF9Ca656af840dff83E8264EcF986CA".lower(),
        ]
        self.scan_interval = int(os.getenv("SCAN_INTERVAL", "300"))

    async def fetch_goplus(self, address: str) -> Dict[str, Any]:
        url = f"{GOPLUS_BASE}/token_security/{self.chain}?contract_addresses={address}"
        if self.goplus_key:
            url += f"&apikey={self.goplus_key}"
        async with self.session.get(url, timeout=20) as resp:
            data = await resp.json()
            return data.get("result", {}).get(address, {})

    async def fetch_etherscan_source(self, address: str) -> Dict[str, Any]:
        if not self.etherscan_key:
            return {}
        params = {
            "module": "contract",
            "action": "getsourcecode",
            "address": address,
            "apikey": self.etherscan_key,
        }
        async with self.session.get(ETHERSCAN_BASE, params=params, timeout=20) as resp:
            data = await resp.json(content_type=None)
            if data.get("status") == "1":
                return data["result"][0]  # first entry
            return {}

    async def analyze_address(self, address: str) -> OpportunitySignal | None:
        try:
            goplus_task = asyncio.create_task(self.fetch_goplus(address))
            etherscan_task = asyncio.create_task(self.fetch_etherscan_source(address))
            goplus, etherscan = await asyncio.gather(goplus_task, etherscan_task, return_exceptions=False)

            if not goplus:
                logger.warning("GoPlus 未返回数据 %s", address)
                return None
            risk_score = float(goplus.get("token_security", {}).get("total_score", 100))  # 0 安全, 100 高危
            confidence = max(0.1, (100 - risk_score) / 100)  # 安全→高置信
            high_risk = risk_score > 60  # 阈值可调

            verified = bool(etherscan.get("SourceCode")) if etherscan else False
            creator = etherscan.get("ContractCreator") if etherscan else None

            signal_type = "high_risk_contract" if high_risk else "low_risk_contract"
            opp = self.create_opportunity(
                signal_type=signal_type,
                symbol=address,
                confidence=confidence,
                data={
                    "goplus": goplus,
                    "verified": verified,
                    "creator": creator,
                    "chain": self.chain,
                },
                expires_in_minutes=60,
            )
            return opp
        except Exception as e:
            logger.error("分析合约失败 %s: %s", address, e)
            return None

    async def scan(self) -> List[OpportunitySignal]:
        tasks = [self.analyze_address(addr) for addr in self.addresses]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        return [r for r in results if r]

async def main():
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    scout = ContractScout({})
    await scout.initialize()
    interval = scout.scan_interval
    try:
        while True:
            opps = await scout.scan()
            await scout.publish_opportunities(opps)
            await asyncio.sleep(interval)
    except KeyboardInterrupt:
        logger.info("ContractRunner 停止")
    finally:
        await scout.cleanup()

if __name__ == "__main__":
    asyncio.run(main())

