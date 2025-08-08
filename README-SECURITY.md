# 🔐 Crypto Alpha Scout 安全指南

## 密钥管理架构

### Infisical 集成

Crypto Alpha Scout 使用 [Infisical](https://infisical.com/) 作为自托管的密钥管理解决方案，替代传统的 `.env` 文件管理方式。

#### 架构优势

1. **集中化管理**: 所有密钥在一个安全的中心位置管理
2. **版本控制**: 密钥变更的完整审计轨迹
3. **环境隔离**: 开发/测试/生产环境密钥完全隔离
4. **访问控制**: 细粒度的用户权限管理
5. **自动轮换**: 支持密钥的自动定期轮换
6. **零信任**: 应用运行时动态获取密钥，无需本地存储

### 部署架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   应用服务      │    │   Infisical     │    │   MongoDB       │
│                 │    │   (密钥管理)    │    │   (密钥存储)    │
│ ┌─────────────┐ │    │ ┌─────────────┐ │    │ ┌─────────────┐ │
│ │ Scout       │─┼────┤ │ API Server  │─┼────┤ │ Encrypted   │ │
│ │ Services    │ │    │ │             │ │    │ │ Storage     │ │
│ └─────────────┘ │    │ └─────────────┘ │    │ └─────────────┘ │
│                 │    │ ┌─────────────┐ │    └─────────────────┘
│ ┌─────────────┐ │    │ │ Web UI      │ │
│ │ ML Engine   │─┼────┤ │             │ │
│ └─────────────┘ │    │ └─────────────┘ │
└─────────────────┘    └─────────────────┘
```

## 安全配置

### 1. 初始部署

```bash
# 1. 启动基础设施
docker-compose up -d infisical-mongo infisical

# 2. 等待服务就绪
sleep 60

# 3. 初始化密钥
python3 scripts/setup-secrets.py

# 4. 启动应用服务
docker-compose up -d
```

### 2. 密钥配置

#### 生产环境密钥清单

| 类别 | 密钥名称 | 描述 | 示例 |
|------|----------|------|------|
| 数据库 | `DATABASE_URL` | TimescaleDB连接字符串 | `postgresql://user:pass@host:5432/db` |
| 消息队列 | `RABBITMQ_URL` | RabbitMQ连接字符串 | `amqp://user:pass@host:5672/` |
| 缓存 | `REDIS_URL` | Redis连接字符串 | `redis://host:6379/0` |
| API密钥 | `ETHERSCAN_API_KEY` | Etherscan API密钥 | `ABC123...` |
| API密钥 | `GOPLUS_API_KEY` | GoPlus安全API密钥 | `DEF456...` |
| 通知 | `TELEGRAM_BOT_TOKEN` | Telegram机器人令牌 | `123456:ABC-DEF...` |
| 安全 | `JWT_SECRET` | JWT签名密钥 | `随机32字符字符串` |
| 安全 | `ENCRYPTION_KEY` | 数据加密密钥 | `随机32字符字符串` |

### 3. 访问控制

#### Service Token 管理

```python
# 获取服务令牌
import asyncio
from scripts.infisical_integration import InfisicalSecretManager

async def get_service_token():
    manager = InfisicalSecretManager(
        infisical_url="http://localhost:8090",
        project_id="your-project-id"
    )
    
    # 应用启动时自动注入密钥
    await manager.inject_secrets_to_env()
```

#### 权限模型

1. **管理员**: 完整的项目和密钥管理权限
2. **开发者**: 读取开发环境密钥
3. **应用服务**: 仅读取生产环境所需密钥
4. **审计员**: 只读访问审计日志

### 4. 密钥轮换

#### 自动轮换策略

```yaml
# config/rotation-policy.yaml
rotation_policies:
  jwt_secret:
    interval: "30d"
    notification: true
  
  api_keys:
    interval: "90d" 
    notification: true
    
  database_passwords:
    interval: "180d"
    notification: true
    require_approval: true
```

#### 手动轮换流程

```bash
# 1. 生成新密钥
python3 scripts/rotate-secret.py --key JWT_SECRET

# 2. 验证应用功能
python3 scripts/health-check.py

# 3. 确认轮换
python3 scripts/confirm-rotation.py --key JWT_SECRET
```

## 安全最佳实践

### 1. 网络安全

```yaml
# docker-compose.yml 网络配置
networks:
  crypto-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16
```

- 所有服务运行在隔离的Docker网络中
- 只暴露必要的端口到主机
- 使用内部DNS进行服务间通信

### 2. 容器安全

```dockerfile
# 使用非root用户
RUN adduser --disabled-password --gecos '' appuser
USER appuser

# 只安装必要的包
RUN apt-get update && apt-get install -y --no-install-recommends \
    required-package \
    && rm -rf /var/lib/apt/lists/*

# 设置只读文件系统
docker run --read-only --tmpfs /tmp myapp
```

### 3. 数据加密

#### 传输加密
- 所有API通信使用HTTPS/TLS
- 内部服务间通信使用TLS
- 数据库连接使用SSL

#### 存储加密
- 敏感数据使用AES-256加密
- 密钥使用HSM或云密钥管理服务
- 数据库透明数据加密(TDE)

### 4. 审计日志

```python
# 自动记录所有密钥访问
import logging

audit_logger = logging.getLogger('security.audit')
audit_logger.info(f"Secret accessed: {key_name} by {user_id} at {timestamp}")
```

## 监控和告警

### 1. 安全监控

```yaml
# prometheus 规则
groups:
  - name: security
    rules:
      - alert: UnauthorizedSecretAccess
        expr: rate(infisical_unauthorized_access[5m]) > 0
        
      - alert: SuspiciousActivity
        expr: rate(failed_logins[1m]) > 10
        
      - alert: SecretRotationDue
        expr: time() - secret_last_rotation > 2592000  # 30天
```

### 2. 健康检查

```bash
# 定期安全检查
./scripts/security-audit.sh

# 检查项目:
# - 过期密钥
# - 未使用的密钥
# - 权限异常
# - 审计日志异常
```

## 应急响应

### 1. 密钥泄露响应

```bash
# 1. 立即撤销泄露的密钥
python3 scripts/revoke-secret.py --key LEAKED_KEY --emergency

# 2. 生成新密钥
python3 scripts/generate-secret.py --key LEAKED_KEY

# 3. 更新所有使用该密钥的服务
python3 scripts/update-services.py --key LEAKED_KEY

# 4. 审计访问日志
python3 scripts/audit-access.py --key LEAKED_KEY --since "2024-01-01"
```

### 2. 系统入侵响应

```bash
# 1. 隔离受影响的服务
docker-compose stop affected-service

# 2. 轮换所有密钥
python3 scripts/emergency-rotation.py --all

# 3. 重新部署干净的镜像
docker-compose up -d --force-recreate

# 4. 分析入侵路径
python3 scripts/forensic-analysis.py
```

## 合规性

### 1. 数据保护法规

- **GDPR**: 用户数据加密存储，支持数据删除
- **SOX**: 完整的审计轨迹和访问控制
- **PCI DSS**: 支付相关数据的安全处理

### 2. 安全标准

- **ISO 27001**: 信息安全管理体系
- **NIST**: 网络安全框架
- **OWASP**: Web应用安全最佳实践

## 故障排除

### 常见问题

1. **Infisical连接失败**
   ```bash
   # 检查网络连接
   docker-compose logs infisical
   
   # 验证配置
   curl http://localhost:8090/api/status
   ```

2. **密钥获取失败**
   ```bash
   # 检查service token
   python3 scripts/test-token.py
   
   # 验证项目权限
   python3 scripts/check-permissions.py
   ```

3. **服务认证失败**
   ```bash
   # 重新生成token
   python3 scripts/regenerate-token.py
   
   # 更新服务配置
   docker-compose restart affected-service
   ```

---

**重要提醒**: 
- 定期更新所有密钥
- 监控异常访问模式
- 保持系统和依赖项更新
- 定期进行安全审计
- 备份关键配置和密钥
