<<<<<<< HEAD
#!/bin/bash
# setup.sh - Crypto Alpha Scout 一键部署脚本
# 根据PDF建议实现的自动化部署流程

set -e  # 遇到错误立即退出
set -u  # 使用未定义变量时报错

# ============================================
# 配置变量
# ============================================
PROJECT_NAME="crypto-alpha-scout"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="${PROJECT_DIR}/setup.log"
ENV_FILE="${PROJECT_DIR}/.env"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================
# 辅助函数
# ============================================
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
    exit 1
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

check_command() {
    if ! command -v "$1" &> /dev/null; then
        error "$1 未安装。请先安装 $1"
    fi
}

# ============================================
# 系统检查
# ============================================
system_check() {
    log "开始系统检查..."
    
    # 检查操作系统
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS="linux"
        DISTRO=$(lsb_release -si 2>/dev/null || echo "Unknown")
        info "检测到 Linux 系统: $DISTRO"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
        info "检测到 macOS 系统"
    else
        error "不支持的操作系统: $OSTYPE"
    fi
    
    # 检查必要的命令
    log "检查必要的工具..."
    check_command "docker"
    check_command "docker-compose"
    check_command "git"
    check_command "python3"
    check_command "pip3"
    check_command "curl"
    
    # 检查Docker服务
    if ! docker info &> /dev/null; then
        error "Docker服务未运行。请启动Docker服务"
    fi
    
    # 检查Python版本
    PYTHON_VERSION=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
    REQUIRED_VERSION="3.9"
    if [[ $(echo "$PYTHON_VERSION < $REQUIRED_VERSION" | bc) -eq 1 ]]; then
        error "Python版本过低。需要 >= $REQUIRED_VERSION，当前: $PYTHON_VERSION"
    fi
    
    log "✅ 系统检查通过"
}

# ============================================
# 创建目录结构
# ============================================
create_directories() {
    log "创建项目目录结构..."
    
    directories=(
        "data"
        "logs"
        "ml_models"
        "historical_data"
        "config/rabbitmq"
        "config/redis"
        "config/prometheus"
        "config/grafana/provisioning/dashboards"
        "config/grafana/provisioning/datasources"
        "config/traefik"
        "config/loki"
        "scripts"
        "docker"
        "tests/unit"
        "tests/integration"
        "tests/performance"
        "reports"
        "backups"
    )
    
    for dir in "${directories[@]}"; do
        mkdir -p "${PROJECT_DIR}/${dir}"
        info "创建目录: ${dir}"
    done
    
    log "✅ 目录结构创建完成"
}

# ============================================
# 生成密钥和配置
# ============================================
generate_secrets() {
    log "生成密钥和配置..."
    
    # 生成随机密码的函数
    generate_password() {
        openssl rand -base64 32 | tr -d "=+/" | cut -c1-25
    }
    
    # 如果.env文件不存在，创建它
    if [ ! -f "$ENV_FILE" ]; then
        cat > "$ENV_FILE" <<EOF
# ============================================
# Crypto Alpha Scout 环境配置
# 自动生成于: $(date)
# ============================================

# 数据库配置
DB_USER=crypto_user
DB_PASSWORD=$(generate_password)
DB_NAME=crypto_scout
DATABASE_URL=postgresql+asyncpg://\${DB_USER}:\${DB_PASSWORD}@timescaledb:5432/\${DB_NAME}

# RabbitMQ配置
RABBITMQ_USER=admin
RABBITMQ_PASS=$(generate_password)
RABBITMQ_URL=amqp://\${RABBITMQ_USER}:\${RABBITMQ_PASS}@rabbitmq:5672/

# Redis配置
REDIS_URL=redis://redis:6379
REDIS_PASSWORD=$(generate_password)

# Infisical密钥管理
INFISICAL_ENCRYPTION_KEY=$(generate_password)
INFISICAL_JWT_SECRET=$(generate_password)

# MongoDB (for Infisical)
MONGO_USER=infisical
MONGO_PASSWORD=$(generate_password)

# Web配置
WEB_SECRET_KEY=$(generate_password)
WEB_PORT=8000

# Telegram Bot (需要手动填写)
TELEGRAM_BOT_TOKEN=

# 监控配置
GRAFANA_USER=admin
GRAFANA_PASSWORD=$(generate_password)

# Web3 Providers (需要手动填写)
WEB3_PROVIDER_ETH=https://eth.llamarpc.com
WEB3_PROVIDER_BSC=https://bsc-dataseed.binance.org

# API Keys (需要手动填写)
COINGECKO_API_KEY=
GITHUB_TOKEN=

# 日志级别
LOG_LEVEL=INFO

# 环境
ENVIRONMENT=production
EOF
        
        chmod 600 "$ENV_FILE"
        log "✅ 环境配置文件已生成: $ENV_FILE"
        warning "请编辑 $ENV_FILE 填写必要的API密钥"
    else
        warning ".env文件已存在，跳过生成"
    fi
}

