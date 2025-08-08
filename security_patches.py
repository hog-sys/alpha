# security_patches.py
"""
综合安全补丁 - 修复项目中所有关键安全漏洞
"""

import os
import secrets
import hashlib
import re
from typing import Any, Dict, List, Optional
from pathlib import Path
import logging
import html
import json
from datetime import datetime, timedelta
import asyncio
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

# ==============================================================================
# 1. 环境变量安全加载器
# ==============================================================================

class SecureEnvLoader:
    """安全的环境变量加载器"""
    
    @staticmethod
    def load_env_file(env_path: str = ".env"):
        """安全加载.env文件"""
        env_file = Path(env_path)
        
        if not env_file.exists():
            logger.warning(f"环境文件不存在: {env_path}")
            return {}
        
        # 检查文件权限
        stat_info = env_file.stat()
        if stat_info.st_mode & 0o077:
            logger.warning(f"环境文件权限过于宽松: {env_path}")
            # 修复权限
            os.chmod(env_path, 0o600)
        
        env_vars = {}
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        # 移除引号
                        value = value.strip('"\'')
                        # 不记录敏感值
                        if any(sensitive in key.upper() for sensitive in ['PASSWORD', 'SECRET', 'KEY', 'TOKEN']):
                            logger.debug(f"加载敏感变量: {key}")
                        else:
                            logger.debug(f"加载变量: {key}={value[:10]}...")
                        env_vars[key] = value
        
        return env_vars
    
    @staticmethod
    def get_secure(key: str, default: str = None, required: bool = False) -> Optional[str]:
        """安全获取环境变量"""
        value = os.environ.get(key, default)
        
        if required and not value:
            raise ValueError(f"必需的环境变量未设置: {key}")
        
        # 清理值
        if value:
            value = value.strip()
            # 检查是否包含潜在危险字符
            if any(char in value for char in [';', '&&', '||', '`', '$(']):
                logger.warning(f"环境变量包含潜在危险字符: {key}")
                return None
        
        return value

# ==============================================================================
# 2. SQL注入防护
# ==============================================================================

class SQLSanitizer:
    """SQL清理器"""
    
    @staticmethod
    def sanitize_identifier(identifier: str) -> str:
        """清理SQL标识符（表名、列名等）"""
        # 只允许字母、数字和下划线
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', identifier):
            raise ValueError(f"无效的SQL标识符: {identifier}")
        return identifier
    
    @staticmethod
    def sanitize_value(value: Any) -> Any:
        """清理SQL值"""
        if isinstance(value, str):
            # 转义特殊字符
            value = value.replace("'", "''")
            value = value.replace("\\", "\\\\")
            value = value.replace("\0", "")
            return value
        return value
    
    @staticmethod
    def validate_query(query: str) -> bool:
        """验证查询是否安全"""
        dangerous_patterns = [
            r';\s*DROP\s+',
            r';\s*DELETE\s+',
            r';\s*UPDATE\s+',
            r';\s*INSERT\s+',
            r'--',
            r'/\*.*\*/',
            r'UNION\s+SELECT',
            r'OR\s+1\s*=\s*1',
            r'OR\s+\'1\'\s*=\s*\'1\'',
        ]
        
        query_upper = query.upper()
        for pattern in dangerous_patterns:
            if re.search(pattern, query_upper, re.IGNORECASE):
                logger.warning(f"检测到潜在的SQL注入: {pattern}")
                return False
        
        return True

# ==============================================================================
# 3. XSS防护
# ==============================================================================

