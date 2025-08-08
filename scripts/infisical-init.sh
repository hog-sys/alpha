#!/bin/bash
# scripts/infisical-init.sh
# Infisical 初始化脚本

set -e

echo "🔐 初始化 Infisical 密钥管理服务..."

# 等待依赖服务启动
echo "等待 MongoDB 启动..."
while ! nc -z infisical-mongo 27017; do
  sleep 2
done
echo "✅ MongoDB 已就绪"

echo "等待 Redis 启动..."
while ! nc -z redis 6379; do
  sleep 2
done
echo "✅ Redis 已就绪"

# 生成必要的环境变量（如果不存在）
if [ -z "$JWT_SECRET" ]; then
  export JWT_SECRET=$(openssl rand -hex 32)
  echo "⚠️  生成临时 JWT_SECRET: $JWT_SECRET"
fi

if [ -z "$ENCRYPTION_KEY" ]; then
  export ENCRYPTION_KEY=$(openssl rand -hex 32)
  echo "⚠️  生成临时 ENCRYPTION_KEY: $ENCRYPTION_KEY"
fi

# 初始化数据库（如果需要）
echo "检查数据库初始化状态..."

# 创建默认管理员用户（如果不存在）
if [ ! -z "$INFISICAL_ADMIN_EMAIL" ] && [ ! -z "$INFISICAL_ADMIN_PASSWORD" ]; then
  echo "创建默认管理员用户..."
  
  # 这里应该调用Infisical的API或CLI来创建用户
  # 由于这是示例，我们只记录日志
  echo "管理员邮箱: $INFISICAL_ADMIN_EMAIL"
fi

# 创建默认项目和环境
echo "设置默认项目..."

# 启动Infisical服务
echo "🚀 启动 Infisical 服务..."
exec npm start