# ============================================
# 创建配置文件
# ============================================
create_config_files() {
    log "创建配置文件..."
    
    # RabbitMQ配置
    cat > "${PROJECT_DIR}/config/rabbitmq/rabbitmq.conf" <<EOF
# RabbitMQ配置
default_user = admin
default_pass = admin
disk_free_limit.absolute = 2GB
vm_memory_high_watermark.relative = 0.4
management.tcp.port = 15672
EOF
    
    # Redis配置
    cat > "${PROJECT_DIR}/config/redis/redis.conf" <<EOF
# Redis配置
maxmemory 1gb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
appendonly yes
appendfsync everysec
requirepass \${REDIS_PASSWORD}
EOF
    
    # Prometheus配置
    cat > "${PROJECT_DIR}/config/prometheus/prometheus.yml" <<EOF
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'crypto-scout'
    static_configs:
      - targets: 
        - 'web-dashboard:8000'
        - 'market-scout:9090'
        - 'defi-scout:9090'
        - 'chain-scout:9090'
        - 'sentiment-scout:9090'
        - 'analyzer:9090'
        - 'ml-predictor:9090'
EOF
    
    # Grafana数据源配置
    cat > "${PROJECT_DIR}/config/grafana/provisioning/datasources/prometheus.yml" <<EOF
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: true
  
  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
    editable: true
  
  - name: TimescaleDB
    type: postgres
    url: timescaledb:5432
    database: crypto_scout
    user: \${DB_USER}
    secureJsonData:
      password: \${DB_PASSWORD}
    jsonData:
      sslmode: 'disable'
      postgresVersion: 1500
      timescaledb: true
EOF
    
    log "✅ 配置文件创建完成"
}

# ============================================
# 安装Python依赖
# ============================================
install_python_dependencies() {
    log "安装Python依赖..."
    
    # 创建虚拟环境
    if [ ! -d "${PROJECT_DIR}/venv" ]; then
        python3 -m venv "${PROJECT_DIR}/venv"
        log "虚拟环境已创建"
    fi
    
    # 激活虚拟环境并安装依赖
    source "${PROJECT_DIR}/venv/bin/activate"
    
    pip install --upgrade pip
    pip install -r "${PROJECT_DIR}/requirements.txt"
    
    # 安装开发依赖
    if [ -f "${PROJECT_DIR}/requirements-dev.txt" ]; then
        pip install -r "${PROJECT_DIR}/requirements-dev.txt"
    fi
    
    deactivate
    
    log "✅ Python依赖安装完成"
}

# ============================================
# 初始化数据库
# ============================================
init_database() {
    log "初始化数据库..."
    
    # 创建初始化SQL脚本
    cat > "${PROJECT_DIR}/scripts/init-db.sql" <<EOF
-- 初始化数据库
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- 创建基础表结构
-- (这里应该包含所有表的创建语句)
EOF
    
    # 创建超表脚本
    cat > "${PROJECT_DIR}/scripts/create-hypertables.sql" <<EOF
-- 创建TimescaleDB超表
SELECT create_hypertable('market_data', 'time', if_not_exists => TRUE);
SELECT create_hypertable('onchain_events', 'time', if_not_exists => TRUE);
SELECT create_hypertable('alpha_opportunities', 'time', if_not_exists => TRUE);
SELECT create_hypertable('social_sentiment', 'time', if_not_exists => TRUE);
SELECT create_hypertable('developer_activity', 'time', if_not_exists => TRUE);

-- 设置数据保留策略
SELECT add_retention_policy('market_data', INTERVAL '90 days');
SELECT add_retention_policy('social_sentiment', INTERVAL '30 days');
EOF
    
    log "✅ 数据库初始化脚本已创建"
}

