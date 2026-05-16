# 📊 红利低波ETF 四维联动定投看板

> 基于股债利差 + 估值双指标四维联动的 A股红利低波动ETF(512890) 定投决策看板，数据自动更新，部署于 GitHub Pages。

**在线访问：** https://moregun.github.io/dividend-etf-dashboard/

---

## ✨ 功能特性

### 🎯 四维联动判断体系

| 维度 | 指标 | 阈值体系 |
|------|------|----------|
| ① 股债利差 | 指数股息率 − 10年国债收益率 | 6级（极度低估 → 严重高估） |
| ② 利差历史分位 | 近10年分位数 | 5级（极低估 → 高估） |
| ③ TTM股息率 | 指数股息率独立参考 | 5级（顶级性价比 → 优势消失） |
| ④ PE / PB | 指数端估值双指标 | 各4级阈值 |

### 📋 一体化买卖执行清单

- ✅ **买入条件**：满足2项以上触发
- 🚀 **加仓/重仓条件**：利差≥2.5% 或 分位≥85%
- ❌ **减仓/清仓条件**：利差<1.2% 或 分位<30%

### 📈 可视化图表

- 股债利差历史走势（含6级阈值色带标注）
- 利差分位仪表盘
- ETF近一年价格走势
- 历史分红记录表

---

## 🔧 技术架构

```
本地/CI 数据更新
      │
      ▼
update_dashboard.py  ──→  dividend_etf_dashboard.html
      │                        │
      │                        ▼
      ▼                   GitHub Pages（静态部署）
GitHub Actions
定时运行（每工作日10:00）
```

### 文件结构

```
├── .github/
│   └── workflows/
│       ├── update-dashboard.yml   # 定时更新数据 + 推送
│       └── deploy-pages.yml      # GitHub Pages 部署
├── dividend_etf_dashboard.html   # 主看板页面
├── index.html                    # 根路径跳转页
├── update_dashboard.py           # 数据更新脚本
└── README.md
```

---

## 🚀 部署指南

### 1. Fork / Clone 本仓库

```bash
git clone https://github.com/moregun/dividend-etf-dashboard.git
cd dividend-etf-dashboard
```

### 2. 配置 GitHub Secrets

进入仓库 **Settings → Secrets and variables → Actions**，添加以下 Secret：

| Secret 名称 | 说明 | 示例值 |
|-------------|------|---------|
| `FEISHU_WEBHOOK` | 飞书自定义机器人 Webhook 后缀 | `d27f80b4-39ac-4cda-9a17-28cc7910****` |
| `NOTIFY_THRESHOLD` | 触发飞书通知的利差阈值（可选，默认2.5） | `2.5` |

> 飞书 Webhook 完整地址格式：`https://open.feishu.cn/open-apis/bot/v2/hook/{你的Webhook后缀}`

### 3. 启用 GitHub Pages

进入仓库 **Settings → Pages**：
- Source 选择 **GitHub Actions**
- 保存后等待部署完成

### 4. 手动触发首次运行（可选）

进入 **Actions → Update Dividend ETF Dashboard → Run workflow**

---

## 📡 数据来源

| 数据项 | 来源 | 更新频率 |
|--------|------|----------|
| ETF价格/净值 | 腾讯财经 API (`qt.gtimg.cn/q=sh512890`) | 每工作日 |
| 10年国债收益率 | 中国债券信息网（公开页面解析） | 每工作日 |
| 指数PE/PB | 理杏仁（需手动更新） | 手动 |
| 历史分红 | 华泰柏瑞基金官网 | 静态 |

> **注意**：PE/PB 数据目前为静态值，需定期手动从理杏仁等平台更新 `update_dashboard.py` 中的对应变量。

---

## 🔔 飞书通知

当股债利差 ≥ 设定阈值时，GitHub Actions 自动推送飞书消息：

```
【深度低估信号】红利低波ETF

时间：2026-05-16 15:00
股债利差：2.64%（深度低估）
利差分位：84%
指数股息率：4.39%
PE-TTM：8.32倍
PB：1.12

操作建议：分批加仓

⚠️ 仅供参考，不构成投资建议
```

---

## 🛠️ 本地开发

### 前置依赖

```bash
pip install requests
```

### 本地运行数据更新

```bash
export FEISHU_WEBHOOK="d27f80b4-39ac-4cda-9a17-28cc79109a5d"
export NOTIFY_THRESHOLD="2.5"
python update_dashboard.py
```

### 本地预览页面

```bash
# Python 简易服务器
python -m http.server 8080
# 访问 http://localhost:8080/dividend_etf_dashboard.html
```

---

## 📅 GitHub Actions 定时任务

| 工作流 | 触发条件 | 说明 |
|--------|---------|------|
| `update-dashboard.yml` | 每工作日 10:00 (Asia/Shanghai) + 手动触发 | 抓取最新数据，更新HTML，自动commit+push |
| `deploy-pages.yml` | 每次 push 到 main 分支 | 部署到 GitHub Pages |

**定时 Cron 表达式：** `0 10 * * 1-5` （北京时间工作日10:00）

---

## ⚠️ 免责声明

本看板仅供学习和参考，不构成任何投资建议。投资有风险，入市须谨慎。

---

## 📄 License

MIT License
