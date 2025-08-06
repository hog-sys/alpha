# src/core/performance_optimizer.py

import asyncio
import psutil
import os
import sys
from typing import Dict
import logging

logger = logging.getLogger(__name__)

class PerformanceOptimizer:
    """性能优化器"""
    
    async def optimize_performance(self):
        """根据平台优化系统性能"""
        if sys.platform == 'win32':
            await self._optimize_windows()
        elif sys.platform == 'linux':
            await self._optimize_linux()
        else:
            logger.info(f"不支持的平台: {sys.platform}, 跳过性能优化。")

    async def _optimize_windows(self):
        """优化Windows系统性能"""
        logger.info("正在为Windows平台优化性能...")
        try:
            p = psutil.Process(os.getpid())
            
            # 设置进程优先级为高
            try:
                p.nice(psutil.HIGH_PRIORITY_CLASS)
            except Exception as e:
                # 修复：移除了f-string中的表情符号
                logger.warning(f"设置进程优先级失败: {e}")
            
            # 设置CPU亲和性（使用所有核心）
            try:
                p.cpu_affinity(list(range(psutil.cpu_count())))
            except Exception as e:
                # 修复：移除了f-string中的表情符号
                logger.warning(f"设置CPU亲和性失败: {e}")
            
            # 增加文件句柄限制
            try:
                import win32file
                win32file._setmaxstdio(2048)
            except ImportError:
                 # 修复：移除了f-string中的表情符号
                logger.warning("pywin32未安装，跳过文件句柄优化")
            except Exception as e:
                 # 修复：移除了f-string中的表情符号
                logger.warning(f"文件句柄优化失败: {e}")
            
            logger.info(f"✅ Windows性能优化完成 - 进程优先级: 高, CPU核心: {psutil.cpu_count()}")
            
        except Exception as e:
            logger.error(f"❌ Windows性能优化失败: {e}")

    async def _optimize_linux(self):
        """优化Linux系统性能"""
        logger.info("正在为Linux平台优化性能...")
        try:
            p = psutil.Process(os.getpid())
            
            # 设置nice值，降低优先级值以获得更高优先级 (-20 to 19)
            try:
                p.nice(-10) 
            except Exception as e:
                 # 修复：移除了f-string中的表情符号
                logger.warning(f"设置进程nice值失败: {e}")

            logger.info(f"✅ Linux性能优化完成。")

        except Exception as e:
            logger.error(f"❌ Linux性能优化失败: {e}")

    def get_system_info(self) -> Dict:
        """获取系统信息"""
        try:
            cpu_freq = psutil.cpu_freq()
            cpu_current = cpu_freq.current if cpu_freq else 0
            
            memory = psutil.virtual_memory()
            memory_total = memory.total / (1024**3)  # GB
            memory_available = memory.available / (1024**3)
            
            disk = psutil.disk_usage('/')
            disk_usage = disk.percent if disk else 0
            
            network_connections = len(psutil.net_connections())
            
            return {
                'cpu_count': psutil.cpu_count(),
                'cpu_freq': cpu_current,
                'memory_total': memory_total,
                'memory_available': memory_available,
                'disk_usage': disk_usage,
                'network_connections': network_connections
            }
        except Exception as e:
            logger.error(f"❌ 获取系统信息失败: {e}")
            return {}