# ============================================
# 构建Docker镜像
# ============================================
build_docker_images() {
    log "构建Docker镜像..."
    
    # 构建所有服务的镜像
    docker-compose -f "${PROJECT_DIR}/docker-compose.production.yml" build --parallel
    
    log "✅ Docker镜像构建完成"
}

# ============================================
# 启动服务
# ============================================
start_services() {
    log "启动服务..."
    
    # 启动基础服务
    docker-compose -f "${PROJECT_DIR}/docker-compose.production.yml" up -d \
        rabbitmq timescaledb redis infisical-mongo infisical
    
    log "等待基础服务启动..."
    sleep 30
    
    # 启动应用服务
    docker-compose -f "${PROJECT_DIR}/docker-compose.production.yml" up -d
    
    log "✅ 所有服务已启动"
}

# ============================================
# 健康检查
# ============================================
health_check() {
    log "执行健康检查..."
    
    services=("rabbitmq" "timescaledb" "redis" "market-scout" "web-dashboard")
    
    for service in "${services[@]}"; do
        if docker-compose -f "${PROJECT_DIR}/docker-compose.production.yml" ps | grep -q "$service.*Up"; then
            info "✅ $service 运行正常"
        else
            warning "⚠️ $service 未正常运行"
        fi
    done
    
    # 检查Web界面
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000 | grep -q "200"; then
        log "✅ Web界面可访问: http://localhost:8000"
    else
        warning "Web界面无法访问"
    fi
    
    # 检查RabbitMQ管理界面
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:15672 | grep -q "200"; then
        log "✅ RabbitMQ管理界面可访问: http://localhost:15672"
    else
        warning "RabbitMQ管理界面无法访问"
    fi
}

# ============================================
# 显示访问信息
# ============================================
show_access_info() {
    log "============================================"
    log "🎉 Crypto Alpha Scout 部署成功！"
    log "============================================"
    log ""
    log "访问地址:"
    log "  - Web控制台: http://localhost:8000"
    log "  - RabbitMQ管理: http://localhost:15672"
    log "  - Grafana监控: http://localhost:3000"
    log "  - Prometheus: http://localhost:9090"
    log ""
    log "默认账号:"
    
    # 从.env文件读取密码
    source "$ENV_FILE"
    
    log "  - RabbitMQ: admin / ${RABBITMQ_PASS}"
    log "  - Grafana: admin / ${GRAFANA_PASSWORD}"
    log ""
    log "下一步:"
    log "  1. 编辑 .env 文件，填写API密钥"
    log "  2. 重启服务: docker-compose -f docker-compose.production.yml restart"
    log "  3. 查看日志: docker-compose -f docker-compose.production.yml logs -f"
    log ""
    log "文档: https://github.com/your-repo/crypto-scout/wiki"
    log "============================================"
}

# ============================================
# 清理函数
# ============================================
cleanup() {
    warning "清理临时文件..."
    # 清理临时文件
}

# ============================================
# 主函数
# ============================================
main() {
    log "============================================"
    log "Crypto Alpha Scout 一键部署脚本"
    log "============================================"
    
    # 切换到项目目录
    cd "$PROJECT_DIR"
    
    # 执行安装步骤
    system_check
    create_directories
    generate_secrets
    create_config_files
    init_database
    install_python_dependencies
    build_docker_images
    start_services
    health_check
    show_access_info
    
    # 设置清理钩子
    trap cleanup EXIT
}

