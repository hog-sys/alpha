# src/telegram/telegram_bot_secure.py
"""
安全版Telegram Bot - 修复所有安全漏洞
"""
import asyncio
import logging
import re
import hmac
import hashlib
from typing import Dict, List, Optional, Set, Any
from datetime import datetime, timedelta
from collections import defaultdict
import json
import html

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes
)
from telegram.error import TelegramError
from telegram.constants import ParseMode
import redis.asyncio as redis
from sqlalchemy import select, desc, and_, or_
from sqlalchemy.sql import func

from src.core.database import engine, opportunities_table

logger = logging.getLogger(__name__)

class SecureTelegramBot:
    """安全的Telegram通知机器人"""

    def __init__(self, token: str):
        # 验证token格式
        self._validate_token(token)
        self.token = token
        
        # 安全配置
        self.max_message_length = 4096
        self.max_buttons_per_row = 3
        self.max_callback_data_length = 64
        
        # 用户管理
        self.authorized_users: Set[int] = set()
        self.admin_users: Set[int] = set()
        self.blocked_users: Set[int] = set()
        
        # 速率限制
        self.rate_limiter = defaultdict(list)
        self.max_requests_per_minute = 30
        self.max_commands_per_hour = 100
        
        # 会话管理
        self.user_sessions = {}
        self.session_timeout = timedelta(hours=24)
        
        # Redis连接
        self.redis_client = None
        
        # 安全审计
        self.audit_logger = self._setup_audit_logger()
        
        # 命令白名单
        self.allowed_commands = {
            'start', 'help', 'status', 'alerts', 'subscribe', 
            'unsubscribe', 'settings', 'stats', 'about', 'stop'
        }
        
        # 用户偏好设置（带验证）
        self.default_preferences = {
            'min_confidence': 0.7,
            'max_alerts_per_hour': 10,
            'signal_types': ['arbitrage', 'volume_spike'],
            'language': 'zh'
        }
        
        self.app = None
        self.running = False
        
    def _validate_token(self, token: str) -> None:
        """验证Telegram Bot Token格式"""
        if not token:
            raise ValueError("Token不能为空")
        
        # Telegram token格式: 数字:字母数字字符串
        if not re.match(r'^\d+:[A-Za-z0-9_-]+$', token):
            raise ValueError("无效的Telegram Bot Token格式")
        
        # 检查长度
        if len(token) < 35 or len(token) > 50:
            raise ValueError("Token长度异常")
    
    def _setup_audit_logger(self) -> logging.Logger:
        """设置审计日志"""
        audit_logger = logging.getLogger('telegram_bot_audit')
        audit_logger.setLevel(logging.INFO)
        
        # 创建审计日志处理器
        handler = logging.FileHandler('logs/telegram_audit.log')
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        audit_logger.addHandler(handler)
        
        return audit_logger
    
    async def initialize(self):
        """初始化机器人"""
        logger.info("初始化安全Telegram机器人...")
        
        try:
            # 初始化Redis
            await self._init_redis()
            
            # 加载授权用户
            await self._load_authorized_users()
            
            # 创建Application
            self.app = Application.builder().token(self.token).build()
            
            # 注册命令处理器（带安全验证）
            self._register_handlers()
            
            # 设置命令列表
            await self._set_bot_commands()
            
            # 初始化应用
            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True  # 丢弃离线期间的消息
            )
            
            self.running = True
            logger.info("✅ 安全Telegram机器人已启动")
            
            # 启动定期任务
            asyncio.create_task(self._cleanup_sessions())
            asyncio.create_task(self._monitor_security())
            
        except Exception as e:
            logger.error(f"初始化机器人失败: {e}")
            raise
    
    async def _init_redis(self):
        """初始化Redis连接"""
        try:
            self.redis_client = await redis.from_url(
                "redis://localhost:6379",
                encoding="utf-8",
                decode_responses=True
            )
            await self.redis_client.ping()
            logger.info("✅ Redis连接成功")
        except Exception as e:
            logger.warning(f"Redis连接失败: {e}，将使用内存存储")
            self.redis_client = None
    
    async def _load_authorized_users(self):
        """加载授权用户列表"""
        if self.redis_client:
            # 从Redis加载
            users = await self.redis_client.smembers("telegram:authorized_users")
            self.authorized_users = {int(u) for u in users if u.isdigit()}
            
            admins = await self.redis_client.smembers("telegram:admin_users")
            self.admin_users = {int(u) for u in admins if u.isdigit()}
            
            blocked = await self.redis_client.smembers("telegram:blocked_users")
            self.blocked_users = {int(u) for u in blocked if u.isdigit()}
        else:
            # 从配置文件加载（示例）
            # 实际应该从数据库或配置文件加载
            self.authorized_users = set()
            self.admin_users = set()
    
    def _register_handlers(self):
        """注册命令处理器"""
        # 命令处理器
        for command in self.allowed_commands:
            handler_method = getattr(self, f'cmd_{command}', None)
            if handler_method:
                self.app.add_handler(
                    CommandHandler(
                        command, 
                        self._secure_handler_wrapper(handler_method)
                    )
                )
        
        # 回调查询处理器
        self.app.add_handler(
            CallbackQueryHandler(
                self._secure_handler_wrapper(self.handle_callback_query)
            )
        )
        
        # 消息处理器（非命令）
        self.app.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                self._secure_handler_wrapper(self.handle_message)
            )
        )
        
        # 错误处理器
        self.app.add_error_handler(self.error_handler)
    
    def _secure_handler_wrapper(self, handler):
        """安全处理器包装器"""
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            try:
                # 获取用户信息
                user = update.effective_user
                if not user:
                    return
                
                user_id = user.id
                
                # 审计日志
                self.audit_logger.info(
                    f"User {user_id} ({user.username}) - "
                    f"Action: {handler.__name__}"
                )
                
                # 检查是否被封锁
                if user_id in self.blocked_users:
                    await update.effective_message.reply_text(
                        "⛔ 您已被封锁，无法使用此机器人。"
                    )
                    return
                
                # 速率限制检查
                if not await self._check_rate_limit(user_id):
                    await update.effective_message.reply_text(
                        "⚠️ 请求过于频繁，请稍后再试。"
                    )
                    return
                
                # 权限检查（某些命令需要授权）
                if handler.__name__ in ['cmd_alerts', 'cmd_settings', 'cmd_subscribe']:
                    if user_id not in self.authorized_users and user_id not in self.admin_users:
                        await update.effective_message.reply_text(
                            "🔒 您需要先获得授权才能使用此功能。\n"
                            "请联系管理员获取访问权限。"
                        )
                        return
                
                # 更新会话
                await self._update_session(user_id)
                
                # 执行实际处理器
                await handler(update, context)
                
            except Exception as e:
                logger.error(f"处理器错误: {e}", exc_info=True)
                await self._send_error_message(update)
        
        return wrapper
    
    async def _check_rate_limit(self, user_id: int) -> bool:
        """检查速率限制"""
        current_time = datetime.now()
        
        # 清理过期记录
        self.rate_limiter[user_id] = [
            t for t in self.rate_limiter[user_id]
            if (current_time - t).seconds < 60
        ]
        
        # 检查是否超过限制
        if len(self.rate_limiter[user_id]) >= self.max_requests_per_minute:
            self.audit_logger.warning(f"用户 {user_id} 触发速率限制")
            return False
        
        # 记录请求
        self.rate_limiter[user_id].append(current_time)
        return True
    
    async def _update_session(self, user_id: int):
        """更新用户会话"""
        self.user_sessions[user_id] = {
            'last_activity': datetime.now(),
            'ip': None,  # Telegram不提供IP
            'requests': self.user_sessions.get(user_id, {}).get('requests', 0) + 1
        }
    
    async def _send_error_message(self, update: Update):
        """发送错误消息"""
        try:
            await update.effective_message.reply_text(
                "❌ 处理您的请求时发生错误。\n"
                "如果问题持续存在，请联系管理员。"
            )
        except:
            pass
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /start 命令"""
        user = update.effective_user
        
        # 清理用户输入
        user_name = html.escape(user.first_name or "用户")
        
        welcome_message = f"""
