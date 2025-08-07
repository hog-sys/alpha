# Crypto Alpha Scout 🚀

一个高性能的加密货币机会扫描系统，集成了机器学习预测、实时数据分析和智能通知功能。

## ✨ 主要特性

- 🔍 **智能机会扫描**: 实时监控市场数据，识别交易机会
- 🤖 **机器学习预测**: 使用先进的ML模型预测价格走势和机会质量
- 📊 **技术指标分析**: 集成RSI、MACD、布林带等技术指标
- 📈 **实时数据收集**: 从多个交易所获取实时市场数据
- 📱 **Telegram通知**: 实时推送机会提醒到Telegram
- 🌐 **Web仪表板**: 提供直观的Web界面查看系统状态
- ⚡ **高性能架构**: 异步处理，支持高并发数据流

## 🏗️ 系统架构

```
Crypto Alpha Scout/
├── config/                 # 配置管理
├── src/
│   ├── core/              # 核心模块
│   ├── analysis/          # 数据分析
│   ├── scouts/            # 扫描器
│   ├── telegram/          # Telegram机器人
│   └── web/              # Web服务
├── data/                  # 数据存储
├── ml_models/            # 机器学习模型
├── logs/                 # 日志文件
└── scripts/              # 工具脚本
```

## 🚀 快速开始

### 1. 环境要求

- Python 3.8+
- Redis服务器
- Telegram Bot Token

### 2. 安装依赖

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
# 复制环境变量模板
cp env.example .env

# 编辑配置文件
# 设置你的Telegram Bot Token和其他配置
```

### 4. 启动系统

```bash
# 使用启动脚本
python scripts/start.py

# 或直接运行
python main.py
```

## 📋 配置说明

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `TELEGRAM_TOKEN` | Telegram Bot Token | 必需 |
| `TELEGRAM_CHAT_ID` | Telegram聊天ID | 必需 |
| `REDIS_URL` | Redis连接URL | `redis://localhost:6379` |
| `DATABASE_URL` | 数据库连接URL | `sqlite:///data/crypto_scout.db` |
| `HOST` | Web服务主机 | `0.0.0.0` |
| `PORT` | Web服务端口 | `8080` |

### 机器学习配置

系统支持以下ML模型：

- **机会分类器**: 评估交易机会的质量
- **价格预测器**: 预测短期价格走势
- **异常检测器**: 识别异常市场行为

## 🔧 功能模块

### 数据收集器 (`src/analysis/data_collector.py`)

- 从Binance API获取实时市场数据
- 计算技术指标（RSI、MACD、布林带等）
- 分析订单簿和交易数据
- 支持多种时间框架的数据收集

### 机器学习预测器 (`src/analysis/ml_predictor.py`)

- 使用随机森林和梯度提升算法
- 自动特征工程和模型训练
- 定期重训练以保持模型准确性
- 支持异常检测和置信度评估

### 扫描管理器 (`src/core/scout_manager.py`)

- 管理多个扫描器实例
- 协调数据收集和分析流程
- 处理机会检测和过滤
- 支持可扩展的扫描器架构

## 📊 监控和日志

系统提供详细的日志记录：

- 应用日志: `logs/crypto_scout_YYYYMMDD.log`
- 错误追踪和性能监控
- 实时系统状态报告

## 🔒 安全特性

- 环境变量配置敏感信息
- API请求频率限制
- 异常处理和错误恢复
- 数据验证和清理

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 📞 支持

如果你遇到问题或有建议，请：

1. 查看 [Issues](../../issues) 页面
2. 创建新的 Issue
3. 联系项目维护者

---

**注意**: 这是一个教育项目，不构成投资建议。加密货币交易存在风险，请谨慎投资。 
=======
# scout