# ============================================
# 脚本入口
# ============================================
if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  --help, -h     显示帮助信息"
    echo "  --clean        清理并重新安装"
    echo "  --update       更新现有安装"
    echo "  --stop         停止所有服务"
    echo "  --restart      重启所有服务"
    echo "  --logs         查看日志"
    echo "  --backup       备份数据"
    exit 0
fi

if [ "${1:-}" = "--clean" ]; then
    warning "清理现有安装..."
    docker-compose -f "${PROJECT_DIR}/docker-compose.production.yml" down -v
    rm -rf "${PROJECT_DIR}/data" "${PROJECT_DIR}/logs"
fi

if [ "${1:-}" = "--stop" ]; then
    log "停止所有服务..."
    docker-compose -f "${PROJECT_DIR}/docker-compose.production.yml" down
    exit 0
fi

if [ "${1:-}" = "--restart" ]; then
    log "重启所有服务..."
    docker-compose -f "${PROJECT_DIR}/docker-compose.production.yml" restart
    exit 0
fi

if [ "${1:-}" = "--logs" ]; then
    docker-compose -f "${PROJECT_DIR}/docker-compose.production.yml" logs -f
    exit 0
fi

if [ "${1:-}" = "--backup" ]; then
    log "备份数据..."
    timestamp=$(date +%Y%m%d_%H%M%S)
    backup_dir="${PROJECT_DIR}/backups/backup_${timestamp}"
    mkdir -p "$backup_dir"
    
    # 备份数据库
    docker-compose -f "${PROJECT_DIR}/docker-compose.production.yml" exec -T timescaledb \
        pg_dump -U "$DB_USER" "$DB_NAME" > "${backup_dir}/database.sql"
    
    # 备份配置
    cp -r "${PROJECT_DIR}/config" "${backup_dir}/"
    cp "${PROJECT_DIR}/.env" "${backup_dir}/"
    
    # 备份ML模型
    cp -r "${PROJECT_DIR}/ml_models" "${backup_dir}/"
    
    log "✅ 备份完成: ${backup_dir}"
    exit 0
fi

# 运行主函数
=======
#!/bin/bash
# setup.sh - Crypto Alpha Scout 一键部署脚本
# 根据PDF建议实现的自动化部署流程

set -e  # 遇到错误立即退出
set -u  # 使用未定义变量时报错

# ============================================
# 配置变量
# ============================================
PROJECT_NAME="crypto-alpha-scout"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="${PROJECT_DIR}/setup.log"
ENV_FILE="${PROJECT_DIR}/.env"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================
# 辅助函数
# ============================================
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
    exit 1
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

check_command() {
    if ! command -v "$1" &> /dev/null; then
        error "$1 未安装。请先安装 $1"
    fi
}

# ============================================
# 系统检查
# ============================================
system_check() {
    log "开始系统检查..."
    
    # 检查操作系统
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS="linux"
        DISTRO=$(lsb_release -si 2>/dev/null || echo "Unknown")
        info "检测到 Linux 系统: $DISTRO"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
        info "检测到 macOS 系统"
    else
        error "不支持的操作系统: $OSTYPE"
    fi
    
    # 检查必要的命令
    log "检查必要的工具..."
    check_command "docker"
    check_command "docker-compose"
    check_command "git"
    check_command "python3"
    check_command "pip3"
    check_command "curl"
    
    # 检查Docker服务
    if ! docker info &> /dev/null; then
        error "Docker服务未运行。请启动Docker服务"
    fi
    
    # 检查Python版本
    PYTHON_VERSION=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
    REQUIRED_VERSION="3.9"
    if [[ $(echo "$PYTHON_VERSION < $REQUIRED_VERSION" | bc) -eq 1 ]]; then
        error "Python版本过低。需要 >= $REQUIRED_VERSION，当前: $PYTHON_VERSION"
    fi
    
    log "✅ 系统检查通过"
}

