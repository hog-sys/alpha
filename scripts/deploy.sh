#!/bin/bash
# scripts/deploy.sh
# Crypto Alpha Scout 部署脚本 - 完整的生产部署流程

set -e

echo "🚀 开始部署 Crypto Alpha Scout..."

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查依赖
check_dependencies() {
    log_info "检查系统依赖..."
    
    # 检查 Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装。请先安装 Docker。"
        exit 1
    fi
    
    # 检查 Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose 未安装。请先安装 Docker Compose。"
        exit 1
    fi
    
    # 检查 Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 未安装。请先安装 Python 3。"
        exit 1
    fi
    
    log_success "依赖检查通过"
}

# 环境准备
prepare_environment() {
    log_info "准备部署环境..."
    
    # 创建必要的目录
    mkdir -p logs data backups ml_models config/ssl
    
    # 设置权限
    chmod +x scripts/*.sh scripts/*.py
    
    # 检查环境变量文件
    if [ ! -f .env ]; then
        if [ -f config/env.template ]; then
            log_warning "未找到 .env 文件，从模板复制..."
            cp config/env.template .env
            log_warning "请编辑 .env 文件并填入实际配置值"
            read -p "按 Enter 继续，或 Ctrl+C 退出编辑配置..."
        else
            log_error "未找到环境配置文件"
            exit 1
        fi
    fi
    
    log_success "环境准备完成"
}

# 构建镜像
build_images() {
    log_info "构建 Docker 镜像..."
    
    # 构建所有自定义镜像
    docker-compose build --parallel
    
    log_success "镜像构建完成"
}

# 启动基础服务
start_infrastructure() {
    log_info "启动基础设施服务..."
    
    # 启动数据库、消息队列、缓存
    docker-compose up -d timescaledb rabbitmq redis
    
    # 等待服务就绪
    log_info "等待基础服务启动..."
    sleep 30
    
    # 检查服务状态
    if ! docker-compose ps | grep -q "timescaledb.*Up"; then
        log_error "TimescaleDB 启动失败"
        docker-compose logs timescaledb
        exit 1
    fi
    
    if ! docker-compose ps | grep -q "rabbitmq.*Up"; then
        log_error "RabbitMQ 启动失败"
        docker-compose logs rabbitmq
        exit 1
    fi
    
    log_success "基础设施服务启动完成"
}

# 启动密钥管理
start_secrets_management() {
    log_info "启动密钥管理服务..."
    
    # 启动 Infisical 和 MongoDB
    docker-compose up -d infisical-mongo infisical
    
    # 等待 Infisical 启动
    log_info "等待 Infisical 启动..."
    sleep 60
    
    # 检查 Infisical 状态
    if ! docker-compose ps | grep -q "infisical.*Up"; then
        log_error "Infisical 启动失败"
        docker-compose logs infisical
        exit 1
    fi
    
    # 设置密钥
    log_info "初始化密钥配置..."
    python3 scripts/setup-secrets.py
    
    log_success "密钥管理服务启动完成"
}

# 数据库初始化
init_database() {
    log_info "初始化数据库..."
    
    # 运行数据库迁移
    if [ -f scripts/sqlite_to_timescale.py ]; then
        log_info "执行数据库迁移..."
        python3 scripts/sqlite_to_timescale.py
    fi
    
    log_success "数据库初始化完成"
}

# 启动应用服务
start_application() {
    log_info "启动应用服务..."
    
    # 启动所有应用服务
    docker-compose up -d \
        market-scout \
        defi-scout \
        chain-scout \
        sentiment-scout \
        contract-scout \
        persistence \
        analyzer \
        ml-predictor \
        web-dashboard \
        telegram-bot
    
    # 等待服务启动
    log_info "等待应用服务启动..."
    sleep 30
    
    log_success "应用服务启动完成"
}

# 启动监控服务
start_monitoring() {
    log_info "启动监控服务..."
    
    # 启动监控组件
    docker-compose up -d prometheus grafana loki traefik
    
    log_success "监控服务启动完成"
}

# 健康检查
health_check() {
    log_info "执行健康检查..."
    
    # 检查所有服务状态
    services=(
        "timescaledb"
        "rabbitmq" 
        "redis"
        "infisical"
        "market-scout"
        "defi-scout"
        "chain-scout"
        "sentiment-scout"
        "contract-scout"
        "persistence"
        "analyzer"
        "web-dashboard"
        "telegram-bot"
        "prometheus"
        "grafana"
    )
    
    failed_services=()
    
    for service in "${services[@]}"; do
        if docker-compose ps | grep -q "${service}.*Up"; then
            log_success "✅ $service"
        else
            log_error "❌ $service"
            failed_services+=("$service")
        fi
    done
    
    if [ ${#failed_services[@]} -eq 0 ]; then
        log_success "所有服务运行正常"
    else
        log_error "以下服务启动失败: ${failed_services[*]}"
        log_info "查看失败服务日志:"
        for service in "${failed_services[@]}"; do
            echo "=== $service 日志 ==="
            docker-compose logs --tail=20 "$service"
        done
        exit 1
    fi
}

# 显示部署信息
show_deployment_info() {
    echo ""
    echo "=============================================="
    echo "🎉 Crypto Alpha Scout 部署完成！"
    echo "=============================================="
    echo ""
    echo "📊 服务访问地址:"
    echo "  • Web Dashboard: http://localhost:8000"
    echo "  • Infisical 密钥管理: http://localhost:8090"
    echo "  • RabbitMQ 管理界面: http://localhost:15672"
    echo "  • Grafana 监控: http://localhost:3000"
    echo "  • Prometheus: http://localhost:9090"
    echo ""
    echo "🔐 默认登录信息:"
    echo "  • RabbitMQ: crypto_user / crypto_pass"
    echo "  • Grafana: admin / admin123"
    echo "  • Infisical: admin@cryptoalphascout.com / SecureAdmin123!"
    echo ""
    echo "📝 常用命令:"
    echo "  • 查看服务状态: docker-compose ps"
    echo "  • 查看日志: docker-compose logs [service-name]"
    echo "  • 停止所有服务: docker-compose down"
    echo "  • 重启服务: docker-compose restart [service-name]"
    echo ""
    echo "⚠️  重要提醒:"
    echo "  • 请修改默认密码"
    echo "  • 请配置实际的 API 密钥"
    echo "  • 请设置适当的防火墙规则"
    echo "  • 建议启用 HTTPS"
    echo ""
    echo "=============================================="
}

# 清理函数
cleanup() {
    if [ $? -ne 0 ]; then
        log_error "部署过程中发生错误"
        log_info "查看服务状态:"
        docker-compose ps
        log_info "如需清理，运行: docker-compose down"
    fi
}

# 主函数
main() {
    # 设置错误处理
    trap cleanup EXIT
    
    log_info "开始 Crypto Alpha Scout 生产部署"
    
    # 执行部署步骤
    check_dependencies
    prepare_environment
    build_images
    start_infrastructure
    start_secrets_management
    init_database
    start_application
    start_monitoring
    health_check
    show_deployment_info
    
    log_success "🎉 部署完成！"
}

# 参数处理
case "${1:-deploy}" in
    "deploy")
        main
        ;;
    "check")
        health_check
        ;;
    "stop")
        log_info "停止所有服务..."
        docker-compose down
        log_success "所有服务已停止"
        ;;
    "restart")
        log_info "重启所有服务..."
        docker-compose restart
        log_success "所有服务已重启"
        ;;
    "logs")
        docker-compose logs -f "${2:-}"
        ;;
    "help")
        echo "用法: $0 [command]"
        echo ""
        echo "命令:"
        echo "  deploy    - 完整部署 (默认)"
        echo "  check     - 健康检查"
        echo "  stop      - 停止所有服务"
        echo "  restart   - 重启所有服务"
        echo "  logs      - 查看日志"
        echo "  help      - 显示帮助"
        ;;
    *)
        log_error "未知命令: $1"
        echo "运行 '$0 help' 查看可用命令"
        exit 1
        ;;
esac
