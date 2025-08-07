#!/bin/bash
# apply_security_fixes.sh - 一键应用所有安全修复

set -e  # 遇到错误立即退出

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 日志函数
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# 检查必要的工具
check_requirements() {
    log "检查系统要求..."
    
    # 检查Python版本
    if ! python3 --version &> /dev/null; then
        error "Python3未安装"
    fi
    
    PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    REQUIRED_VERSION="3.9"
    
    if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
        error "Python版本过低。需要 >= $REQUIRED_VERSION，当前: $PYTHON_VERSION"
    fi
    
    # 检查pip
    if ! pip3 --version &> /dev/null; then
        error "pip3未安装"
    fi
    
    # 检查git
    if ! git --version &> /dev/null; then
        error "git未安装"
    fi
    
    log "✅ 系统要求检查通过"
}

# 备份现有代码
backup_code() {
    log "备份现有代码..."
    
    BACKUP_DIR="backups/security_backup_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    
    # 备份关键文件
    cp -r src/ "$BACKUP_DIR/" 2>/dev/null || true
    cp *.py "$BACKUP_DIR/" 2>/dev/null || true
    cp .env "$BACKUP_DIR/" 2>/dev/null || true
    cp requirements*.txt "$BACKUP_DIR/" 2>/dev/null || true
    
    # Git备份
    if [ -d .git ]; then
        git add -A
        git commit -m "Backup before security fixes $(date +%Y%m%d_%H%M%S)" || true
        git branch security-backup-$(date +%Y%m%d) || true
    fi
    
    log "✅ 代码已备份到: $BACKUP_DIR"
}

# 更新敏感文件权限
fix_file_permissions() {
    log "修复文件权限..."
    
    # 修复.env文件权限
    if [ -f .env ]; then
        chmod 600 .env
        info "设置.env权限为600"
    fi
    
    # 修复密钥文件权限
    if [ -d ~/.crypto_scout ]; then
        chmod 700 ~/.crypto_scout
        find ~/.crypto_scout -type f -exec chmod 600 {} \;
        info "修复密钥文件权限"
    fi
    
    # 修复日志文件权限
    if [ -d logs ]; then
        chmod 755 logs
        find logs -type f -exec chmod 644 {} \;
        info "修复日志文件权限"
    fi
    
    log "✅ 文件权限修复完成"
}

# 清理敏感数据
clean_sensitive_data() {
    log "清理敏感数据..."
    
    # 从代码中移除硬编码的密钥
    FILES_TO_CHECK=("fetch_data.py" "config.py" "settings.py")
    
    for file in "${FILES_TO_CHECK[@]}"; do
        if [ -f "$file" ]; then
            # 备份原文件
            cp "$file" "$file.bak"
            
            # 移除API密钥
            sed -i 's/api_key\s*=\s*"[^"]*"/api_key = os.getenv("API_KEY", "")/gi' "$file"
            sed -i 's/api_key\s*=\s*'"'"'[^'"'"']*'"'"'/api_key = os.getenv("API_KEY", "")/gi' "$file"
            
            # 移除密码
            sed -i 's/password\s*=\s*"[^"]*"/password = os.getenv("PASSWORD", "")/gi' "$file"
            sed -i 's/password\s*=\s*'"'"'[^'"'"']*'"'"'/password = os.getenv("PASSWORD", "")/gi' "$file"
            
            info "清理了 $file 中的敏感数据"
        fi
    done
    
    log "✅ 敏感数据清理完成"
}

# 生成安全密钥
generate_secure_keys() {
    log "生成安全密钥..."
    
    # 生成SECRET_KEY
    SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
    
    # 生成数据库密码
    DB_PASSWORD=$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')
    
    # 生成RabbitMQ密码
    RABBITMQ_PASSWORD=$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')
    
    # 创建或更新.env.secure文件
    cat > .env.secure <<EOF
# 安全配置文件 - 自动生成
# 生成时间: $(date)

# 核心密钥
SECRET_KEY=$SECRET_KEY

# 数据库
DB_USER=crypto_user
DB_PASSWORD=$DB_PASSWORD
DB_NAME=crypto_scout

# RabbitMQ
RABBITMQ_USER=admin
RABBITMQ_PASS=$RABBITMQ_PASSWORD

# Redis
REDIS_PASSWORD=$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')

# 请手动填写以下API密钥
TELEGRAM_BOT_TOKEN=
COINGECKO_API_KEY=
GITHUB_TOKEN=
EOF
    
    chmod 600 .env.secure
    
    log "✅ 安全密钥已生成并保存到 .env.secure"
    warning "请手动将API密钥从旧的.env文件复制到.env.secure"
}

# 安装安全依赖
install_security_dependencies() {
    log "安装安全依赖..."
    
    # 创建虚拟环境（如果不存在）
    if [ ! -d venv ]; then
        python3 -m venv venv
        info "创建虚拟环境"
    fi
    
    # 激活虚拟环境
    source venv/bin/activate
    
    # 升级pip
    pip install --upgrade pip
    
    # 安装安全依赖
    if [ -f requirements-security.txt ]; then
        pip install -r requirements-security.txt
        log "✅ 安全依赖安装完成"
    else
        warning "requirements-security.txt不存在，跳过安装"
    fi
    
    deactivate
}

