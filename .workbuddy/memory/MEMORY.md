# MEMORY.md - 长期记忆

## 用户背景
- 价值投资者，专注A股分析
- 关注合力泰（002217）等股票
- 关注AI和金融科技政策动态

## 重要项目

### 红利低波ETF定投看板 V2（四维联动版）
- 文件：`E:\WorkBuddy\dividend_etf_dashboard\dividend_etf_dashboard.html`
- 部署地址：http://127.0.0.1:7892/dividend_etf_dashboard.html
- 目标ETF：512890（华泰柏瑞中证红利低波动ETF），跟踪指数H30269
- V2升级（2026-04-30）：四维联动判断阈值体系
  - 维度1：6级股债利差阈值（极度低估→严重高估）
  - 维度2：5级历史分位阈值（90%+→0-20%）
  - 维度3：5级TTM股息率独立阈值（≥4.80%→<3.20%）
  - 维度4：PE/PB估值双指标阈值
  - 一体化买卖执行清单（买入/加仓/重仓/减仓/清仓）
- 数据来源：primary=neodata-financial-search；backup=腾讯行情API(sh512890) + 昨日国债数据
- 飞书Webhook：https://open.feishu.cn/open-apis/bot/v2/hook/d27f80b4-39ac-4cda-9a17-28cc79109a5d
- 注意：指数股息率(H30269 ~4.32%) ≠ 基金TTM分红率(512890 ~10.2%)，看板使用指数级别
- 自动更新：update_dashboard.py（2026-05-07创建）
  - 每交易日10:00自动运行（automation ID: automation-1778155809666）
  - primary: neodata-financial-search（copilot.tencent.com端点，12h token有效期）
  - backup: 腾讯行情API(https://qt.gtimg.cn/q=sh512890) + 中债国债昨日数据
  - 估算：指数股息率（基于ETF价格变动反推）、历史分位（分段线性映射）
  - PE/PB：neodata无此结构化数据，保留原值，需手动从理杏仁更新

### 合力泰价值投资分析
- 文件：合力泰002217_价值投资分析报告.html
- 评级：回避（2026-04-22分析）

## 踩坑记录
- finance-data-retrieval 的 https://www.codebuddy.cn/v2/tool/financedata 接口需要独立token，neodata token无效（40101错误）
- neodata token失效问题（2026-05-14）：connect_cloud_service给的token的audience是"account"，不适用于copilot.tencent.com（需要audience"copilot"）。临时解决：使用腾讯行情API获取ETF价格（https://qt.gtimg.cn/q=sh512890），国债沿用昨日数据
- 解决：使用 neodata-financial-search skill 的 query.py 脚本（需正确token）或腾讯API备用方案
- update_dashboard.py旧路径硬编码问题：原路径`C:\...\20260422192838\`已迁移，应使用`Path(__file__).parent`相对路径（2026-05-14已修复）

