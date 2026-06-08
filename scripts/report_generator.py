"""
Bitcoin Monitor Report Generator.

Generates Chinese-language markdown analysis reports from collected indicator data.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import config as cfg


def _fmt_price(v) -> str:
    """Format a USD price value."""
    if v is None:
        return "N/A"
    try:
        v = float(v)
        if v >= 1000000:
            return f"${v / 1000000:,.2f}M"
        elif v >= 1000:
            return f"${v:,.0f}"
        elif v >= 1:
            return f"${v:,.2f}"
        else:
            return f"${v:.4f}"
    except (ValueError, TypeError):
        return str(v)


def _fmt_number(v) -> str:
    """Format a large number with commas."""
    if v is None:
        return "N/A"
    try:
        v = float(v)
        if v >= 1_000_000_000:
            return f"{v / 1_000_000_000:.2f}B"
        elif v >= 1_000_000:
            return f"{v / 1_000_000:.2f}M"
        elif v >= 1_000:
            return f"{v / 1_000:.1f}K"
        return f"{v:,.0f}"
    except (ValueError, TypeError):
        return str(v)


def _fmt_pct(v) -> str:
    """Format a percentage value with sign."""
    if v is None:
        return "N/A"
    try:
        v = float(v)
        sign = "+" if v > 0 else ""
        return f"{sign}{v:.2f}%"
    except (ValueError, TypeError):
        return str(v)


def _signal_badge(value: float, thresholds: list) -> str:
    """Return emoji badge based on value vs thresholds."""
    for threshold, emoji, label in thresholds:
        if value >= threshold:
            return f"{emoji} {label}"
    return "⚪ 中性"


def generate_report(data: dict) -> str:
    """Generate a full Chinese Markdown report."""
    now = datetime.now(timezone.utc)
    price = data.get("price", {})
    onchain = data.get("onchain", {})
    tech = data.get("technical", {})
    risk = data.get("risk", {})

    # --- Header ---
    report = [
        f"# ₿ 比特币多指标监控报告",
        f"",
        f"**生成时间**: {now.strftime('%Y-%m-%d %H:%M')} UTC",
        f"**数据来源**: CoinGecko · Blockchain.info",
        f"",
        f"---",
        f"",
        f"## 📊 综合风险评估",
        f"",
    ]

    # Risk score bar
    score = risk.get("score", 50)
    bar_len = 20
    filled = round(score / 100 * bar_len)
    bar = "█" * filled + "░" * (bar_len - filled)
    report.append(f"**风险评分: {score}/100**")
    report.append(f"")
    report.append(f"`{bar}`")
    report.append(f"")
    report.append(f"**判断**: {risk.get('label', 'N/A')}")
    report.append(f"")
    report.append(f"**策略建议**: {risk.get('summary', 'N/A')}")
    report.append(f"")

    # Individual signals
    signals = risk.get("signals", [])
    if signals:
        report.append(f"### 🔔 关键信号")
        for s in signals:
            report.append(f"- {s}")
        report.append(f"")

    report.append(f"---")
    report.append(f"")

    # --- Price Dashboard ---
    btc_price = price.get("price_usd")
    report.append(f"## 💰 价格快照")
    report.append(f"")
    report.append(f"| 指标 | 数值 |")
    report.append(f"|------|------|")
    report.append(f"| **当前价格** | **{_fmt_price(btc_price)}** |")
    report.append(f"| 24h最高 | {_fmt_price(price.get('high_24h'))} |")
    report.append(f"| 24h最低 | {_fmt_price(price.get('low_24h'))} |")
    report.append(f"| 历史最高 (ATH) | {_fmt_price(price.get('ath'))} |")
    report.append(f"| ATH 距今日 | {price.get('ath_date', 'N/A')[:10] if price.get('ath_date') else 'N/A'} |")
    report.append(f"| 市值 | {_fmt_number(price.get('market_cap'))} |")
    report.append(f"| 24h交易量 | {_fmt_number(price.get('volume_24h'))} |")
    report.append(f"| BTC市占率 | {price.get('btc_dominance', 'N/A')}% |")
    report.append(f"| 总加密市值 | {_fmt_number(price.get('total_market_cap'))} |")
    report.append(f"")

    # Price changes
    report.append(f"### 📈 涨跌幅")
    report.append(f"")
    report.append(f"| 周期 | 变化 | 信号 |")
    report.append(f"|------|------|------|")
    chg_7d = price.get("change_7d_pct")
    chg_30d = price.get("change_30d_pct")
    chg_60d = price.get("change_60d_pct")
    chg_200d = price.get("change_200d_pct")

    for days, val in [("7天", chg_7d), ("14天", price.get("change_14d_pct")),
                      ("30天", chg_30d), ("60天", chg_60d), ("200天", chg_200d)]:
        badge = ""
        if val is not None:
            if abs(val) > 30:
                badge = "🔥 {}" if val > 0 else "💥 {}"
            elif abs(val) > 15:
                badge = "📈 {}" if val > 0 else "📉 {}"
            elif abs(val) > 5:
                badge = "↗ {}" if val > 0 else "↘ {}"
            else:
                badge = "➡ {}"
            badge = badge.format(_fmt_pct(val))
        else:
            badge = "N/A"
        report.append(f"| {days} | {_fmt_pct(val)} | {badge} |")

    report.append(f"")

    # --- Technical Analysis ---
    report.append(f"---")
    report.append(f"")
    report.append(f"## 🔬 技术指标")
    report.append(f"")

    # RSI
    rsi = tech.get("rsi_14")
    if rsi is not None:
        if rsi > 70:
            rsi_signal = "🔥 过热"
        elif rsi > 60:
            rsi_signal = "📈 偏强"
        elif rsi < 30:
            rsi_signal = "💎 超卖"
        elif rsi < 40:
            rsi_signal = "📉 偏弱"
        else:
            rsi_signal = "⚪ 中性"
    else:
        rsi_signal = "N/A"

    report.append(f"| 指标 | 数值 | 信号 |")
    report.append(f"|------|------|------|")
    report.append(f"| **RSI (14)** | **{rsi if rsi is not None else 'N/A'}** | {rsi_signal} |")
    report.append(f"| SMA 20 | {_fmt_price(tech.get('sma_20'))} | {_fmt_pct(tech.get('pct_above_sma20'))} |")
    report.append(f"| SMA 50 | {_fmt_price(tech.get('sma_50'))} | {_fmt_pct(tech.get('pct_above_sma50'))} |")
    report.append(f"| 布林带上轨 | {_fmt_price(tech.get('bb_upper'))} | — |")
    report.append(f"| 布林带下轨 | {_fmt_price(tech.get('bb_lower'))} | — |")
    report.append(f"| 布林带宽度 | {tech.get('bb_width_pct', 'N/A')}% | {'⬅ 挤压' if tech.get('bb_width_pct') is not None and tech.get('bb_width_pct', 0) < 5 else '➡ 正常'} |")
    report.append(f"| 布林带位置 | {tech.get('bb_position_pct', 'N/A')}% | {'上轨' if tech.get('bb_position_pct', 50) > 80 else '下轨' if tech.get('bb_position_pct', 50) < 20 else '中轨'} |")

    macd_line = tech.get("macd_line")
    macd_signal = tech.get("macd_signal")
    macd_hist = tech.get("macd_histogram")
    if macd_line is not None and macd_signal is not None:
        macd_status = "📈 多头" if macd_line > macd_signal else "📉 空头"
        report.append(f"| MACD 快线 | {macd_line:.2f} | {macd_status} |")
        report.append(f"| MACD 信号线 | {macd_signal:.2f} | 柱: {macd_hist:.4f} |")
    report.append(f"")

    # --- On-Chain Analysis ---
    report.append(f"---")
    report.append(f"")
    report.append(f"## ⛓️ 链上数据")
    report.append(f"")

    report.append(f"| 指标 | 数值 |")
    report.append(f"|------|------|")
    report.append(f"| 活跃地址 (24h) | — (需要其他API) |")
    report.append(f"| 交易数 (24h) | {_fmt_number(onchain.get('tx_count_24h'))} |")
    report.append(f"| 当前高度 | {_fmt_number(onchain.get('latest_block_height'))} |")
    report.append(f"| 挖矿难度 | {_fmt_number(onchain.get('difficulty'))} |")
    report.append(f"| 算力 | {_fmt_number(onchain.get('hashrate_ghs'))} GH/s |")
    report.append(f"| 已挖 BTC | {_fmt_number(onchain.get('total_btc_mined'))} / 21,000,000 |")
    report.append(f"| 24h 手续费总额 | {onchain.get('avg_fee_btc', 'N/A')} BTC |")
    report.append(f"| 24h 出块数 | {onchain.get('blocks_mined_24h', 'N/A')} |")
    report.append(f"| 出块间隔 | {onchain.get('minutes_between_blocks', 'N/A')} 分钟 |")
    report.append(f"")

    # --- Key levels ---
    if btc_price:
        report.append(f"---")
        report.append(f"")
        report.append(f"## 🎯 关键价位参考")
        report.append(f"")
        report.append(f"| 级别 | 价位 | 说明 |")
        report.append(f"|------|------|------|")

        # Fibonacci levels from ATH retracement
        ath = float(price.get("ath", btc_price * 1.5)) if price.get("ath") else btc_price * 1.5
        # Only show fib levels if current is below ATH
        if btc_price < ath * 0.95:
            bear = ath - btc_price
            fib_236 = ath - bear * 0.236
            fib_382 = ath - bear * 0.382
            fib_500 = ath - bear * 0.5
            fib_618 = ath - bear * 0.618
            fib_786 = ath - bear * 0.786
            report.append(f"| 当前价 | {_fmt_price(btc_price)} | — |")
            report.append(f"| ATH | {_fmt_price(ath)} | 历史最高 |")
            report.append(f"| Fib 0.236 | {_fmt_price(fib_236)} | 弱反弹阻力 |")
            report.append(f"| Fib 0.382 | {_fmt_price(fib_382)} | 关键阻力 |")
            report.append(f"| Fib 0.500 | {_fmt_price(fib_500)} | 心理位 |")
            report.append(f"| Fib 0.618 | {_fmt_price(fib_618)} | 强支撑/阻力 |")
            report.append(f"| Fib 0.786 | {_fmt_price(fib_786)} | 最后防线 |")

    report.append(f"")
    report.append(f"---")
    report.append(f"")
    report.append(f"*报告自动生成于 {now.strftime('%Y-%m-%d %H:%M UTC')}*")
    report.append(f"*⚠️ 以上分析仅供参考，不构成投资建议。加密货币市场风险高，请理性决策。*")
    report.append(f"")

    return "\n".join(report)


def run(data: dict = None) -> dict:
    """Generate report from collected data dict or fresh collection."""
    if data is None:
        from scripts.indicators import collect_all, save_raw_data
        data = collect_all()
        save_raw_data(data)

    report = generate_report(data)

    today = datetime.now().strftime("%Y%m%d")
    report_path = cfg.REPORTS_DIR / f"btc_monitor_{today}.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    cfg.logger.info(f"报告已生成: {report_path}")
    return {"path": str(report_path), "size": len(report), "summary": data.get("risk", {}).get("summary", "")}


if __name__ == "__main__":
    result = run()
    print(f"✅ 报告生成: {result['path']}")
    print(f"📊 {result['summary']}")