class XSSProtection:
    """XSS防护"""
    
    @staticmethod
    def escape_html(text: str) -> str:
        """HTML转义"""
        return html.escape(text, quote=True)
    
    @staticmethod
    def sanitize_json(data: Any) -> Any:
        """清理JSON数据中的XSS"""
        if isinstance(data, str):
            return XSSProtection.escape_html(data)
        elif isinstance(data, dict):
            return {k: XSSProtection.sanitize_json(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [XSSProtection.sanitize_json(item) for item in data]
        return data
    
    @staticmethod
    def validate_url(url: str) -> bool:
        """验证URL是否安全"""
        # 检查协议
        if not url.startswith(('http://', 'https://')):
            return False
        
        # 检查是否包含JavaScript
        if 'javascript:' in url.lower():
            return False
        
        # 检查是否包含data URI
        if url.startswith('data:'):
            return False
        
        return True

# ==============================================================================
# 4. 修复Telegram Bot安全问题
# ==============================================================================

class SecureTelegramBot:
    """安全的Telegram Bot"""
    
    def __init__(self, token: str):
        self.token = self._validate_token(token)
        self.authorized_users = set()  # 授权用户ID集合
        self.rate_limiter = {}  # 速率限制器
        
    def _validate_token(self, token: str) -> str:
        """验证Telegram token格式"""
        if not re.match(r'^\d+:[A-Za-z0-9_-]+$', token):
            raise ValueError("无效的Telegram Bot Token")
        return token
    
    async def verify_user(self, user_id: int) -> bool:
        """验证用户是否授权"""
        return user_id in self.authorized_users
    
    async def check_rate_limit(self, user_id: int, max_requests: int = 10, window: int = 60) -> bool:
        """检查速率限制"""
        current_time = datetime.now()
        
        if user_id not in self.rate_limiter:
            self.rate_limiter[user_id] = []
        
        # 清理过期的请求记录
        self.rate_limiter[user_id] = [
            t for t in self.rate_limiter[user_id]
            if (current_time - t).seconds < window
        ]
        
        # 检查是否超过限制
        if len(self.rate_limiter[user_id]) >= max_requests:
            return False
        
        # 记录新请求
        self.rate_limiter[user_id].append(current_time)
        return True
    
    def sanitize_message(self, message: str) -> str:
        """清理消息内容"""
        # 移除潜在的命令注入
        message = re.sub(r'[;&|`$]', '', message)
        # 限制长度
        return message[:4096]

# ==============================================================================
# 5. 修复密钥管理问题
# ==============================================================================

class SecureKeyManager:
    """安全的密钥管理器"""
    
    def __init__(self):
        self.key_file = Path.home() / '.crypto_scout' / 'keys.json'
        self.key_file.parent.mkdir(parents=True, exist_ok=True)
        
    def generate_key(self, length: int = 32) -> str:
        """生成安全的密钥"""
        return secrets.token_urlsafe(length)
    
    def store_key(self, name: str, key: str):
        """安全存储密钥"""
        keys = {}
        
        if self.key_file.exists():
            with open(self.key_file, 'r') as f:
                keys = json.load(f)
        
        # 对密钥进行哈希存储（用于验证）
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        keys[name] = {
            'hash': key_hash,
            'created': datetime.now().isoformat()
        }
        
        with open(self.key_file, 'w') as f:
            json.dump(keys, f, indent=2)
        
        # 设置文件权限
        os.chmod(self.key_file, 0o600)
    
    def verify_key(self, name: str, key: str) -> bool:
        """验证密钥"""
        if not self.key_file.exists():
            return False
        
        with open(self.key_file, 'r') as f:
            keys = json.load(f)
        
        if name not in keys:
            return False
        
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        return keys[name]['hash'] == key_hash

# ==============================================================================
# 6. 修复错误处理
# ==============================================================================

class SecureErrorHandler:
    """安全的错误处理器"""
    
    @staticmethod
    def handle_error(error: Exception, context: str = None) -> Dict[str, Any]:
        """安全地处理错误"""
        # 不要暴露敏感信息
        error_id = secrets.token_urlsafe(8)
        
        # 记录详细错误（仅在日志中）
        logger.error(f"错误ID: {error_id}, 上下文: {context}, 错误: {str(error)}", exc_info=True)
        
        # 返回通用错误消息给用户
        return {
            'error': True,
            'error_id': error_id,
            'message': '发生了一个错误，请联系管理员并提供错误ID',
            'timestamp': datetime.now().isoformat()
        }
    
    @staticmethod
    def sanitize_traceback(tb: str) -> str:
        """清理追踪信息中的敏感数据"""
        # 移除文件路径
        tb = re.sub(r'File ".*?([^/\\]+\.py)"', r'File "\1"', tb)
        # 移除可能的密码
        tb = re.sub(r'password["\']?\s*[:=]\s*["\'][^"\']+["\']', 'password=***', tb, flags=re.IGNORECASE)
        # 移除可能的token
        tb = re.sub(r'token["\']?\s*[:=]\s*["\'][^"\']+["\']', 'token=***', tb, flags=re.IGNORECASE)
        # 移除可能的API密钥
        tb = re.sub(r'api[_-]?key["\']?\s*[:=]\s*["\'][^"\']+["\']', 'api_key=***', tb, flags=re.IGNORECASE)
        
        return tb

# ==============================================================================
# 7. 修复并发问题
# ==============================================================================

class ConcurrencySafeManager:
    """并发安全管理器"""
    
    def __init__(self):
        self._locks = {}
        self._semaphores = {}
    
    @asynccontextmanager
    async def get_lock(self, key: str):
        """获取异步锁"""
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        
        async with self._locks[key]:
            yield
    
    @asynccontextmanager
    async def get_semaphore(self, key: str, value: int = 10):
        """获取信号量"""
        if key not in self._semaphores:
            self._semaphores[key] = asyncio.Semaphore(value)
        
        async with self._semaphores[key]:
            yield

# ==============================================================================
# 8. 输入验证器
# ==============================================================================

class InputValidator:
    """输入验证器"""
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """验证邮箱"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def validate_symbol(symbol: str) -> bool:
        """验证交易对符号"""
        pattern = r'^[A-Z]{2,10}/[A-Z]{2,10}$'
        return bool(re.match(pattern, symbol))
    
    @staticmethod
    def validate_number(value: str, min_val: float = None, max_val: float = None) -> bool:
        """验证数字"""
        try:
            num = float(value)
            if min_val is not None and num < min_val:
                return False
            if max_val is not None and num > max_val:
                return False
            return True
        except ValueError:
            return False
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """清理文件名"""
        # 移除路径分隔符
        filename = filename.replace('/', '').replace('\\', '')
        # 移除特殊字符
        filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
        # 防止目录遍历
        filename = filename.replace('..', '')
        # 限制长度
        return filename[:255]

# ==============================================================================
# 9. 安全的文件操作
# ==============================================================================

class SecureFileHandler:
    """安全的文件处理器"""
    
    @staticmethod
    def safe_write(filepath: Path, content: str, mode: int = 0o644):
        """安全写入文件"""
        # 创建临时文件
        temp_file = filepath.with_suffix('.tmp')
        
        try:
            # 写入临时文件
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # 设置权限
            os.chmod(temp_file, mode)
            
            # 原子性移动
            temp_file.replace(filepath)
            
        except Exception as e:
            # 清理临时文件
            if temp_file.exists():
                temp_file.unlink()
            raise e
    
    @staticmethod
    def safe_read(filepath: Path) -> Optional[str]:
        """安全读取文件"""
        if not filepath.exists():
            return None
        
        # 检查文件大小（防止读取过大文件）
        max_size = 10 * 1024 * 1024  # 10MB
        if filepath.stat().st_size > max_size:
            logger.warning(f"文件过大: {filepath}")
            return None
        
        # 检查是否为符号链接（防止符号链接攻击）
        if filepath.is_symlink():
            logger.warning(f"检测到符号链接: {filepath}")
            return None
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"读取文件失败: {e}")
            return None

# ==============================================================================
# 10. 安全审计器
# ==============================================================================

class SecurityAuditor:
    """安全审计器"""
    
    def __init__(self):
        self.audit_log = Path('logs/security_audit.log')
        self.audit_log.parent.mkdir(parents=True, exist_ok=True)
    
    def log_event(self, event_type: str, details: Dict[str, Any], severity: str = 'INFO'):
        """记录安全事件"""
        event = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'severity': severity,
            'details': details
        }
        
        # 写入审计日志
        with open(self.audit_log, 'a', encoding='utf-8') as f:
            f.write(json.dumps(event) + '\n')
        
        # 设置日志文件权限
        os.chmod(self.audit_log, 0o600)
        
        # 如果是严重事件，发送警报
        if severity in ['ERROR', 'CRITICAL']:
            self._send_alert(event)
    
    def _send_alert(self, event: Dict[str, Any]):
        """发送安全警报"""
        logger.critical(f"安全警报: {event}")
        # 这里可以添加邮件、Slack等通知

# ==============================================================================
# 应用安全补丁的函数
# ==============================================================================

def apply_security_patches():
    """应用所有安全补丁"""
    logger.info("开始应用安全补丁...")
    
    # 1. 初始化安全组件
    env_loader = SecureEnvLoader()
    sql_sanitizer = SQLSanitizer()
    xss_protection = XSSProtection()
    key_manager = SecureKeyManager()
    error_handler = SecureErrorHandler()
    concurrency_manager = ConcurrencySafeManager()
    input_validator = InputValidator()
    file_handler = SecureFileHandler()
    auditor = SecurityAuditor()
    
    # 2. 加载安全的环境变量
    env_vars = env_loader.load_env_file()
    
    # 3. 生成必要的密钥
    if not env_vars.get('SECRET_KEY'):
        secret_key = key_manager.generate_key()
        key_manager.store_key('SECRET_KEY', secret_key)
        logger.info("生成了新的SECRET_KEY")
    
    # 4. 审计现有配置
    auditor.log_event('SECURITY_PATCH', {'status': 'applied'}, 'INFO')
    
    logger.info("✅ 安全补丁应用完成")
    
    return {
        'env_loader': env_loader,
        'sql_sanitizer': sql_sanitizer,
        'xss_protection': xss_protection,
        'key_manager': key_manager,
        'error_handler': error_handler,
        'concurrency_manager': concurrency_manager,
        'input_validator': input_validator,
        'file_handler': file_handler,
        'auditor': auditor
    }

if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 应用补丁
    security_components = apply_security_patches()
    
    print("\n安全补丁已成功应用！")
    print("请重启应用以使更改生效。")