# 应用代码补丁
apply_code_patches() {
    log "应用安全补丁..."
    
    # 替换不安全的文件
    if [ -f fetch_data_secure.py ]; then
        mv fetch_data.py fetch_data_old.py 2>/dev/null || true
        cp fetch_data_secure.py fetch_data.py
        info "应用了fetch_data.py的安全补丁"
    fi
    
    if [ -f dashboard_server_secure.py ]; then
        mv src/web/dashboard_server.py src/web/dashboard_server_old.py 2>/dev/null || true
        cp dashboard_server_secure.py src/web/dashboard_server.py
        info "应用了dashboard_server.py的安全补丁"
    fi
    
    # 运行Python安全补丁脚本
    if [ -f security_patches.py ]; then
        source venv/bin/activate
        python3 security_patches.py
        deactivate
        log "✅ Python安全补丁应用完成"
    fi
}

# 运行安全扫描
run_security_scan() {
    log "运行安全扫描..."
    
    source venv/bin/activate
    
    # Bandit扫描
    if command -v bandit &> /dev/null; then
        info "运行Bandit安全扫描..."
        bandit -r src/ -f json -o security_scan_bandit.json || true
        bandit -r src/ -ll
    fi
    
    # Safety检查
    if command -v safety &> /dev/null; then
        info "运行Safety依赖检查..."
        safety check --json > security_scan_safety.json || true
        safety check
    fi
    
    # Pylint检查
    if command -v pylint &> /dev/null; then
        info "运行Pylint代码质量检查..."
        pylint src/ --output-format=json > security_scan_pylint.json || true
    fi
    
    deactivate
    
    log "✅ 安全扫描完成，结果保存在security_scan_*.json文件中"
}

# 创建安全配置文件
create_security_configs() {
    log "创建安全配置文件..."
    
    # 创建.gitignore（如果不存在）
    if [ ! -f .gitignore ]; then
        cat > .gitignore <<EOF
# 环境变量和密钥
.env
.env.*
*.key
*.pem
*.cert

# 密钥和凭证
**/keys/
**/credentials/
~/.crypto_scout/

# 日志
*.log
logs/

# 备份
backups/
*.bak
*.backup

# Python
__pycache__/
*.pyc
venv/
.venv/

# IDE
.vscode/
.idea/
*.swp

# 测试和扫描结果
security_scan_*.json
.coverage
htmlcov/
EOF
        info "创建了.gitignore文件"
    fi
    
    # 创建.dockerignore
    if [ ! -f .dockerignore ]; then
        cat > .dockerignore <<EOF
.env
.env.*
*.key
*.pem
.git/
.github/
tests/
docs/
backups/
*.md
EOF
        info "创建了.dockerignore文件"
    fi
    
    log "✅ 安全配置文件创建完成"
}

# 显示安全建议
show_security_recommendations() {
    log "============================================"
    log "🔒 安全修复完成！"
    log "============================================"
    echo ""
    log "✅ 已完成的安全修复："
    echo "  - 备份了现有代码"
    echo "  - 修复了文件权限"
    echo "  - 清理了敏感数据"
    echo "  - 生成了安全密钥"
    echo "  - 安装了安全依赖"
    echo "  - 应用了代码补丁"
    echo "  - 运行了安全扫描"
    echo ""
    warning "⚠️ 需要手动完成的任务："
    echo "  1. 将API密钥从.env复制到.env.secure"
    echo "  2. 删除旧的.env文件：rm .env"
    echo "  3. 重命名.env.secure为.env：mv .env.secure .env"
    echo "  4. 更新所有密码和API密钥"
    echo "  5. 审查security_scan_*.json中的扫描结果"
    echo "  6. 重启所有服务"
    echo ""
    info "📚 安全最佳实践："
    echo "  - 定期更新依赖：pip install --upgrade -r requirements-security.txt"
    echo "  - 定期运行安全扫描：bandit -r src/"
    echo "  - 使用强密码和双因素认证"
    echo "  - 定期备份数据"
    echo "  - 监控异常活动"
    echo ""
    log "详细的安全报告请查看：SECURITY_AUDIT_REPORT.md"
    log "============================================"
}

# 主函数
main() {
    log "============================================"
    log "🔧 Crypto Alpha Scout 安全修复脚本"
    log "============================================"
    echo ""
    
    # 确认执行
    read -p "此脚本将修改您的代码和配置。是否继续？(y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        warning "用户取消操作"
        exit 1
    fi
    
    # 执行修复步骤
    check_requirements
    backup_code
    fix_file_permissions
    clean_sensitive_data
    generate_secure_keys
    install_security_dependencies
    apply_code_patches
    create_security_configs
    run_security_scan
    show_security_recommendations
}

# 处理参数
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  --help, -h     显示帮助信息"
    echo "  --scan-only    仅运行安全扫描"
    echo "  --backup-only  仅备份代码"
    echo "  --quick        快速修复（跳过扫描）"
    exit 0
fi

if [ "$1" = "--scan-only" ]; then
    check_requirements
    run_security_scan
    exit 0
fi

if [ "$1" = "--backup-only" ]; then
    backup_code
    exit 0
fi

if [ "$1" = "--quick" ]; then
    check_requirements
    backup_code
    fix_file_permissions
    clean_sensitive_data
    generate_secure_keys
    apply_code_patches
    show_security_recommendations
    exit 0
fi

# 运行主函数
main