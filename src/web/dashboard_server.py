# src/web/dashboard_server_secure.py
"""
安全版本的Web仪表盘服务器 - 添加认证、授权和安全措施
"""
import asyncio
import logging
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pathlib import Path
import json
from datetime import datetime, timedelta
import secrets
import hashlib
import hmac
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, validator
import html
from sqlalchemy import select, desc, text, and_
from sqlalchemy.sql import func
from src.core.database import engine, opportunities_table
import redis.asyncio as redis
from contextlib import asynccontextmanager
import ipaddress
import time
from collections import defaultdict

logger = logging.getLogger(__name__)

# ==============================================================================
# 安全配置
# ==============================================================================

class SecurityConfig:
    """安全配置"""
    SECRET_KEY = secrets.token_urlsafe(32)  # 应该从环境变量加载
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30
    REFRESH_TOKEN_EXPIRE_DAYS = 7
    
    # 速率限制
    RATE_LIMIT_REQUESTS = 100
    RATE_LIMIT_WINDOW = 60  # 秒
    
    # CORS配置
    ALLOWED_ORIGINS = ["http://localhost:3000", "http://localhost:8000"]
    
    # 可信主机
    ALLOWED_HOSTS = ["localhost", "127.0.0.1", "crypto-scout.local"]

security_config = SecurityConfig()

# ==============================================================================
# 认证系统
# ==============================================================================

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

class UserModel(BaseModel):
    """用户模型"""
    username: str
    email: str
    is_active: bool = True
    is_admin: bool = False
    
    @validator('username')
    def validate_username(cls, v):
        if not v or len(v) < 3:
            raise ValueError('用户名至少3个字符')
        if not v.isalnum():
            raise ValueError('用户名只能包含字母和数字')
        return v
    
    @validator('email')
    def validate_email(cls, v):
        if '@' not in v:
            raise ValueError('无效的邮箱地址')
        return v

class TokenData(BaseModel):
    """令牌数据"""
    username: Optional[str] = None
    scopes: List[str] = []

class AuthManager:
    """认证管理器"""
    
    def __init__(self):
        self.redis_client = None
        self.failed_attempts = defaultdict(int)
        self.blocked_ips = set()
    
    async def init_redis(self):
        """初始化Redis连接"""
        self.redis_client = await redis.from_url(
            "redis://localhost:6379",
            encoding="utf-8",
            decode_responses=True
        )
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """验证密码"""
        return pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """获取密码哈希"""
        return pwd_context.hash(password)
    
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None):
        """创建访问令牌"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=15)
        
        to_encode.update({"exp": expire, "type": "access"})
        encoded_jwt = jwt.encode(to_encode, security_config.SECRET_KEY, algorithm=security_config.ALGORITHM)
        return encoded_jwt
    
    def create_refresh_token(self, data: dict):
        """创建刷新令牌"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=security_config.REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire, "type": "refresh"})
        encoded_jwt = jwt.encode(to_encode, security_config.SECRET_KEY, algorithm=security_config.ALGORITHM)
        return encoded_jwt
    
    async def get_current_user(self, credentials: HTTPAuthorizationCredentials = Depends(security)):
        """获取当前用户"""
        token = credentials.credentials
        
        try:
            payload = jwt.decode(token, security_config.SECRET_KEY, algorithms=[security_config.ALGORITHM])
            username: str = payload.get("sub")
            token_type: str = payload.get("type")
            
            if username is None or token_type != "access":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="无效的认证凭据",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            # 检查令牌是否被撤销
            if self.redis_client:
                is_revoked = await self.redis_client.get(f"revoked_token:{token}")
                if is_revoked:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="令牌已被撤销"
                    )
            
            return TokenData(username=username)
            
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的认证凭据",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    async def revoke_token(self, token: str):
        """撤销令牌"""
        if self.redis_client:
            # 存储被撤销的令牌，设置过期时间
            await self.redis_client.setex(
                f"revoked_token:{token}",
                security_config.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                "1"
            )
    
    def check_rate_limit(self, client_ip: str) -> bool:
        """检查速率限制"""
        if client_ip in self.blocked_ips:
            return False
        
        current_time = time.time()
        # 这里应该使用Redis实现分布式速率限制
        # 简化版本
        return True
    
    def record_failed_attempt(self, client_ip: str):
        """记录失败的尝试"""
        self.failed_attempts[client_ip] += 1
        if self.failed_attempts[client_ip] > 5:
            self.blocked_ips.add(client_ip)
            logger.warning(f"IP {client_ip} 被封锁due to多次失败尝试")

auth_manager = AuthManager()

