"""
链上Scout - 监控链上活动和趋势
"""
import asyncio
from typing import List, Dict, Any
from datetime import datetime, timedelta
import logging
from web3 import Web3
from .base_scout import BaseScout, OpportunitySignal

logger = logging.getLogger(__name__)

class ChainScout(BaseScout):
    """链上活动扫描器"""
    
    async def _initialize(self):
        """初始化链上Scout"""
        self.chains = self.config.get('chains', ['ethereum', 'bsc'])
        
        # 巨鲸地址阈值
        self.whale_thresholds = self.config.get('whale_thresholds', {
            'ETH': 1000,
            'BNB': 5000,
            'USDT': 1000000,
            'USDC': 1000000
        })
        
        # 已知的地址标签
        self.known_addresses = {
            # 交易所地址
            'exchanges': {
                '0x28C6c06298d514Db089934071355E5743bf21d60': 'Binance',
                '0xDFd5293D8e347dFe59E90eFd55b2956a1343963d': 'Binance',
                '0x56Eddb7aa87536c09CCc2793473599fD21A8b17F': 'Binance',
                '0x9696f59E4d72E237BE84fFD425DCaD154Bf96976': 'Binance',
                '0x21a31Ee1afC51d94C2eFcCAa2092aD1028285549': 'Binance',
                '0xb5d85CBf7cB3EE0D56b3bB207D5Fc4B82f43F511': 'Coinbase',
                '0xeB2629a2734e272Bcc07BDA959863f316F4bD4Cf': 'Coinbase',
                '0xA090e606E30bD747d4E6245a1517EbE430F0057e': 'Coinbase'
            },
            # 知名钱包
            'smart_money': {
                # 这里可以添加已知的聪明钱地址
            }
        }
        
        # Gas价格历史
        self.gas_history = {}
        
        # 初始化Web3连接
        self.w3_connections = {}
        await self._init_web3_connections()
    
    async def _init_web3_connections(self):
        """初始化Web3连接"""
        from config.settings import settings
        
        for chain in self.chains:
            if chain in settings.WEB3_PROVIDERS:
                try:
                    w3 = Web3(Web3.HTTPProvider(settings.WEB3_PROVIDERS[chain]))
                    if w3.is_connected():
                        self.w3_connections[chain] = w3
                        logger.info(f"✅ 连接到 {chain} 网络")
                except Exception as e:
                    logger.error(f"连接 {chain} 失败: {e}")
    
    async def scan(self) -> List[OpportunitySignal]:
        """扫描链上活动"""
        opportunities = []
        
        tasks = [
            self._scan_whale_movements(),
            self._scan_exchange_flows(),
            self._scan_gas_anomalies(),
            self._scan_smart_money(),
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, list):
                opportunities.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"链上扫描错误: {result}")
                
        return opportunities
    
    async def _scan_whale_movements(self) -> List[OpportunitySignal]:
        """扫描巨鲸转账"""
        opportunities = []
        
        for chain, w3 in self.w3_connections.items():
            try:
                latest_block = w3.eth.block_number
                
                # 扫描最近几个区块
                for block_num in range(latest_block - 5, latest_block + 1):
                    block = w3.eth.get_block(block_num, full_transactions=True)
                    
                    for tx in block.transactions:
                        # ETH转账
                        eth_value = w3.from_wei(tx.value, 'ether')
                        
                        if eth_value >= self.whale_thresholds.get('ETH', 1000):
                            # 识别地址
                            from_label = self._get_address_label(tx['from'])
                            to_label = self._get_address_label(tx.to) if tx.to else 'Contract Creation'
                            
                            opportunity = self.create_opportunity(
                                signal_type='whale_movement',
                                symbol='ETH',
                                confidence=0.85,
                                data={
                                    'chain': chain,
                                    'tx_hash': tx.hash.hex(),
                                    'from_address': tx['from'],
                                    'to_address': tx.to,
                                    'from_label': from_label,
                                    'to_label': to_label,
                                    'value_eth': float(eth_value),
                                    'value_usd': float(eth_value) * 2000,  # 简化
                                    'block': block_num,
                                    'gas_used': tx.gas,
                                    'movement_type': self._classify_movement(from_label, to_label)
                                }
                            )
                            opportunities.append(opportunity)
                            
                            logger.info(f"🐋 巨鲸转账: {eth_value:.2f} ETH "
                                       f"从 {from_label or tx['from'][:10]} "
                                       f"到 {to_label or (tx.to[:10] if tx.to else 'Contract')}")
                            
                # 同时扫描ERC20代币转账
                # 这里需要监控Transfer事件
                
            except Exception as e:
                logger.error(f"扫描 {chain} 巨鲸转账失败: {e}")
                
        return opportunities
    
    def _get_address_label(self, address: str) -> str:
        """获取地址标签"""
        if not address:
            return None
            
        address = address.lower()
        
        # 检查交易所地址
        for exc_addr, exc_name in self.known_addresses['exchanges'].items():
            if address == exc_addr.lower():
                return exc_name
                
        # 检查聪明钱地址
        for smart_addr, label in self.known_addresses['smart_money'].items():
            if address == smart_addr.lower():
                return label
                
        return None
    
    def _classify_movement(self, from_label: str, to_label: str) -> str:
        """分类转账类型"""
        if from_label and 'exchange' in from_label.lower():
            return 'exchange_outflow'  # 交易所流出
        elif to_label and 'exchange' in to_label.lower():
            return 'exchange_inflow'   # 交易所流入
        elif from_label and to_label:
            return 'exchange_to_exchange'  # 交易所间转账
        else:
            return 'whale_transfer'    # 普通巨鲸转账
    
    async def _scan_exchange_flows(self) -> List[OpportunitySignal]:
        """扫描交易所资金流向"""
        opportunities = []
        
        # 统计各交易所的流入流出
        exchange_flows = {}
        
        for chain, w3 in self.w3_connections.items():
            try:
                latest_block = w3.eth.block_number
                
                # 初始化统计
                for exc_name in set(self.known_addresses['exchanges'].values()):
                    if exc_name not in exchange_flows:
                        exchange_flows[exc_name] = {
                            'inflow': 0,
                            'outflow': 0,
                            'net_flow': 0,
                            'tx_count': 0
                        }
                
                # 扫描最近的区块
                for block_num in range(latest_block - 10, latest_block + 1):
                    block = w3.eth.get_block(block_num, full_transactions=True)
                    
                    for tx in block.transactions:
                        from_label = self._get_address_label(tx['from'])
                        to_label = self._get_address_label(tx.to) if tx.to else None
                        eth_value = float(w3.from_wei(tx.value, 'ether'))
                        
                        # 统计流入
                        if to_label in exchange_flows and eth_value > 0:
                            exchange_flows[to_label]['inflow'] += eth_value
                            exchange_flows[to_label]['tx_count'] += 1
                            
                        # 统计流出
                        if from_label in exchange_flows and eth_value > 0:
                            exchange_flows[from_label]['outflow'] += eth_value
                            exchange_flows[from_label]['tx_count'] += 1
                
                # 分析异常流向
                for exc_name, flows in exchange_flows.items():
                    flows['net_flow'] = flows['inflow'] - flows['outflow']
                    
                    # 检查是否有显著的净流入/流出
                    if abs(flows['net_flow']) > 1000:  # 1000 ETH
                        opportunity = self.create_opportunity(
                            signal_type='exchange_flow',
                            symbol=f'{exc_name}@{chain}',
                            confidence=min(abs(flows['net_flow']) / 5000, 0.9),
                            data={
                                'chain': chain,
                                'exchange': exc_name,
                                'inflow_eth': flows['inflow'],
                                'outflow_eth': flows['outflow'],
                                'net_flow_eth': flows['net_flow'],
                                'tx_count': flows['tx_count'],
                                'flow_direction': 'inflow' if flows['net_flow'] > 0 else 'outflow',
                                'timeframe': '10_blocks'
                            }
                        )
                        opportunities.append(opportunity)
                        
                        logger.info(f"💸 交易所资金流: {exc_name} "
                                   f"净{'流入' if flows['net_flow'] > 0 else '流出'} "
                                   f"{abs(flows['net_flow']):.2f} ETH")
                                   
            except Exception as e:
                logger.error(f"扫描 {chain} 交易所流向失败: {e}")
                
        return opportunities
    
    async def _scan_gas_anomalies(self) -> List[OpportunitySignal]:
        """扫描Gas费异常"""
        opportunities = []
        
        for chain, w3 in self.w3_connections.items():
            try:
                # 获取当前gas价格
                gas_price = w3.eth.gas_price
                gas_price_gwei = w3.from_wei(gas_price, 'gwei')
                
                # 获取历史平均值
                if chain not in self.gas_history:
                    self.gas_history[chain] = []
                
                self.gas_history[chain].append(float(gas_price_gwei))
                
                # 保留最近100个数据点
                if len(self.gas_history[chain]) > 100:
                    self.gas_history[chain] = self.gas_history[chain][-100:]
                
                # 计算平均值和标准差
                if len(self.gas_history[chain]) >= 20:
                    import numpy as np
                    avg_gas = np.mean(self.gas_history[chain])
                    std_gas = np.std(self.gas_history[chain])
                    
                    # 检查是否异常（超过2个标准差）
                    if abs(gas_price_gwei - avg_gas) > 2 * std_gas:
                        opportunity = self.create_opportunity(
                            signal_type='gas_anomaly',
                            symbol=f'GAS@{chain}',
                            confidence=0.7,
                            data={
                                'chain': chain,
                                'current_gas_gwei': float(gas_price_gwei),
                                'avg_gas_gwei': avg_gas,
                                'std_gas_gwei': std_gas,
                                'deviation': (gas_price_gwei - avg_gas) / std_gas,
                                'anomaly_type': 'spike' if gas_price_gwei > avg_gas else 'drop'
                            }
                        )
                        opportunities.append(opportunity)
                        
                        logger.info(f"⛽ Gas异常: {chain} "
                                   f"当前: {gas_price_gwei:.2f} Gwei "
                                   f"(平均: {avg_gas:.2f})")
                                   
            except Exception as e:
                logger.error(f"扫描 {chain} Gas异常失败: {e}")
                
        return opportunities
    
    async def _scan_smart_money(self) -> List[OpportunitySignal]:
        """跟踪聪明钱动向"""
        opportunities = []
        
        # 这里可以添加已知的聪明钱地址
        # 监控他们的交易活动
        
        return opportunities