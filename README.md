# 股票交易与回测系统

一个基于Python的股票交易与回测系统，支持A股数据获取、策略回测和模拟交易。

## 功能特点

### 回测系统
- 支持从Tushare获取A股日线数据
- 提供多种技术指标策略（双均线、布林带、RSI）
- 完整的回测引擎，支持交易成本和滑点模拟
- 详细的回测报告和可视化

### 交易系统
- 模拟交易接口
- 风险管理和仓位控制
- 交易记录和持仓管理
- 实时监控和日志记录

## 项目结构

```
StockDev/
├── src/                    # 源代码目录
│   ├── common/            # 公共模块
│   ├── data/              # 数据获取和处理
│   ├── backtesting/       # 回测系统
│   └── trading/           # 交易系统
├── config/                # 配置文件
├── data/                  # 数据存储
├── logs/                  # 日志文件
├── tests/                 # 测试文件
├── notebooks/             # Jupyter笔记本
├── requirements.txt       # 依赖包列表
├── .env.example          # 环境变量示例
└── main.py               # 主程序入口
```

## 快速开始

### 1. 安装依赖

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows
.\venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

复制环境变量示例文件并填入实际值：

```bash
cp .env.example .env
```

编辑`.env`文件，填入你的Tushare Token等信息。

### 3. 运行系统

```bash
# 启动系统
python main.py

# 运行回测
python -m src.backtesting

# 运行交易系统
python -m src.trading
```

### 4. 运行测试

```bash
python -m pytest tests/
```

## 配置说明

主要配置文件位于`config/config.yaml`，包含以下配置项：

- 数据源配置
- 数据库配置
- 回测参数
- 交易参数
- 风控参数
- 日志配置

## 策略开发

系统支持自定义策略开发，只需继承基础策略类并实现`on_bar`方法：

```python
from src.backtesting.strategies import Strategy

class MyStrategy(Strategy):
    def on_bar(self, bar_data):
        # 实现你的策略逻辑
        pass
```

## 注意事项

1. 本系统仅用于学习和研究，不构成投资建议
2. 实盘交易前请充分测试策略
3. 使用模拟账户进行测试，避免真实资金损失

## 许可证

MIT License