# ==============================================================================
# 输入验证
# ==============================================================================

class OpportunityFilter(BaseModel):
    """机会过滤器"""
    min_confidence: float = 0.0
    max_confidence: float = 1.0
    signal_types: Optional[List[str]] = None
    limit: int = 20
    
    @validator('min_confidence', 'max_confidence')
    def validate_confidence(cls, v):
        if not 0 <= v <= 1:
            raise ValueError('置信度必须在0到1之间')
        return v
    
    @validator('limit')
    def validate_limit(cls, v):
        if not 1 <= v <= 100:
            raise ValueError('限制必须在1到100之间')
        return v

# ==============================================================================
# 安全的仪表盘服务器
# ==============================================================================

class SecureDashboardServer:
    """安全的Web控制台服务器"""

    def __init__(self, config):
        self.config = config
        self.app = FastAPI(
            title="Crypto Alpha Scout Dashboard",
            docs_url=None,  # 在生产环境禁用文档
            redoc_url=None
        )
        self.active_connections: Dict[str, WebSocket] = {}
        self._setup_middleware()
        self._register_routes()
        
    def _setup_middleware(self):
        """设置中间件"""
        # CORS中间件
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=security_config.ALLOWED_ORIGINS,
            allow_credentials=True,
            allow_methods=["GET", "POST"],
            allow_headers=["*"],
            max_age=3600,
        )
        
        # 可信主机中间件
        self.app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=security_config.ALLOWED_HOSTS
        )
        
        # Gzip压缩
        self.app.add_middleware(GZipMiddleware, minimum_size=1000)
        
        # 自定义安全头中间件
        @self.app.middleware("http")
        async def add_security_headers(request, call_next):
            response = await call_next(request)
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline';"
            return response
        
        # 速率限制中间件
        @self.app.middleware("http")
        async def rate_limit_middleware(request, call_next):
            client_ip = request.client.host
            
            if not auth_manager.check_rate_limit(client_ip):
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "请求过于频繁"}
                )
            
            response = await call_next(request)
            return response

    def _register_routes(self):
        """注册API路由"""
        
        @self.app.on_event("startup")
        async def startup_event():
            await auth_manager.init_redis()
        
        @self.app.post("/api/auth/login")
        async def login(username: str, password: str, request):
            """用户登录"""
            client_ip = request.client.host
            
            # 验证用户（这里应该查询数据库）
            # 示例硬编码，实际应查询数据库
            if username != "admin" or password != "secure_password":
                auth_manager.record_failed_attempt(client_ip)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="用户名或密码错误"
                )
            
            # 创建令牌
            access_token = auth_manager.create_access_token(
                data={"sub": username},
                expires_delta=timedelta(minutes=security_config.ACCESS_TOKEN_EXPIRE_MINUTES)
            )
            refresh_token = auth_manager.create_refresh_token(
                data={"sub": username}
            )
            
            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer"
            }
        
        @self.app.post("/api/auth/logout")
        async def logout(token: str, current_user: TokenData = Depends(auth_manager.get_current_user)):
            """用户登出"""
            await auth_manager.revoke_token(token)
            return {"message": "登出成功"}
        
        @self.app.get("/api/status")
        async def get_status(current_user: TokenData = Depends(auth_manager.get_current_user)):
            """获取系统状态 - 需要认证"""
            try:
                async with engine.connect() as conn:
                    # 使用参数化查询防止SQL注入
                    total_opps_query = text("SELECT COUNT(id) FROM opportunities")
                    total_opps = await conn.scalar(total_opps_query) or 0
                    
                    one_hour_ago = datetime.now() - timedelta(hours=1)
                    
                    # 使用SQLAlchemy的查询构建器，自动防止SQL注入
                    opps_last_hour_query = select(func.count(opportunities_table.c.id)).where(
                        opportunities_table.c.timestamp > one_hour_ago
                    )
                    opps_last_hour = await conn.scalar(opps_last_hour_query) or 0
                
                return {
                    "status": "running",
                    "timestamp": datetime.now().isoformat(),
                    "total_opportunities": total_opps,
                    "opportunities_last_hour": opps_last_hour,
                    "user": current_user.username
                }
            except Exception as e:
                logger.error(f"获取状态失败: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="内部服务器错误"
                )
        
        @self.app.post("/api/opportunities")
        async def get_opportunities(
            filters: OpportunityFilter,
            current_user: TokenData = Depends(auth_manager.get_current_user)
        ):
            """获取机会列表 - 需要认证且有输入验证"""
            try:
                # 构建安全的查询
                query = select(opportunities_table).where(
                    and_(
                        opportunities_table.c.confidence >= filters.min_confidence,
                        opportunities_table.c.confidence <= filters.max_confidence
                    )
                ).order_by(desc(opportunities_table.c.timestamp)).limit(filters.limit)
                
                # 如果指定了信号类型，添加过滤
                if filters.signal_types:
                    query = query.where(
                        opportunities_table.c.signal_type.in_(filters.signal_types)
                    )
                
                async with engine.connect() as conn:
                    results = await conn.execute(query)
                    opportunities = []
                    
                    for row in results.mappings():
                        # 对输出进行HTML转义，防止XSS
                        opp = dict(row)
                        for key, value in opp.items():
                            if isinstance(value, str):
                                opp[key] = html.escape(value)
                        opportunities.append(opp)
                
                return {"opportunities": opportunities}
                
            except Exception as e:
                logger.error(f"获取机会列表失败: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="内部服务器错误"
                )
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket连接 - 需要认证"""
            await websocket.accept()
            
            # WebSocket认证
            try:
                # 等待认证消息
                auth_message = await asyncio.wait_for(websocket.receive_json(), timeout=10.0)
                
                if "token" not in auth_message:
                    await websocket.close(code=1008, reason="需要认证")
                    return
                
                # 验证令牌
                token = auth_message["token"]
                payload = jwt.decode(token, security_config.SECRET_KEY, algorithms=[security_config.ALGORITHM])
                username = payload.get("sub")
                
                if not username:
                    await websocket.close(code=1008, reason="无效的令牌")
                    return
                
                # 存储认证的连接
                connection_id = secrets.token_urlsafe(16)
                self.active_connections[connection_id] = websocket
                
                try:
                    while True:
                        # 定期发送更新
                        await asyncio.sleep(5)
                        
                        # 获取最新数据
                        status_data = await self._get_safe_status()
                        
                        # 发送给客户端
                        await websocket.send_json({
                            "type": "update",
                            "data": status_data,
                            "timestamp": datetime.now().isoformat()
                        })
                        
                except WebSocketDisconnect:
                    del self.active_connections[connection_id]
                except Exception as e:
                    logger.error(f"WebSocket错误: {e}")
                    if connection_id in self.active_connections:
                        del self.active_connections[connection_id]
                        
            except asyncio.TimeoutError:
                await websocket.close(code=1008, reason="认证超时")
            except JWTError:
                await websocket.close(code=1008, reason="无效的令牌")
            except Exception as e:
                logger.error(f"WebSocket认证失败: {e}")
                await websocket.close(code=1011, reason="内部错误")
        
        @self.app.get("/", response_class=HTMLResponse)
        async def get_dashboard():
            """返回仪表盘HTML - 不需要认证，但HTML已经过安全处理"""
            html_path = Path(__file__).parent.parent / "templates/dashboard_secure.html"
            if html_path.exists():
                # 读取并返回安全的HTML
                with open(html_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                return HTMLResponse(content=content)
            return HTMLResponse(content="<h1>Dashboard not found</h1>", status_code=404)
    
    async def _get_safe_status(self) -> Dict[str, Any]:
        """获取安全的状态数据"""
        try:
            async with engine.connect() as conn:
                # 使用参数化查询
                query = text("""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(CASE WHEN timestamp > :one_hour_ago THEN 1 END) as last_hour
                    FROM opportunities
                """)
                
                result = await conn.execute(
                    query,
                    {"one_hour_ago": datetime.now() - timedelta(hours=1)}
                )
                row = result.fetchone()
                
                return {
                    "total_opportunities": row[0] if row else 0,
                    "opportunities_last_hour": row[1] if row else 0
                }
        except Exception as e:
            logger.error(f"获取状态失败: {e}")
            return {
                "total_opportunities": 0,
                "opportunities_last_hour": 0
            }
    
    async def start(self):
        """启动Web服务器"""
        import uvicorn
        
        # 生产环境配置
        config = uvicorn.Config(
            self.app,
            host="0.0.0.0",
            port=self.config.WEB_PORT,
            log_level="info",
            access_log=True,
            use_colors=False,
            # 启用SSL/TLS（需要证书）
            # ssl_keyfile="path/to/key.pem",
            # ssl_certfile="path/to/cert.pem",
            # 限制请求大小
            limit_max_requests=1000,
            limit_concurrency=100
        )
        
        server = uvicorn.Server(config)
        await server.serve()

# ==============================================================================
# 创建安全的服务器实例
# ==============================================================================

def create_secure_dashboard(config):
    """创建安全的仪表盘服务器"""
    return SecureDashboardServer(config)