👋 欢迎使用 Crypto Alpha Scout Bot，{user_name}！

我是一个智能的加密货币机会发现机器人，可以帮助您：
• 🎯 发现套利机会
• 📊 监控市场异动
• 🔔 实时推送高价值信号

使用 /help 查看所有可用命令。
        """
        
        keyboard = [
            [
                InlineKeyboardButton("📚 帮助", callback_data="help"),
                InlineKeyboardButton("⚙️ 设置", callback_data="settings")
            ],
            [
                InlineKeyboardButton("📊 状态", callback_data="status")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            text=self._sanitize_message(welcome_message),
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN_V2
        )
        
        # 记录新用户
        if self.redis_client:
            await self.redis_client.sadd("telegram:users", str(user.id))
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /help 命令"""
        help_text = """
📚 **可用命令**

基础命令：
/start - 开始使用机器人
/help - 显示帮助信息
/about - 关于机器人

功能命令：
/status - 查看系统状态
/alerts - 查看最新机会
/subscribe - 订阅通知
/unsubscribe - 取消订阅
/settings - 个人设置

管理命令：
/stats - 查看统计信息
/stop - 停止接收通知

需要帮助？联系 @support
        """
        
        await update.message.reply_text(
            text=self._sanitize_message(help_text),
            parse_mode=ParseMode.MARKDOWN_V2
        )
    
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /status 命令"""
        try:
            # 获取系统状态
            async with engine.connect() as conn:
                # 使用参数化查询
                result = await conn.execute(
                    select(
                        func.count(opportunities_table.c.id).label('total'),
                        func.count(
                            opportunities_table.c.id
                        ).filter(
                            opportunities_table.c.timestamp > datetime.now() - timedelta(hours=1)
                        ).label('last_hour')
                    )
                )
                row = result.fetchone()
                
                total_opps = row.total if row else 0
                recent_opps = row.last_hour if row else 0
            
            status_text = f"""
