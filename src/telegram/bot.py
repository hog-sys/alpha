# src/telegram/bot.py

import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
import json

# 新增数据库相关导入
from sqlalchemy import select, desc, text
from src.core.database import engine, opportunities_table

logger = logging.getLogger(__name__)

class TelegramBot:
    """Telegram通知机器人，数据源为数据库"""

    def __init__(self, token: str):
        self.token = token
        # 移除 scout_manager 和 redis_client
        self.app = None
        self.subscribers = set()
        self.user_preferences = {}
        self.last_checked_timestamp = datetime.now() # 用于轮询新机会

        self.default_preferences = {
            'min_confidence': 0.7,
            'notification_interval': 60,
        }

    async def initialize(self):
        """初始化机器人并开始监听"""
        logger.info("初始化Telegram机器人...")
        # (此处可以添加从数据库加载订阅者的逻辑)

        self.app = Application.builder().token(self.token).build()

        # 注册命令处理器 (保持不变)
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("help", self.cmd_help))
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("alerts", self.cmd_alerts))
        # ... 其他命令处理器

        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()

        # 新增：启动一个后台任务来轮询和发送通知
        asyncio.create_task(self._poll_and_notify())

        logger.info("✅ Telegram机器人已启动并开始监听数据库")

    async def _poll_and_notify(self):
        """定期轮询数据库，检查是否有新机会需要通知"""
        while True:
            try:
                # 查询自上次检查以来，符合高置信度的新机会
                query = (
                    select(opportunities_table)
                    .where(opportunities_table.c.timestamp > self.last_checked_timestamp)
                    .where(opportunities_table.c.confidence >= 0.75) # 硬编码一个高置信度阈值
                    .order_by(desc(opportunities_table.c.timestamp))
                    .limit(10) # 每次最多处理10个
                )
                
                async with engine.connect() as conn:
                    results = await conn.execute(query)
                    new_opportunities = results.mappings().all()

                if new_opportunities:
                    # 更新最后检查的时间戳
                    self.last_checked_timestamp = new_opportunities[0]['timestamp']
                    
                    for opp in reversed(new_opportunities): # 按时间顺序发送
                        await self.send_opportunity(dict(opp))

                # 等待下一个轮询周期
                await asyncio.sleep(30) # 每30秒检查一次

            except Exception as e:
                logger.error(f"轮询通知任务失败: {e}", exc_info=True)
                await asyncio.sleep(60) # 出错后等待更长时间

    async def cmd_status(self, update: Update, context):
        """处理 /status 命令，从数据库获取状态"""
        try:
            async with engine.connect() as conn:
                # 查询机会总数
                total_opps_query = text("SELECT COUNT(id) FROM opportunities;")
                total_opps = await conn.scalar(total_opps_query)

                # 查询最近一小时的机会数
                one_hour_ago = datetime.now() - timedelta(hours=1)
                opps_last_hour_query = select(opportunities_table).where(opportunities_table.c.timestamp > one_hour_ago)
                opps_last_hour_result = await conn.execute(opps_last_hour_query)
                opps_last_hour = len(opps_last_hour_result.fetchall())

            status_text = f"""
📊 **系统状态 (数据源: 数据库)**

- 机会总数: {total_opps}
- 最近一小时机会: {opps_last_hour}
- 数据库连接: {'✅ 正常' if engine else '❌ 异常'}

_更新时间: {datetime.now().strftime('%H:%M:%S')}_
            """
            await update.message.reply_text(status_text, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"获取状态失败: {e}")
            await update.message.reply_text("❌ 获取系统状态失败。")

    async def cmd_alerts(self, update: Update, context):
        """处理 /alerts 命令，从数据库获取最新机会"""
        try:
            query = select(opportunities_table).order_by(desc(opportunities_table.c.timestamp)).limit(5)
            async with engine.connect() as conn:
                results = await conn.execute(query)
                opportunities = [dict(row) for row in results.mappings().all()]

            if not opportunities:
                await update.message.reply_text("📭 暂无新机会")
                return

            alerts_text = "🎯 **最新机会 (来自数据库)**\n\n"
            for i, opp in enumerate(opportunities, 1):
                alerts_text += self._format_opportunity_brief(opp, i)
                alerts_text += "\n"

            await update.message.reply_text(alerts_text, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"获取最新机会失败: {e}")
            await update.message.reply_text("❌ 获取最新机会失败。")

    async def send_opportunity(self, opportunity: Dict):
        """发送机会通知 (此方法现在由内部轮询任务调用)"""
        message = self._format_opportunity_message(opportunity)
        keyboard = self._create_opportunity_keyboard(opportunity)
        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

        # 简化：发送给所有订阅者，实际应用中会检查用户偏好
        for chat_id in self.subscribers:
            try:
                await self.app.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
            except Exception as e:
                logger.error(f"发送消息到 {chat_id} 失败: {e}")

    # _format_opportunity_message, _create_opportunity_keyboard 等辅助方法保持不变...
    # ...

    async def stop(self):
        """停止机器人"""
        if self.app:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
        logger.info("Telegram机器人已停止")

    # (此处省略部分未修改的辅助方法，如 _format_opportunity_message 等)
    def _format_opportunity_message(self, opportunity: Dict) -> str:
        # (此方法保持不变)
        signal_type = opportunity.get('signal_type', 'unknown')
        symbol = opportunity.get('symbol', 'N/A')
        confidence = opportunity.get('confidence', 0)
        message = f"🎯 **{signal_type.replace('_', ' ').title()}**\n\n"
        message += f"**交易对:** `{symbol}`\n"
        message += f"**置信度:** {confidence*100:.1f}%\n"
        # ... 更多格式化逻辑
        return message
    
    def _create_opportunity_keyboard(self, opportunity: Dict) -> List[List[InlineKeyboardButton]]:
        # (此方法保持不变)
        return [[InlineKeyboardButton("📊 详情", callback_data=f"detail_{opportunity.get('id', '')[:8]}")]]

    def _format_opportunity_brief(self, opp: Dict, index: int) -> str:
        # (此方法保持不变)
        signal_type = opp.get('signal_type', 'unknown')
        symbol = opp.get('symbol', 'N/A')
        confidence = opp.get('confidence', 0)
        return f"{index}. 🎯 **{symbol}** - {signal_type.replace('_', ' ')} ({confidence*100:.0f}%)\n"

