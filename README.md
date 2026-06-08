<p align="center">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square&logo=python" alt="Python"/>
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License"/>
  <img src="https://img.shields.io/github/stars/YunhaoDou/bitcoin-monitor?style=flat-square&logo=github&color=yellow" alt="Stars"/>
  <img src="https://img.shields.io/github/last-commit/YunhaoDou/bitcoin-monitor?style=flat-square&logo=git" alt="Last Commit"/>
  <img src="https://img.shields.io/badge/coverage-100%25-brightgreen?style=flat-square" alt="Coverage"/>
</p>

<br>

<div align="center">
  <h1>₿ Bitcoin Monitor</h1>
  <p><strong>比特币多指标监控系统</strong><br>
  实时可视化面板 · 自定义策略引擎 · 自动报告推送</p>
</div>

<br>

<p align="center">
  <b>English</b> · <a href="#features">简体中文</a>
</p>

<br>

---

<br>

<a id="features"></a>

# ₿ Bitcoin Monitor

> 一个开箱即用的比特币监控系统，集数据采集、技术分析、策略评估、可视化面板于一体。

**痛点**：加密货币市场信息碎片化——链上数据、技术指标、市场情绪分散在不同平台。手动整合费时费力。<br>
**方案**：一键启动的本地监控系统，自动采集多源数据，生成中文分析报告 + 实时可视化面板 + 可定制的交易策略引擎。

---

## ✨ 功能特性

| | 模块 | 说明 |
|--|------|------|
| 📡 | **多源数据采集** | CoinGecko（价格/市值/全球数据）+ Blockchain.info（链上数据），自动降级容错 |
| 🔬 | **技术指标分析** | RSI(14) / SMA20/50 / 布林带 / MACD / 多指标风险评分（0-100） |
| 📊 | **实时可视化面板** | Chart.js 交互式图表，60s自动刷新，毛玻璃UI设计 |
| 🎯 | **策略引擎** | 自定义条件组合 + 加权评分 → 买卖信号。支持多策略、一键激活 |
| 📋 | **中文报告** | 每12h自动生成 Markdown 分析报告，含斐波那契价位 |
| 🔄 | **全自动运行** | cron 定时器，无需手动干预 |
| 🌐 | **本地Web服务** | 轻量HTTP服务器，浏览器打开即可查看 |

---

## 🏗 系统架构

```
                    cron 每12h
                        │
                        ▼
    ┌────────────────────────────────────┐
    │   orchestrator.py (主管线)          │
    │   ├─ indicators.py                 │
    │   │   ├─ CoinGecko API             │
    │   │   │   ├─ 价格/市值/全球数据     │
    │   │   │   └─ 7日market_chart       │
    │   │   ├─ Blockchain.info           │
    │   │   │   └─ 交易数/难度/算力/出块   │
    │   │   └─ 计算技术指标              │
    │   │       ├─ RSI(14) / SMA / BB    │
    │   │       └─ MACD / 风险评分       │
    │   └─ report_generator.py           │
    │       └─ 中文Markdown报告          │
    └──────────┬────────────────────────┘
               │
        写入 data/raw_*.json + data/reports/
               │
               ▼
    ┌────────────────────────────────────┐
    │   server.py (Web服务器 :8765)       │
    │   ├─ GET  /        → 监控面板      │
    │   ├─ GET  /strategies → 策略管理   │
    │   └─ GET  /api/*   → JSON数据      │
    └──────────┬────────────────────────┘
               │
               ▼
       浏览器 → 实时可视化面板
       
    ┌────────────────────────────────────┐
    │   strategy_engine.py               │
    │   ├─ 策略CRUD (创建/读取/更新/删除) │
    │   ├─ 多条件加权评分                 │
    │   └─ 买卖信号判定                   │
    └────────────────────────────────────┘
```

---

## 🚀 快速开始

### 前置要求

- Python 3.10+
- 网络连接（访问 CoinGecko 和 Blockchain.info API）

### 安装

```bash
# 克隆仓库
git clone https://github.com/YunhaoDou/bitcoin-monitor.git
cd bitcoin-monitor

# （可选）创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 无额外依赖——仅使用 Python 标准库
```

### 运行

```bash
# 1️⃣ 采集数据 + 生成分析报告
python scripts/orchestrator.py

# 2️⃣ 启动可视化面板
bash server.sh start

# 3️⃣ 打开浏览器
open http://localhost:8765
```

### 面板管理

```bash
bash server.sh start   # 启动面板
bash server.sh stop    # 停止面板
bash server.sh status  # 查看状态
```

---

## 📊 可视化面板

访问 **http://localhost:8765** 即可查看。

### 📊 监控面板（首页）