# ============================================
# 创建目录结构
# ============================================
create_directories() {
    log "创建项目目录结构..."
    
    directories=(
        "data"
        "logs"
        "ml_models"
        "historical_data"
        "config/rabbitmq"
        "config/redis"
        "config/prometheus"
        "config/grafana/provisioning/dashboards"
        "config/grafana/provisioning/datasources"
        "config/traefik"
        "config/loki"
        "scripts"
        "docker"
        "tests/unit"
        "tests/integration"
        "tests/performance"
        "reports"
        "backups"
    )
    
    for dir in "${directories[@]}"; do
        mkdir -p "${PROJECT_DIR}/${dir}"
        info "创建目录: ${dir}"
    done
    
    log "✅ 目录结构创建完成"
}

# ============================================
# 生成密钥和配置
# ============================================
generate_secrets() {
    log "生成密钥和配置..."
    
    # 生成随机密码的函数
    generate_password() {
        openssl rand -base64 32 | tr -d "=+/" | cut -c1-25
    }
    
    # 如果.env文件不存在，创建它
    if [ ! -f "$ENV_FILE" ]; then
        cat > "$ENV_FILE" <<EOF
# ============================================
# Crypto Alpha Scout 环境配置
# 自动生成于: $(date)
# ============================================

# 数据库配置
DB_USER=crypto_user
DB_PASSWORD=$(generate_password)
DB_NAME=crypto_scout
DATABASE_URL=postgresql+asyncpg://\${DB_USER}:\${DB_PASSWORD}@timescaledb:5432/\${DB_NAME}

# RabbitMQ配置
RABBITMQ_USER=admin
RABBITMQ_PASS=$(generate_password)
RABBITMQ_URL=amqp://\${RABBITMQ_USER}:\${RABBITMQ_PASS}@rabbitmq:5672/

# Redis配置
REDIS_URL=redis://redis:6379
REDIS_PASSWORD=$(generate_password)

# Infisical密钥管理
INFISICAL_ENCRYPTION_KEY=$(generate_password)
INFISICAL_JWT_SECRET=$(generate_password)

# MongoDB (for Infisical)
MONGO_USER=infisical
MONGO_PASSWORD=$(generate_password)

# Web配置
WEB_SECRET_KEY=$(generate_password)
WEB_PORT=8000

# Telegram Bot (需要手动填写)
TELEGRAM_BOT_TOKEN=

# 监控配置
GRAFANA_USER=admin
GRAFANA_PASSWORD=$(generate_password)

# Web3 Providers (需要手动填写)
WEB3_PROVIDER_ETH=https://eth.llamarpc.com
WEB3_PROVIDER_BSC=https://bsc-dataseed.binance.org

# API Keys (需要手动填写)
COINGECKO_API_KEY=
GITHUB_TOKEN=

# 日志级别
LOG_LEVEL=INFO

# 环境
ENVIRONMENT=production
EOF
        
        chmod 600 "$ENV_FILE"
        log "✅ 环境配置文件已生成: $ENV_FILE"
        warning "请编辑 $ENV_FILE 填写必要的API密钥"
    else
        warning ".env文件已存在，跳过生成"
    fi
}

# ============================================
# 创建配置文件
# ============================================
create_config_files() {
    log "创建配置文件..."
    
    # RabbitMQ配置
    cat > "${PROJECT_DIR}/config/rabbitmq/rabbitmq.conf" <<EOF
# RabbitMQ配置
default_user = admin
default_pass = admin
disk_free_limit.absolute = 2GB
vm_memory_high_watermark.relative = 0.4
management.tcp.port = 15672
EOF
    
    # Redis配置
    cat > "${PROJECT_DIR}/config/redis/redis.conf" <<EOF
# Redis配置
maxmemory 1gb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
appendonly yes
appendfsync everysec
requirepass \${REDIS_PASSWORD}
EOF
    
    # Prometheus配置
    cat > "${PROJECT_DIR}/config/prometheus/prometheus.yml" <<EOF
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'crypto-scout'
    static_configs:
      - targets: 
        - 'web-dashboard:8000'
        - 'market-scout:9090'
        - 'defi-scout:9090'
        - 'chain-scout:9090'
        - 'sentiment-scout:9090'
        - 'analyzer:9090'
        - 'ml-predictor:9090'
EOF
    
    # Grafana数据源配置
    cat > "${PROJECT_DIR}/config/grafana/provisioning/datasources/prometheus.yml" <<EOF
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: true
  
  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
    editable: true
  
  - name: TimescaleDB
    type: postgres
    url: timescaledb:5432
    database: crypto_scout
    user: \${DB_USER}
    secureJsonData:
      password: \${DB_PASSWORD}
    jsonData:
      sslmode: 'disable'
      postgresVersion: 1500
      timescaledb: true
EOF
    
    log "✅ 配置文件创建完成"
}

