#!/usr/bin/env python3
"""
红利低波ETF定投看板 - 每日数据自动更新脚本（GitHub Actions 云端版）

数据来源（完全公开，无需 token）：
  1. ETF价格/净值: 腾讯财经API (qt.gtimg.cn)
  2. 10年国债收益率: investing.com / tradingeconomics.com 页面爬取
  3. PE/PB: 从现有HTML保留（公开源不稳定，暂用估算）
  4. 股息率: 基于ETF价格反推

用法：
  python update_dashboard.py [--feishu-webhook URL] [--notify] [--threshold X.X]

GitHub Actions 环境变量:
  FEISHU_WEBHOOK - 飞书机器人Webhook地址
  NOTIFY_THRESHOLD - 触发通知的利差阈值（默认2.5）
"""

import json
import os
import re
import sys
import urllib.request
import time
from datetime import datetime, date
from pathlib import Path

# ============================================================
#  配置
# ============================================================
DASHBOARD_HTML = Path(__file__).parent / "dividend_etf_dashboard.html"


# ============================================================
#  通用工具
# ============================================================

def fetch_url(url: str, timeout: int = 15) -> str:
    """通用URL获取，自动处理编码，返回文本内容"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read()
            for enc in ("utf-8", "gbk", "gb2312", "iso-8859-1"):
                try:
                    return content.decode(enc)
                except UnicodeDecodeError:
                    continue
            return content.decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [WARN] 获取失败 {url[:60]}: {e}", file=sys.stderr)
        return ""


# ============================================================
#  数据获取（完全公开数据源，无需 token）
# ============================================================

def fetch_etf_512890() -> tuple:
    """获取512890 ETF最新价格和净值
    数据源: 腾讯财经API（公开，无需认证）
    返回: (价格float, 净值float) 或 (None, None)
    """
    print("[1/4] 获取512890 ETF数据（腾讯API）...")
    url = "https://qt.gtimg.cn/q=sh512890"
    content = fetch_url(url)
    if not content:
        return None, None
    try:
        # 返回格式: v_sh512890="51~红利低波ETF华泰柏瑞~512890~1.167~-0.008~-0.68%~..."
        match = re.search(r'v_sh512890="([^"]+)"', content)
        if not match:
            print("  [WARN] 腾讯API返回格式异常", file=sys.stderr)
            return None, None
        fields = match.group(1).split("~")
        # 字段: 0=市场,1=名字,2=代码,3=价格,4=涨跌,5=涨跌幅,6=...
        price_str = fields[3] if len(fields) > 3 else ""
        if price_str and float(price_str) > 0:
            price = float(price_str)
            nav = price  # ETF价格≈净值（简化处理）
            print(f"  512890: 价格={price}, 净值≈{nav}")
            return price, nav
    except Exception as e:
        print(f"  [WARN] 解析ETF数据失败: {e}", file=sys.stderr)
    return None, None


def fetch_bond_yield_10y() -> float:
    """获取10年国债收益率
    数据源: investing.com（公开页面，闭盘数据可直接获取）
    返回: 收益率 float (%) 或 None
    """
    print("[2/4] 获取10年国债收益率...")
    sources = [
        ("https://cn.investing.com/rates-bonds/china-10-year-bond-yield", _parse_investing),
        ("https://zh.tradingeconomics.com/china/government-bond-yield", _parse_tradingeconomics),
    ]
    for url, parser in sources:
        content = fetch_url(url)
        if content:
            result = parser(content)
            if result is not None:
                print(f"  10年国债收益率: {result:.4f}% (来源: {url.split('/')[2]})")
                return result
        time.sleep(1)  # 避免被封

    print("  [WARN] 所有数据源均失败", file=sys.stderr)
    return None


def _parse_investing(content: str) -> float:
    """解析 investing.com 中国10年国债收益率页面"""
    try:
        # 方法1: 查找 data-test="instrument-price-last" 后的数值
        m = re.search(r'data-test="instrument-price-last">\s*([\d.]+)\s*<', content)
        if m:
            val = float(m.group(1))
            if 0.3 < val < 6.0:
                return val

        # 方法2: 查找 "中国10年期国债（代码：CN10YT=RR）最新收益率：1.750%"
        m2 = re.search(r'收益率\s*[：:]\s*([\d.]+)\s*%', content)
        if m2:
            val = float(m2.group(1))
            if 0.3 < val < 6.0:
                return val

        # 方法3: 查找页面中任意合理的收益率数字（出现在债券相关上下文中）
        for m3 in re.finditer(r'([\d.]{4,5})', content):
            val = float(m3.group(1))
            if 0.5 < val < 5.0:
                # 检查附近是否有"国债"或"收益率"关键词
                context = content[max(0, m3.start()-50):min(len(content), m3.end()+50)]
                if "国债" in context or "收益率" in context or "bond" in context.lower():
                    return val
    except Exception as e:
        print(f"  [WARN] investing.com解析失败: {e}", file=sys.stderr)
    return None


def _parse_tradingeconomics(content: str) -> float:
    """解析 tradingeconomics.com 中国国债收益率页面"""
    try:
        # 查找 "China 10Y ... 1.75" 格式
        m = re.search(r'China\s+10Y[^0-9]*?([\d.]+)\s*[-+]', content)
        if m:
            val = float(m.group(1))
            if 0.3 < val < 6.0:
                return val
    except Exception as e:
        print(f"  [WARN] tradingeconomics解析失败: {e}", file=sys.stderr)
    return None


def fetch_index_valuation() -> tuple:
    """获取指数估值（PE/PB/股息率）
    数据源: 从现有HTML保留原值（公开源不稳定）
    返回: (pe, pb, div_yield) 部分可能为None
    """
    print("[3/4] 获取中证红利低波动指数估值数据...")
    # 公开API不稳定，暂不实现自动获取
    # PE/PB 保留HTML中的原值，用户可手动从理杏仁更新
    print("  [INFO] PE/PB保留原值（请从理杏仁手动更新）")
    return None, None, None


def estimate_index_div_yield(etf_price: float, prev_price: float = 1.187, prev_div: float = 4.32) -> float:
    """基于ETF价格变化估算指数股息率
    逻辑: 股息率 ≈ 前期股息率 × (前期价格 / 当前价格)
    """
    if not etf_price or etf_price <= 0:
        return prev_div
    ratio = prev_price / etf_price
    estimated = round(prev_div * ratio, 2)
    return max(0.01, min(10.0, estimated))


# ============================================================
#  HTML 更新
# ============================================================

def read_current_snap() -> dict:
    """从HTML文件中读取当前SNAP数据"""
    if not DASHBOARD_HTML.exists():
        return {}
    html = DASHBOARD_HTML.read_text(encoding="utf-8")
    snap = {}
    # 匹配 const SNAP = {...};  保留注释
    pattern = r'const SNAP = \{([^}]+)\};'
    match = re.search(pattern, html, re.DOTALL)
    if not match:
        return {}
    for line in match.group(1).split('\n'):
        line = line.strip()
        if not line or line.startswith('//'):
            continue
        kv = re.match(r'(\w+):\s*([\d.]+|"[^"]*")', line)
        if kv:
            key = kv.group(1)
            val = kv.group(2).strip().rstrip(',')
            if val.startswith('"'):
                snap[key] = val.strip('"')
            else:
                snap[key] = float(val) if '.' in val else int(val)
    return snap


def update_dashboard_html(snap_data: dict) -> bool:
    """更新HTML看板中的SNAP对象，保留注释格式"""
    print("[4/4] 更新看板HTML...")
    if not DASHBOARD_HTML.exists():
        print(f"  [ERROR] 看板文件不存在: {DASHBOARD_HTML}", file=sys.stderr)
        return False

    html = DASHBOARD_HTML.read_text(encoding="utf-8")

    new_snap = f"""const SNAP = {{
  indexDivYield: {snap_data['indexDivYield']},      // 中证红利低波指数TTM股息率 %
  bondYield10Y:  {snap_data['bondYield10Y']},      // 10年国债收益率 %
  spread:        {snap_data['spread']},      // 股债利差 pp
  percentile:    {snap_data['percentile']},        // 近10年利差历史分位（估算）
  pe:            {snap_data['pe']},      // 指数PE-TTM
  pb:            {snap_data['pb']},      // 指数PB
  etfPrice:      {snap_data['etfPrice']},     // 512890 最新价
  etfNav:        {snap_data['etfNav']},    // 512890 最新净值
  updateDate:    '{snap_data['updateDate']}'
}};"""

    pattern = r"const SNAP = \{[^}]+};"
    new_html = re.sub(pattern, new_snap, html, count=1, flags=re.DOTALL)

    if new_html == html:
        print("  [WARN] SNAP对象未找到或未变化", file=sys.stderr)
        return False

    DASHBOARD_HTML.write_text(new_html, encoding="utf-8")
    print(f"  看板已更新: {snap_data['updateDate']}")
    print(f"  利差={snap_data['spread']:.2f}%, 分位={snap_data['percentile']}%, 股息率={snap_data['indexDivYield']:.2f}%")
    return True


# ============================================================
#  阈值检测 & 通知
# ============================================================

def check_thresholds(snap: dict) -> list:
    """检查四维阈值，返回触发的信号列表"""
    alerts = []
    spread = snap['spread']
    div_yield = snap['indexDivYield']
    pe = snap['pe']
    pb = snap['pb']

    # 维度1：股债利差 6级
    if spread >= 3.00:
        alerts.append(f"🔴 利差{spread:.2f}%≥3.00% → 极度低估，重仓布局！")
    elif spread >= 2.50:
        alerts.append(f"🟢 利差{spread:.2f}%≥2.50% → 深度低估，分批加仓")
    elif spread >= 2.00:
        alerts.append(f"🟢 利差{spread:.2f}%≥2.00% → 合理偏低，定投为主")
    elif spread < 0.50:
        alerts.append(f"🔴 利差{spread:.2f}%<0.50% → 严重高估，清仓/大幅减仓！")
    elif spread < 1.20:
        alerts.append(f"🟠 利差{spread:.2f}%<1.20% → 偏贵区间，停止买入/减仓")

    # 维度3：股息率
    if div_yield >= 4.80:
        alerts.append(f"🔴 股息率{div_yield:.2f}%≥4.80% → 顶级性价比，强买入信号！")
    elif div_yield >= 4.30:
        alerts.append(f"🟢 股息率{div_yield:.2f}%≥4.30% → 优质区间，适合长期配置")
    elif div_yield < 3.20:
        alerts.append(f"🔴 股息率{div_yield:.2f}%<3.20% → 优势消失，规避！")

    # 维度4：PE/PB
    if pe < 9.5:
        alerts.append(f"🟢 PE={pe:.1f}<9.5 → 低估，加仓加持")
    elif pe >= 13.0:
        alerts.append(f"🔴 PE={pe:.1f}≥13.0 → 高估，减仓离场")
    if pb < 1.40:
        alerts.append(f"🟢 PB={pb:.2f}<1.40 → 深度低估，重仓")
    elif pb >= 1.80:
        alerts.append(f"🔴 PB={pb:.2f}≥1.80 → 高估泡沫，减仓")

    return alerts


def send_feishu_notification(webhook: str, content: str) -> bool:
    """通过飞书Webhook发送通知"""
    if not webhook:
        return False
    try:
        data = json.dumps({
            "msg_type": "text",
            "content": {"text": content}
        }).encode("utf-8")
        req = urllib.request.Request(webhook, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if result.get("code") == 0:
                print("  飞书通知已发送 ✓")
                return True
            else:
                print(f"  [WARN] 飞书返回错误: {result}", file=sys.stderr)
    except Exception as e:
        print(f"  [WARN] 飞书通知发送失败: {e}", file=sys.stderr)
    return False


# ============================================================
#  主流程
# ============================================================

def main():
    print(f"{'='*60}")
    print(f"红利低波ETF看板 - 数据更新  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")

    # 从环境变量或命令行读取配置
    feishu_webhook = os.environ.get("FEISHU_WEBHOOK", "")
    notify_threshold = float(os.environ.get("NOTIFY_THRESHOLD", "2.5"))

    # 解析命令行参数（覆盖环境变量）
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--feishu-webhook" and i + 1 < len(sys.argv):
            feishu_webhook = sys.argv[i + 1]
            i += 2
        elif arg == "--notify":
            i += 1  # 通知总是开启（如果有webhook）
        elif arg == "--threshold" and i + 1 < len(sys.argv):
            try:
                notify_threshold = float(sys.argv[i + 1])
            except ValueError:
                pass
            i += 2
        else:
            i += 1

    # 读取现有SNAP数据作为默认值
    existing_snap = read_current_snap()
    if not existing_snap:
        # 默认值（首次运行）
        existing_snap = {
            'indexDivYield': 4.32,
            'bondYield10Y': 1.76,
            'spread': 2.56,
            'percentile': 80,
            'pe': 8.3,
            'pb': 1.12,
            'etfPrice': 1.187,
            'etfNav': 1.1967,
            'updateDate': '2026-04-30'
        }

    # 1. 获取512890 ETF价格/净值
    etf_price, etf_nav = fetch_etf_512890()
    if etf_price is not None:
        existing_snap['etfPrice'] = etf_price
        print(f"  ✓ ETF价格更新: {etf_price}")
    else:
        print("  ✗ ETF价格获取失败，保留原值")

    if etf_nav is not None:
        existing_snap['etfNav'] = etf_nav
        print(f"  ✓ ETF净值更新: {etf_nav}")
    else:
        print("  ✗ ETF净值获取失败，保留原值")

    # 2. 获取10年国债收益率
    bond_yield = fetch_bond_yield_10y()
    if bond_yield is not None:
        existing_snap['bondYield10Y'] = round(bond_yield, 2)
        print(f"  ✓ 国债收益率更新: {bond_yield:.4f}%")
    else:
        print("  ✗ 国债收益率获取失败，保留原值")

    # 3. 获取指数估值（PE/PB/股息率）
    idx_pe, idx_pb, idx_div = fetch_index_valuation()
    if idx_pe is not None:
        existing_snap['pe'] = idx_pe
    if idx_pb is not None:
        existing_snap['pb'] = idx_pb
    if idx_div is not None:
        existing_snap['indexDivYield'] = idx_div
    else:
        # 估算股息率：基于ETF价格变动反推
        if etf_price is not None:
            estimated_div = estimate_index_div_yield(etf_price)
            existing_snap['indexDivYield'] = estimated_div
            print(f"  ℹ 指数股息率估算: {estimated_div:.2f}% (基于ETF价格变化)")

    # 4. 计算股债利差
    existing_snap['spread'] = round(existing_snap['indexDivYield'] - existing_snap['bondYield10Y'], 2)

    # 5. 估算历史分位（分段线性映射）
    spread = existing_snap['spread']
    if spread >= 3.0:
        existing_snap['percentile'] = 95
    elif spread >= 2.5:
        existing_snap['percentile'] = int(80 + (spread - 2.5) / 0.5 * 15)
    elif spread >= 2.0:
        existing_snap['percentile'] = int(50 + (spread - 2.0) / 0.5 * 30)
    elif spread >= 1.2:
        existing_snap['percentile'] = int(20 + (spread - 1.2) / 0.8 * 30)
    elif spread >= 0.5:
        existing_snap['percentile'] = int(5 + (spread - 0.5) / 0.7 * 15)
    else:
        existing_snap['percentile'] = max(0, int(spread / 0.5 * 5))

    # 6. 更新日期
    today = date.today()
    existing_snap['updateDate'] = today.strftime('%Y-%m-%d')

    # 7. 写入HTML
    success = update_dashboard_html(existing_snap)

    if success:
        print(f"\n{'='*60}")
        print("更新结果:")
        print(f"  股息率: {existing_snap['indexDivYield']:.2f}%")
        print(f"  国债10Y: {existing_snap['bondYield10Y']:.2f}%")
        print(f"  股债利差: {existing_snap['spread']:.2f}%")
        print(f"  历史分位: {existing_snap['percentile']}%")
        print(f"  PE: {existing_snap['pe']:.1f}  PB: {existing_snap['pb']:.2f}")
        print(f"  ETF价格: {existing_snap['etfPrice']:.3f}  净值: {existing_snap['etfNav']:.4f}")

        # 8. 阈值检查
        alerts = check_thresholds(existing_snap)
        if alerts:
            print(f"\n⚠️ 触发信号:")
            for a in alerts:
                print(f"  {a}")
        else:
            print(f"\n📊 当前处于合理区间，无极端信号")

        # 9. 飞书通知
        spread = existing_snap['spread']
        if feishu_webhook and spread >= notify_threshold:
            alerts = check_thresholds(existing_snap)
            print(f"\n⚡ 利差{spread:.2f}% ≥ 阈值{notify_threshold}%，触发通知！")
            content = f"【红利低波ETF】数据更新 {today.strftime('%m-%d')}\n\n"
            content += f"更新日期: {existing_snap['updateDate']}\n"
            content += f"指数股息率: {existing_snap['indexDivYield']:.2f}%\n"
            content += f"10年国债: {existing_snap['bondYield10Y']:.2f}%\n"
            content += f"股债利差: {existing_snap['spread']:.2f}%\n"
            content += f"历史分位: {existing_snap['percentile']}%\n"
            content += f"PE-TTM: {existing_snap['pe']:.1f}\n"
            content += f"PB: {existing_snap['pb']:.2f}\n"
            content += f"ETF价格: {existing_snap['etfPrice']:.3f}\n"

            d1_label = "极度低估" if spread >= 3.0 else "深度低估" if spread >= 2.5 else "合理偏低"
            content += f"\n⚡ 触发信号：{d1_label}\n操作建议："
            if spread >= 3.0:
                content += "重仓布局"
            elif spread >= 2.5:
                content += "分批加仓"
            elif spread >= 2.0:
                content += "定投为主"
            content += "\n\n⚠️ 仅供参考，不构成投资建议"

            send_feishu_notification(feishu_webhook, content)
        elif feishu_webhook:
            print(f"\n📊 利差{spread:.2f}% < 阈值{notify_threshold}%，不触发通知")
        else:
            print("\n  [INFO] 未配置飞书Webhook，跳过通知")

    else:
        print("\n[FAIL] 看板更新失败")
        sys.exit(1)

    print(f"\n{'='*60}")
    print("完成！")


if __name__ == "__main__":
    main()