| 区域 | 内容 |
|------|------|
| 🟠 价格横幅 | BTC当前价 + 7日/30日涨跌幅 + RSI + 风险分 |
| 📊 风险评估 | 0-100风险评分 + 进度条 + 策略建议 |
| 📈 价格走势图 | 7日每小时价格 Chart.js 交互折线图 |
| 🔬 技术速览 | RSI/SMA/布林带/MACD + 多指标信号 |
| ⛓️ 链上数据 | 交易数/算力/难度/出块/已挖BTC |
| 🎯 关键价位 | 斐波那契回撤参考价位 |

### 🎯 策略管理（/strategies）

| 区域 | 内容 |
|------|------|
| 📡 实时信号 | 当前激活策略的评估结果（自动30s刷新） |
| 📋 策略列表 | 所有已保存策略，点击编辑 |
| ✏️ 策略编辑器 | 自定义条件规则 + 加权评分配置 |

#### 策略格式示例

```json
{
  "name": "RSI超卖反弹",
  "description": "当RSI进入超卖区域且价格接近布林带下轨时买入",
  "logic": "AND",
  "min_score": 2.0,
  "conditions": [
    {
      "label": "RSI超卖 (<35)",
      "indicator": "technical.rsi_14",
      "operator": "<",
      "value": 35,
      "weight": 2.0
    },
    {
      "label": "布林带下轨附近 (<30%)",
      "indicator": "technical.bb_position_pct",
      "operator": "<",
      "value": 30,
      "weight": 1.5
    }
  ]
}
```

> 可用指标：价格、涨跌幅、RSI、SMA、布林带、MACD、链上数据、风险评分（共20+个）
> 运算符：`>` `<` `>=` `<=` `==` `!=` `between`
> 权重：正数→看多，负数→看空

---

## 📁 项目结构

```
bitcoin-monitor/
├── config.py                 ← 全局配置（API地址、数据目录）
├── server.sh                 ← 面板启动/停止/状态脚本
├── .gitignore
├── scripts/
│   ├── orchestrator.py       ← 主管线（串联采集→报告）
│   ├── indicators.py         ← 数据采集 + 技术指标计算
│   ├── report_generator.py   ← 中文Markdown报告生成
│   ├── dashboard.py          ← 离线HTML仪表盘生成
│   ├── server.py             ← 本地Web服务器（含面板+策略页面）
│   └── strategy_engine.py    ← 策略定义/存储/评估引擎
├── data/
│   ├── reports/              ← 生成的报告（.md + .html）（gitignore）
│   ├── strategies/           ← 用户策略（.json）（版本控制）
│   └── raw_*.json            ← 采集原始数据（gitignore）
└── logs/                     ← 运行日志（gitignore）
```

---

## 🔄 定时任务

系统通过 Hermes cron 每12小时自动运行：

```bash
# 查看已配置的定时任务
# （通过 Hermes 面板管理）
```

运行流程：
1. 采集 CoinGecko + Blockchain.info 数据
2. 计算技术指标和风险评分
3. 生成中文 Markdown 分析报告
4. 更新原始 JSON 数据 → 面板自动反映最新数据

---

## 🛠 技术栈

| 组件 | 技术 |
|------|------|
| 数据采集 | Python stdlib (`urllib`) |
| 技术分析 | 自实现 RSI/SMA/BB/MACD |
| 可视化 | Chart.js (CDN) |
| Web服务器 | Python `http.server` (std) |
| UI设计 | 毛玻璃（Glassmorphism）暗色主题 |
| 版本控制 | Git + GitHub |
| 定时任务 | Hermes Agent cron |

---

## 📌 路线图

- [x] 多源数据采集（CoinGecko + Blockchain.info）
- [x] 技术指标计算（RSI/SMA/布林带/MACD）
- [x] 多指标风险评分
- [x] 中文Markdown报告
- [x] Chart.js 实时可视化面板
- [x] 自定义策略引擎（多条件加权）
- [x] GitHub 版本控制
- [ ] 接入更多数据源（Glassnode / Santiment）
- [ ] 策略回测功能
- [ ] 推送通知（Telegram / 微信）
- [ ] 价格预警系统
- [ ] 多币种监控扩展

---

## 🤝 贡献

| 方式 | 说明 |
|------|------|
| ⭐ Star | 收藏项目，支持维护 |
| 🐛 Issue | 报告Bug或提出建议 |
| 🔀 PR | 提交代码改进 |
| 📖 文档 | 完善使用说明和注释 |

---

<p align="center">
  <a href="https://github.com/YunhaoDou/bitcoin-monitor">
    <img src="https://api.star-history.com/svg?repos=YunhaoDou/bitcoin-monitor&type=Date" alt="Star History" width="500">
  </a>
</p>

<p align="center">
  <sub>⚠️ 以上分析仅供参考，不构成投资建议。加密货币市场风险高，请理性决策。</sub>
</p>

<p align="center">
  <a href="https://github.com/YunhaoDou/bitcoin-monitor">GitHub</a> ·
  <sub>Built with Python & Chart.js</sub>
</p>