# ============================================
# 安装Python依赖
# ============================================
install_python_dependencies() {
    log "安装Python依赖..."
    
    # 创建虚拟环境
    if [ ! -d "${PROJECT_DIR}/venv" ]; then
        python3 -m venv "${PROJECT_DIR}/venv"
        log "虚拟环境已创建"
    fi
    
    # 激活虚拟环境并安装依赖
    source "${PROJECT_DIR}/venv/bin/activate"
    
    pip install --upgrade pip
    pip install -r "${PROJECT_DIR}/requirements.txt"
    
    # 安装开发依赖
    if [ -f "${PROJECT_DIR}/requirements-dev.txt" ]; then
        pip install -r "${PROJECT_DIR}/requirements-dev.txt"
    fi
    
    deactivate
    
    log "✅ Python依赖安装完成"
}

# ============================================
# 初始化数据库
# ============================================
init_database() {
    log "初始化数据库..."
    
    # 创建初始化SQL脚本
    cat > "${PROJECT_DIR}/scripts/init-db.sql" <<EOF
-- 初始化数据库
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- 创建基础表结构
-- (这里应该包含所有表的创建语句)
EOF
    
    # 创建超表脚本
    cat > "${PROJECT_DIR}/scripts/create-hypertables.sql" <<EOF
-- 创建TimescaleDB超表
SELECT create_hypertable('market_data', 'time', if_not_exists => TRUE);
SELECT create_hypertable('onchain_events', 'time', if_not_exists => TRUE);
SELECT create_hypertable('alpha_opportunities', 'time', if_not_exists => TRUE);
SELECT create_hypertable('social_sentiment', 'time', if_not_exists => TRUE);
SELECT create_hypertable('developer_activity', 'time', if_not_exists => TRUE);

-- 设置数据保留策略
SELECT add_retention_policy('market_data', INTERVAL '90 days');
SELECT add_retention_policy('social_sentiment', INTERVAL '30 days');
EOF
    
    log "✅ 数据库初始化脚本已创建"
}

# ============================================
# 构建Docker镜像
# ============================================
build_docker_images() {
    log "构建Docker镜像..."
    
    # 构建所有服务的镜像
    docker-compose -f "${PROJECT_DIR}/docker-compose.production.yml" build --parallel
    
    log "✅ Docker镜像构建完成"
}

# ============================================
# 启动服务
# ============================================
start_services() {
    log "启动服务..."
    
    # 启动基础服务
    docker-compose -f "${PROJECT_DIR}/docker-compose.production.yml" up -d \
        rabbitmq timescaledb redis infisical-mongo infisical
    
    log "等待基础服务启动..."
    sleep 30
    
    # 启动应用服务
    docker-compose -f "${PROJECT_DIR}/docker-compose.production.yml" up -d
    
    log "✅ 所有服务已启动"
}

# ============================================
# 健康检查
# ============================================
health_check() {
    log "执行健康检查..."
    
    services=("rabbitmq" "timescaledb" "redis" "market-scout" "web-dashboard")
    
    for service in "${services[@]}"; do
        if docker-compose -f "${PROJECT_DIR}/docker-compose.production.yml" ps | grep -q "$service.*Up"; then
            info "✅ $service 运行正常"
        else
            warning "⚠️ $service 未正常运行"
        fi
    done
    
    # 检查Web界面
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000 | grep -q "200"; then
        log "✅ Web界面可访问: http://localhost:8000"
    else
        warning "Web界面无法访问"
    fi
    
    # 检查RabbitMQ管理界面
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:15672 | grep -q "200"; then
        log "✅ RabbitMQ管理界面可访问: http://localhost:15672"
    else
        warning "RabbitMQ管理界面无法访问"
    fi
}