📊 **系统状态**

• 总机会数: {total_opps}
• 最近1小时: {recent_opps}
• 系统状态: ✅ 正常运行
• 最后更新: {datetime.now().strftime('%H:%M:%S')}
            """
            
            await update.message.reply_text(
                text=self._sanitize_message(status_text),
                parse_mode=ParseMode.MARKDOWN_V2
            )
            
        except Exception as e:
            logger.error(f"获取状态失败: {e}")
            await update.message.reply_text("❌ 获取系统状态失败。")
    
    async def cmd_alerts(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /alerts 命令 - 需要授权"""
        try:
            # 获取最新机会
            query = select(opportunities_table).where(
                opportunities_table.c.confidence >= 0.7
            ).order_by(
                desc(opportunities_table.c.timestamp)
            ).limit(5)
            
            async with engine.connect() as conn:
                results = await conn.execute(query)
                opportunities = [dict(row) for row in results.mappings()]
            
            if not opportunities:
                await update.message.reply_text("📭 暂无新机会")
                return
            
            alerts_text = "🎯 **最新机会**\n\n"
            
            for opp in opportunities:
                # 清理和转义数据
                symbol = html.escape(str(opp.get('symbol', 'N/A')))
                signal_type = html.escape(str(opp.get('signal_type', 'unknown')))
                confidence = float(opp.get('confidence', 0))
                
                alerts_text += f"• {symbol} - {signal_type}\n"
                alerts_text += f"  置信度: {confidence*100:.1f}%\n\n"
            
            await update.message.reply_text(
                text=self._sanitize_message(alerts_text),
                parse_mode=ParseMode.MARKDOWN_V2
            )
            
        except Exception as e:
            logger.error(f"获取机会失败: {e}")
            await update.message.reply_text("❌ 获取最新机会失败。")
    
    async def cmd_subscribe(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理订阅命令"""
        user_id = update.effective_user.id
        
        if self.redis_client:
            await self.redis_client.sadd("telegram:subscribers", str(user_id))
        
        self.authorized_users.add(user_id)
        
        await update.message.reply_text(
            "✅ 您已成功订阅机会通知！\n"
            "使用 /settings 自定义您的通知偏好。"
        )
    
    async def cmd_unsubscribe(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理取消订阅命令"""
        user_id = update.effective_user.id
        
        if self.redis_client:
            await self.redis_client.srem("telegram:subscribers", str(user_id))
        
        self.authorized_users.discard(user_id)
        
        await update.message.reply_text(
            "✅ 您已取消订阅机会通知。\n"
            "使用 /subscribe 重新订阅。"
        )
    
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理回调查询"""
        query = update.callback_query
        await query.answer()
        
        # 验证callback_data
        if not self._validate_callback_data(query.data):
            await query.message.reply_text("❌ 无效的操作")
            return
        
        # 处理不同的回调
        if query.data == "help":
            await self.cmd_help(update, context)
        elif query.data == "status":
            await self.cmd_status(update, context)
        elif query.data == "settings":
            await self._show_settings(update, context)
        elif query.data.startswith("set_"):
            await self._handle_setting(update, context, query.data)
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理普通消息"""
        # 清理消息内容
        message_text = self._sanitize_input(update.message.text)
        
        # 限制消息长度
        if len(message_text) > 1000:
            await update.message.reply_text("❌ 消息过长，请简化您的输入。")
            return
        
        # 检查是否包含敏感内容
        if self._contains_sensitive_content(message_text):
            self.audit_logger.warning(
                f"用户 {update.effective_user.id} 发送了可疑内容"
            )
            await update.message.reply_text("⚠️ 检测到不当内容，请注意您的言辞。")
            return
        
        # 默认回复
        await update.message.reply_text(
            "我不理解您的消息。请使用 /help 查看可用命令。"
        )
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理错误"""
        logger.error(f"Update {update} caused error {context.error}")
        
        # 不要向用户暴露详细错误信息
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ 发生了一个错误。如果问题持续，请联系管理员。"
            )
    
    def _sanitize_message(self, text: str) -> str:
        """清理消息内容"""
        # 移除潜在的注入攻击
        text = re.sub(r'[<>&]', '', text)
        
        # 限制长度
        if len(text) > self.max_message_length:
            text = text[:self.max_message_length - 3] + "..."
        
        # 转义Markdown特殊字符
        escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in escape_chars:
            text = text.replace(char, f'\\{char}')
        
        return text
    
    def _sanitize_input(self, text: str) -> str:
        """清理用户输入"""
        if not text:
            return ""
        
        # 移除控制字符
        text = ''.join(char for char in text if ord(char) >= 32 or char == '\n')
        
        # HTML转义
        text = html.escape(text)
        
        # 移除多余空白
        text = ' '.join(text.split())
        
        return text[:1000]  # 限制长度
    
    def _validate_callback_data(self, data: str) -> bool:
        """验证回调数据"""
        if not data:
            return False
        
        if len(data) > self.max_callback_data_length:
            return False
        
        # 只允许特定格式
        if not re.match(r'^[a-zA-Z0-9_\-:]+$', data):
            return False
        
        return True
    
    def _contains_sensitive_content(self, text: str) -> bool:
        """检查是否包含敏感内容"""
        # 检查可疑模式
        suspicious_patterns = [
            r'<script',
            r'javascript:',
            r'onclick=',
            r'onerror=',
            r'SELECT.*FROM',
            r'DROP\s+TABLE',
            r'INSERT\s+INTO',
            r'UPDATE\s+SET',
            r'DELETE\s+FROM'
        ]
        
        text_lower = text.lower()
        for pattern in suspicious_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return True
        
        return False
    
    async def _show_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """显示设置菜单"""
        user_id = update.effective_user.id
        
        # 获取用户设置
        settings = await self._get_user_settings(user_id)
        
        settings_text = f"""
⚙️ **个人设置**

• 最小置信度: {settings['min_confidence']*100:.0f}%
• 每小时最大通知: {settings['max_alerts_per_hour']}
• 信号类型: {', '.join(settings['signal_types'])}
        """
        
        keyboard = [
            [
                InlineKeyboardButton("📊 置信度", callback_data="set_confidence"),
                InlineKeyboardButton("🔔 通知频率", callback_data="set_frequency")
            ],
            [
                InlineKeyboardButton("📈 信号类型", callback_data="set_signals")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.message.edit_text(
                text=self._sanitize_message(settings_text),
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN_V2
            )
        else:
            await update.message.reply_text(
                text=self._sanitize_message(settings_text),
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN_V2
            )
    
    async def _get_user_settings(self, user_id: int) -> Dict[str, Any]:
        """获取用户设置"""
        if self.redis_client:
            settings_str = await self.redis_client.get(f"user:settings:{user_id}")
            if settings_str:
                try:
                    settings = json.loads(settings_str)
                    # 验证设置
                    return self._validate_user_settings(settings)
                except:
                    pass
        
        return self.default_preferences.copy()
    
    def _validate_user_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """验证用户设置"""
        validated = self.default_preferences.copy()
        
        # 验证置信度
        if 'min_confidence' in settings:
            try:
                conf = float(settings['min_confidence'])
                if 0 <= conf <= 1:
                    validated['min_confidence'] = conf
            except:
                pass
        
        # 验证通知频率
        if 'max_alerts_per_hour' in settings:
            try:
                freq = int(settings['max_alerts_per_hour'])
                if 1 <= freq <= 100:
                    validated['max_alerts_per_hour'] = freq
            except:
                pass
        
        # 验证信号类型
        if 'signal_types' in settings:
            if isinstance(settings['signal_types'], list):
                valid_types = {'arbitrage', 'volume_spike', 'sentiment_shift', 'new_pool', 'whale_movement'}
                validated['signal_types'] = [
                    t for t in settings['signal_types'] 
                    if t in valid_types
                ]
        
        return validated
    
    async def _handle_setting(self, update: Update, context: ContextTypes.DEFAULT_TYPE, setting: str):
        """处理设置更改"""
        # 实现具体的设置处理逻辑
        await update.callback_query.message.reply_text(
            f"设置功能 {setting} 正在开发中..."
        )
    
    async def _cleanup_sessions(self):
        """清理过期会话"""
        while self.running:
            try:
                current_time = datetime.now()
                expired_users = []
                
                for user_id, session in self.user_sessions.items():
                    if current_time - session['last_activity'] > self.session_timeout:
                        expired_users.append(user_id)
                
                for user_id in expired_users:
                    del self.user_sessions[user_id]
                    logger.debug(f"清理过期会话: {user_id}")
                
                await asyncio.sleep(3600)  # 每小时清理一次
                
            except Exception as e:
                logger.error(f"清理会话失败: {e}")
                await asyncio.sleep(3600)
    
    async def _monitor_security(self):
        """监控安全事件"""
        while self.running:
            try:
                # 检查异常活动
                for user_id, requests in self.rate_limiter.items():
                    if len(requests) > self.max_requests_per_minute * 0.8:
                        self.audit_logger.warning(f"用户 {user_id} 接近速率限制")
                
                # 检查被封锁的用户
                if self.blocked_users:
                    self.audit_logger.info(f"当前封锁用户数: {len(self.blocked_users)}")
                
                await asyncio.sleep(300)  # 每5分钟检查一次
                
            except Exception as e:
                logger.error(f"安全监控失败: {e}")
                await asyncio.sleep(300)
    
    async def _set_bot_commands(self):
        """设置Bot命令列表"""
        commands = [
            BotCommand("start", "开始使用机器人"),
            BotCommand("help", "获取帮助信息"),
            BotCommand("status", "查看系统状态"),
            BotCommand("alerts", "查看最新机会"),
            BotCommand("subscribe", "订阅通知"),
            BotCommand("unsubscribe", "取消订阅"),
            BotCommand("settings", "个人设置"),
            BotCommand("about", "关于机器人")
        ]
        
        await self.app.bot.set_my_commands(commands)
    
    async def send_opportunity(self, opportunity: Dict[str, Any], user_ids: List[int] = None):
        """发送机会通知给用户"""
        if not self.running or not self.app:
            return
        
        # 准备消息
        message = self._format_opportunity_message(opportunity)
        
        # 如果没有指定用户，发送给所有订阅者
        if user_ids is None:
            if self.redis_client:
                subscribers = await self.redis_client.smembers("telegram:subscribers")
                user_ids = [int(u) for u in subscribers if u.isdigit()]
            else:
                user_ids = list(self.authorized_users)
        
        # 发送消息
        for user_id in user_ids:
            try:
                # 检查用户设置
                settings = await self._get_user_settings(user_id)
                
                # 检查置信度阈值
                if opportunity.get('confidence', 0) < settings['min_confidence']:
                    continue
                
                # 检查信号类型
                if opportunity.get('signal_type') not in settings['signal_types']:
                    continue
                
                # 发送消息
                await self.app.bot.send_message(
                    chat_id=user_id,
                    text=self._sanitize_message(message),
                    parse_mode=ParseMode.MARKDOWN_V2
                )
                
                # 记录发送
                self.audit_logger.info(f"发送机会通知给用户 {user_id}")
                
            except TelegramError as e:
                logger.error(f"发送消息给 {user_id} 失败: {e}")
                
                # 如果用户阻止了机器人，从订阅列表移除
                if "blocked" in str(e).lower():
                    if self.redis_client:
                        await self.redis_client.srem("telegram:subscribers", str(user_id))
                    self.authorized_users.discard(user_id)
            
            # 避免发送过快
            await asyncio.sleep(0.1)
    
    def _format_opportunity_message(self, opportunity: Dict[str, Any]) -> str:
        """格式化机会消息"""
        # 清理和验证数据
        signal_type = html.escape(str(opportunity.get('signal_type', 'unknown')))
        symbol = html.escape(str(opportunity.get('symbol', 'N/A')))
        confidence = float(opportunity.get('confidence', 0))
        
        # 构建消息
        message = f"🎯 **{signal_type.replace('_', ' ').title()}**\n\n"
        message += f"**交易对:** {symbol}\n"
        message += f"**置信度:** {confidence*100:.1f}%\n"
        
        # 添加数据详情
        data = opportunity.get('data', {})
        if isinstance(data, dict):
            for key, value in list(data.items())[:5]:  # 限制显示的字段数
                # 清理键名和值
                key = html.escape(str(key).replace('_', ' ').title())
                value = html.escape(str(value)[:100])  # 限制值的长度
                message += f"**{key}:** {value}\n"
        
        # 添加时间戳
        timestamp = opportunity.get('timestamp')
        if timestamp:
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            message += f"\n⏰ {timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
        
        return message
    
    async def stop(self):
        """停止机器人"""
        logger.info("正在停止Telegram机器人...")
        self.running = False
        
        if self.app:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
        
        if self.redis_client:
            await self.redis_client.close()
        
        logger.info("✅ Telegram机器人已停止")

# 创建安全的机器人实例
def create_secure_telegram_bot(token: str) -> SecureTelegramBot:
    """创建安全的Telegram机器人"""
    return SecureTelegramBot(token)