# ============================================
# 显示访问信息
# ============================================
show_access_info() {
    log "============================================"
    log "🎉 Crypto Alpha Scout 部署成功！"
    log "============================================"
    log ""
    log "访问地址:"
    log "  - Web控制台: http://localhost:8000"
    log "  - RabbitMQ管理: http://localhost:15672"
    log "  - Grafana监控: http://localhost:3000"
    log "  - Prometheus: http://localhost:9090"
    log ""
    log "默认账号:"
    
    # 从.env文件读取密码
    source "$ENV_FILE"
    
    log "  - RabbitMQ: admin / ${RABBITMQ_PASS}"
    log "  - Grafana: admin / ${GRAFANA_PASSWORD}"
    log ""
    log "下一步:"
    log "  1. 编辑 .env 文件，填写API密钥"
    log "  2. 重启服务: docker-compose -f docker-compose.production.yml restart"
    log "  3. 查看日志: docker-compose -f docker-compose.production.yml logs -f"
    log ""
    log "文档: https://github.com/your-repo/crypto-scout/wiki"
    log "============================================"
}

# ============================================
# 清理函数
# ============================================
cleanup() {
    warning "清理临时文件..."
    # 清理临时文件
}

# ============================================
# 主函数
# ============================================
main() {
    log "============================================"
    log "Crypto Alpha Scout 一键部署脚本"
    log "============================================"
    
    # 切换到项目目录
    cd "$PROJECT_DIR"
    
    # 执行安装步骤
    system_check
    create_directories
    generate_secrets
    create_config_files
    init_database
    install_python_dependencies
    build_docker_images
    start_services
    health_check
    show_access_info
    
    # 设置清理钩子
    trap cleanup EXIT
}

# ============================================
# 脚本入口
# ============================================
if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  --help, -h     显示帮助信息"
    echo "  --clean        清理并重新安装"
    echo "  --update       更新现有安装"
    echo "  --stop         停止所有服务"
    echo "  --restart      重启所有服务"
    echo "  --logs         查看日志"
    echo "  --backup       备份数据"
    exit 0
fi

if [ "${1:-}" = "--clean" ]; then
    warning "清理现有安装..."
    docker-compose -f "${PROJECT_DIR}/docker-compose.production.yml" down -v
    rm -rf "${PROJECT_DIR}/data" "${PROJECT_DIR}/logs"
fi

if [ "${1:-}" = "--stop" ]; then
    log "停止所有服务..."
    docker-compose -f "${PROJECT_DIR}/docker-compose.production.yml" down
    exit 0
fi

if [ "${1:-}" = "--restart" ]; then
    log "重启所有服务..."
    docker-compose -f "${PROJECT_DIR}/docker-compose.production.yml" restart
    exit 0
fi

if [ "${1:-}" = "--logs" ]; then
    docker-compose -f "${PROJECT_DIR}/docker-compose.production.yml" logs -f
    exit 0
fi

if [ "${1:-}" = "--backup" ]; then
    log "备份数据..."
    timestamp=$(date +%Y%m%d_%H%M%S)
    backup_dir="${PROJECT_DIR}/backups/backup_${timestamp}"
    mkdir -p "$backup_dir"
    
    # 备份数据库
    docker-compose -f "${PROJECT_DIR}/docker-compose.production.yml" exec -T timescaledb \
        pg_dump -U "$DB_USER" "$DB_NAME" > "${backup_dir}/database.sql"
    
    # 备份配置
    cp -r "${PROJECT_DIR}/config" "${backup_dir}/"
    cp "${PROJECT_DIR}/.env" "${backup_dir}/"
    
    # 备份ML模型
    cp -r "${PROJECT_DIR}/ml_models" "${backup_dir}/"
    
    log "✅ 备份完成: ${backup_dir}"
    exit 0
fi

# 运行主函数
>>>>>>> e5cf058720e42a15be9be28747f9f02b5d15a885
main "$@"