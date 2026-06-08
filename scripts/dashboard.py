"""
Bitcoin Dashboard Generator.

Reads collected data and generates a beautiful HTML visualization dashboard.
"""
import json
from datetime import datetime
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import config as cfg


def _load_latest_data() -> dict:
    """Load the most recent raw data JSON."""
    raw_files = sorted(cfg.DATA_DIR.glob("raw_*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not raw_files:
        return {}
    with open(raw_files[0], "r", encoding="utf-8") as f:
        return json.load(f)


def fmt_price(v):
    if v is None:
        return "—"
    v = float(v)
    if v >= 1000:
        return f"${v:,.0f}"
    return f"${v:.2f}"


def fmt_number(v):
    if v is None:
        return "—"
    v = float(v)
    if v >= 1_000_000_000_000:
        return f"{v / 1_000_000_000_000:.2f}T"
    if v >= 1_000_000_000:
        return f"{v / 1_000_000_000:.2f}B"
    if v >= 1_000_000:
        return f"{v / 1_000_000:.2f}M"
    if v >= 1_000:
        return f"{v / 1_000:.1f}K"
    return f"{v:,.2f}"


def fmt_pct(v):
    if v is None:
        return "—"
    v = float(v)
    sign = "+" if v > 0 else ""
    return f"{sign}{v:.2f}%"


def generate_dashboard(data: dict = None) -> str:
    """Generate a complete HTML dashboard."""
    if data is None:
        data = _load_latest_data()

    if not data:
        return "<html><body><h1>暂无数据</h1><p>请先运行 pipeline 采集数据。</p></body></html>"

    ts = data.get("timestamp", datetime.now().isoformat())
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        time_str = dt.strftime("%Y-%m-%d %H:%M UTC")
    except:
        time_str = ts

    price = data.get("price", {})
    tech = data.get("technical", {})
    risk = data.get("risk", {})
    onchain = data.get("onchain", {})

    btc_price = price.get("price_usd") or onchain.get("market_price_usd") or tech.get("current_price_usd") or 0
    btc_price_fmt = fmt_price(btc_price)

    risk_score = risk.get("score", 50)

    # Price change colors
    chg_7d = price.get("change_7d_pct")
    chg_7d_fmt = fmt_pct(chg_7d)
    chg_7d_color = "#22c55e" if chg_7d and chg_7d > 0 else "#ef4444" if chg_7d and chg_7d < 0 else "#94a3b8"

    chg_30d = price.get("change_30d_pct")
    chg_30d_fmt = fmt_pct(chg_30d)
    chg_30d_color = "#22c55e" if chg_30d and chg_30d > 0 else "#ef4444" if chg_30d and chg_30d < 0 else "#94a3b8"

    # Risk label and color
    if risk_score >= 75:
        risk_label = "极度贪婪"
        risk_color = "#ef4444"
        risk_bg = "rgba(239, 68, 68, 0.15)"
        risk_advice = "市场情绪过热。建议：分批减仓，设置移动止盈。"
    elif risk_score >= 60:
        risk_label = "贪婪"
        risk_color = "#f59e0b"
        risk_bg = "rgba(245, 158, 11, 0.15)"
        risk_advice = "市场偏乐观，部分指标过热。建议：持有为主，适当止盈。"
    elif risk_score >= 40:
        risk_label = "中性"
        risk_color = "#3b82f6"
        risk_bg = "rgba(59, 130, 246, 0.15)"
        risk_advice = "各指标处于正常范围，无明显极端信号。建议：持有或定投。"
    elif risk_score >= 25:
        risk_label = "恐惧"
        risk_color = "#8b5cf6"
        risk_bg = "rgba(139, 92, 246, 0.15)"
        risk_advice = "市场偏悲观，部分超卖。建议：分批建仓，关注机会。"
    else:
        risk_label = "极度恐惧"
        risk_color = "#06b6d4"
        risk_bg = "rgba(6, 182, 212, 0.15)"
        risk_advice = "市场极度恐慌。建议：积极加仓，留足子弹。"

    # Technical indicators
    rsi = tech.get("rsi_14")
    rsi_color = "#22c55e" if rsi and rsi < 40 else "#ef4444" if rsi and rsi > 70 else "#3b82f6"
    rsi_label = "超卖" if rsi and rsi < 30 else "偏弱" if rsi and rsi < 40 else "中性" if rsi and rsi < 60 else "偏强" if rsi and rsi < 70 else "过热"

    sma_20 = tech.get("sma_20")
    sma_50 = tech.get("sma_50")
    pct_20 = tech.get("pct_above_sma20")
    pct_50 = tech.get("pct_above_sma50")

    bb_upper = tech.get("bb_upper")
    bb_lower = tech.get("bb_lower")
    bb_pos = tech.get("bb_position_pct")
    bb_width = tech.get("bb_width_pct")

    macd_line = tech.get("macd_line")
    macd_signal = tech.get("macd_signal")
    macd_hist = tech.get("macd_histogram")
    macd_status = "多头" if macd_line and macd_signal and macd_line > macd_signal else "空头"

    # On-chain
    tx_count = onchain.get("tx_count_24h")
    blocks = onchain.get("blocks_mined_24h")
    difficulty = onchain.get("difficulty")
    hashrate = onchain.get("hashrate_ghs")
    btc_mined = onchain.get("total_btc_mined")

    # Signals
    signals = risk.get("signals", [])

    # Price history for chart (from sparkline or market_chart)
    # We stored sparkline data in raw data if available
    price_history = []
    if "market_chart_7d" in data:
        price_history = data["market_chart_7d"]
    elif "price" in data and "sparkline_7d" in data["price"]:
        price_history = data["price"]["sparkline_7d"]

    price_history_json = json.dumps(price_history)
    btc_price_json = json.dumps(btc_price)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>₿ 比特币监控仪表盘</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: #0f172a;
  color: #e2e8f0;
  min-height: 100vh;
  padding: 20px;
}}
.container {{ max-width: 1400px; margin: 0 auto; }}

/* Header */
.header {{
  text-align: center;
  padding: 30px 20px;
  margin-bottom: 30px;
}}
.header h1 {{
  font-size: 2.2rem;
  background: linear-gradient(135deg, #f7931a, #ffd700);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}}
.header .subtitle {{
  color: #64748b;
  margin-top: 6px;
  font-size: 0.9rem;
}}

/* Glassmorphism Cards */
.card {{
  background: rgba(30, 41, 59, 0.6);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  padding: 24px;
  position: relative;
  overflow: hidden;
}}
.card::before {{
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, #f7931a, #ffd700, #f7931a);
  opacity: 0.5;
}}

/* Price Banner */
.price-banner {{
  background: linear-gradient(135deg, rgba(247, 147, 26, 0.12), rgba(255, 215, 0, 0.05));
  border: 1px solid rgba(247, 147, 26, 0.2);
  border-radius: 20px;
  padding: 32px 40px;
  margin-bottom: 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 20px;
}}
.price-main .label {{
  font-size: 0.85rem;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 1px;
}}
.price-main .price {{
  font-size: 3.2rem;
  font-weight: 700;
  color: #f8fafc;
  letter-spacing: -1px;
  line-height: 1.2;
}}
.price-main .price span {{
  font-size: 1.4rem;
  color: #64748b;
  font-weight: 400;
}}
.price-changes {{
  display: flex;
  gap: 24px;
}}
.change-item {{
  text-align: center;
}}
.change-item .period {{
  font-size: 0.75rem;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}}
.change-item .value {{
  font-size: 1.3rem;
  font-weight: 600;
  margin-top: 4px;
}}

/* Grid Layout */
.grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
.grid-3 {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; }}
.grid-4 {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; }}

@media (max-width: 1024px) {{
  .grid-2, .grid-3, .grid-4 {{ grid-template-columns: 1fr 1fr; }}
}}
@media (max-width: 640px) {{
  .grid-2, .grid-3, .grid-4 {{ grid-template-columns: 1fr; }}
  .price-main .price {{ font-size: 2.2rem; }}
}}

/* Risk Gauge */
.risk-gauge {{
  text-align: center;
  padding: 20px;
}}
.risk-score {{
  font-size: 3.5rem;
  font-weight: 700;
  color: {risk_color};
  line-height: 1;
}}
.risk-label {{
  font-size: 1.1rem;
  font-weight: 500;
  margin: 8px 0 4px;
  color: {risk_color};
}}
.risk-bar {{
  width: 100%;
  height: 8px;
  background: rgba(255,255,255,0.1);
  border-radius: 4px;
  margin: 12px 0;
  overflow: hidden;
}}
.risk-fill {{
  height: 100%;
  width: {risk_score}%;
  background: linear-gradient(90deg, #06b6d4, #22c55e, #f59e0b, #ef4444);
  border-radius: 4px;
  transition: width 1s ease;
}}
.risk-advice {{
  font-size: 0.85rem;
  color: #94a3b8;
  line-height: 1.5;
  margin-top: 8px;
}}

/* Metric Cards */
.metric-card {{
  padding: 16px;
}}
.metric-card .metric-label {{
  font-size: 0.75rem;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}}
.metric-card .metric-value {{
  font-size: 1.5rem;
  font-weight: 600;
  margin-top: 6px;
  color: #f1f5f9;
}}
.metric-card .metric-sub {{ font-size: 0.85rem; color: #94a3b8; margin-top: 2px; }}

/* Chart containers */
.chart-container {{
  position: relative;
  height: 280px;
  margin-top: 12px;
}}

/* Section titles */
.section-title {{
  font-size: 1.1rem;
  font-weight: 600;
  color: #f1f5f9;
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(255,255,255,0.06);
}}
.section-title .badge {{
  font-size: 0.7rem;
  background: rgba(247,147,26,0.2);
  color: #f7931a;
  padding: 2px 8px;
  border-radius: 10px;
  margin-left: 8px;
}}

/* Table */
.data-table {{ width: 100%; border-collapse: collapse; }}
.data-table td {{
  padding: 8px 12px;
  border-bottom: 1px solid rgba(255,255,255,0.04);
  font-size: 0.9rem;
}}
.data-table td:last-child {{ text-align: right; font-weight: 500; }}
.data-table tr:last-child td {{ border-bottom: none; }}

/* Signal badges */
.signal {{
  display: inline-block;
  padding: 2px 10px;
  border-radius: 6px;
  font-size: 0.8rem;
  font-weight: 500;
}}
.signal-bull {{ background: rgba(34,197,94,0.15); color: #22c55e; }}
.signal-bear {{ background: rgba(239,68,68,0.15); color: #ef4444; }}
.signal-neutral {{ background: rgba(148,163,184,0.15); color: #94a3b8; }}
.signal-hot {{ background: rgba(239,68,68,0.2); color: #ef4444; }}

/* On-chain grid */
.onchain-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
}}
.onchain-item {{
  background: rgba(255,255,255,0.03);
  border-radius: 10px;
  padding: 14px;
}}
.onchain-item .label {{ font-size: 0.72rem; color: #64748b; }}
.onchain-item .value {{ font-size: 1.1rem; font-weight: 600; margin-top: 4px; }}

/* Signals list */
.signals-list {{
  margin-top: 12px;
}}
.signals-list li {{
  list-style: none;
  padding: 6px 0;
  font-size: 0.9rem;
  color: #94a3b8;
}}
.signals-list li::before {{
  content: '🔔 ';
}}

/* Footer */
.footer {{
  text-align: center;
  color: #475569;
  font-size: 0.8rem;
  padding: 40px 0 20px;
  border-top: 1px solid rgba(255,255,255,0.05);
  margin-top: 40px;
}}

/* Key Levels Table */
.key-levels td:first-child {{
  color: #94a3b8;
  font-weight: 400;
}}
</style>
</head>
<body>
<div class="container">

  <!-- Header -->
  <div class="header">
    <h1>₿ 比特币监控仪表盘</h1>
    <div class="subtitle">数据更新于 {time_str} · 多指标共识分析</div>
  </div>

  <!-- Price Banner -->
  <div class="price-banner">
    <div class="price-main">
      <div class="label">Bitcoin / USD</div>
      <div class="price">{fmt_price(btc_price)} <span>USD</span></div>
    </div>
    <div class="price-changes">
      <div class="change-item">
        <div class="period">7日</div>
        <div class="value" style="color:{chg_7d_color}">{chg_7d_fmt}</div>
      </div>
      <div class="change-item">
        <div class="period">30日</div>
        <div class="value" style="color:{chg_30d_color}">{chg_30d_fmt}</div>
      </div>
      <div class="change-item">
        <div class="period">RSI</div>
        <div class="value" style="color:{rsi_color}">{rsi if rsi else "—"}</div>
      </div>
      <div class="change-item">
        <div class="period">风险</div>
        <div class="value" style="color:{risk_color}">{risk_score}</div>
      </div>
    </div>
  </div>

  <!-- Row 1: Risk + Key Metrics -->
  <div class="grid-3" style="margin-bottom:24px">
    <!-- Risk Score -->
    <div class="card risk-gauge">
      <div class="risk-score">{risk_score}</div>
      <div class="risk-label">{risk_label}</div>
      <div class="risk-bar"><div class="risk-fill"></div></div>
      <div class="risk-advice">{risk_advice}</div>
    </div>

    <!-- Key Metrics -->
    <div class="card">
      <div class="section-title">📊 关键指标</div>
      <table class="data-table">
        <tr><td>市值</td><td style="color:#f1f5f9">{fmt_number(price.get('market_cap'))}</td></tr>
        <tr><td>24h 交易量</td><td style="color:#f1f5f9">{fmt_number(price.get('volume_24h'))}</td></tr>
        <tr><td>BTC 市占率</td><td style="color:#f1f5f9">{price.get('btc_dominance', '—')}%</td></tr>
        <tr><td>历史最高 (ATH)</td><td style="color:#f1f5f9">{fmt_price(price.get('ath'))}</td></tr>
        <tr><td>24h Highest</td><td style="color:#f1f5f9">{fmt_price(price.get('high_24h'))}</td></tr>
        <tr><td>24h Lowest</td><td style="color:#f1f5f9">{fmt_price(price.get('low_24h'))}</td></tr>
      </table>
    </div>

    <!-- Technical Snapshot -->
    <div class="card">
      <div class="section-title">🔬 技术速览</div>
      <table class="data-table">
        <tr>
          <td>RSI(14)</td>
          <td><span class="signal {'signal-hot' if rsi and rsi>70 else 'signal-bear' if rsi and rsi<30 else 'signal-neutral'}">{rsi if rsi else '—'} · {rsi_label}</span></td>
        </tr>
        <tr>
          <td>SMA 20</td>
          <td style="color:#f1f5f9">{fmt_price(sma_20)} <span style="color:{'#22c55e' if pct_20 and pct_20>0 else '#ef4444'};font-size:0.8rem">{fmt_pct(pct_20)}</span></td>
        </tr>
        <tr>
          <td>SMA 50</td>
          <td style="color:#f1f5f9">{fmt_price(sma_50)} <span style="color:{'#22c55e' if pct_50 and pct_50>0 else '#ef4444'};font-size:0.8rem">{fmt_pct(pct_50)}</span></td>
        </tr>
        <tr>
          <td>布林带位置</td>
          <td><span class="signal {'signal-hot' if bb_pos and bb_pos>80 else 'signal-bear' if bb_pos and bb_pos<20 else 'signal-neutral'}">{bb_pos:.0f}%</span></td>
        </tr>
        <tr>
          <td>MACD</td>
          <td><span class="signal {'signal-bull' if macd_status=='多头' else 'signal-bear'}">{macd_status}</span></td>
        </tr>
      </table>
      {f'<div class="signals-list"><ul>{"".join(f"<li>{s}</li>" for s in signals[:3])}</ul></div>' if signals else ''}
    </div>
  </div>

  <!-- Row 2: Price Chart + RSI Chart -->
  <div class="grid-2" style="margin-bottom:24px">
    <div class="card">
      <div class="section-title">📈 价格走势 <span class="badge">7日·每小时</span></div>
      <div class="chart-container">
        <canvas id="priceChart"></canvas>
      </div>
    </div>
    <div class="card">
      <div class="section-title">📊 技术指标详情</div>
      <table class="data-table">
        <tr>
          <td>RSI(14)</td>
          <td style="color:{rsi_color};font-weight:600">{rsi if rsi else '—'}</td>
        </tr>
        <tr>
          <td>布林带上轨</td>
          <td style="color:#f1f5f9">{fmt_price(bb_upper)}</td>
        </tr>
        <tr>
          <td>布林带下轨</td>
          <td style="color:#f1f5f9">{fmt_price(bb_lower)}</td>
        </tr>
        <tr>
          <td>布林带宽度</td>
          <td style="color:#f1f5f9">{bb_width:.2f}%</td>
        </tr>
        <tr>
          <td>MACD 快线</td>
          <td style="color:#22c55e">{macd_line:.2f}</td>
        </tr>
        <tr>
          <td>MACD 信号线</td>
          <td style="color:#ef4444">{macd_signal:.2f}</td>
        </tr>
        <tr>
          <td>MACD 柱 (Histogram)</td>
          <td style="color:#3b82f6">{macd_hist:.4f}</td>
        </tr>
      </table>

      <div class="section-title" style="margin-top:20px">🎯 关键价位</div>
      <table class="data-table key-levels">
        <tr><td>当前价</td><td style="color:#f1f5f9;font-weight:600">{fmt_price(btc_price)}</td></tr>
        <tr><td>ATH</td><td style="color:#f1f5f9">{fmt_price(price.get('ath'))}</td></tr>
        <tr><td>Fib 0.236</td><td style="color:#94a3b8">{fmt_price(float(price.get('ath',0))*0.764 + float(btc_price)*0.236) if price.get('ath') and btc_price < float(price.get('ath',0))*0.95 else '—'}</td></tr>
        <tr><td>Fib 0.382</td><td style="color:#94a3b8">{fmt_price(float(price.get('ath',0))*0.618 + float(btc_price)*0.382) if price.get('ath') and btc_price < float(price.get('ath',0))*0.95 else '—'}</td></tr>
        <tr><td>Fib 0.618</td><td style="color:#94a3b8">{fmt_price(float(price.get('ath',0))*0.382 + float(btc_price)*0.618) if price.get('ath') and btc_price < float(price.get('ath',0))*0.95 else '—'}</td></tr>
      </table>
    </div>
  </div>

  <!-- Row 3: On-Chain Data -->
  <div class="card" style="margin-bottom:24px">
    <div class="section-title">⛓️ 链上数据 <span class="badge">Blockchain.info</span></div>
    <div class="onchain-grid">
      <div class="onchain-item">
        <div class="label">24h 交易数</div>
        <div class="value">{fmt_number(tx_count)}</div>
      </div>
      <div class="onchain-item">
        <div class="label">24h 出块数</div>
        <div class="value">{blocks if blocks else '—'}</div>
      </div>
      <div class="onchain-item">
        <div class="label">出块间隔</div>
        <div class="value">{onchain.get('minutes_between_blocks', '—')} min</div>
      </div>
      <div class="onchain-item">
        <div class="label">挖矿难度</div>
        <div class="value">{fmt_number(difficulty)}</div>
      </div>
      <div class="onchain-item">
        <div class="label">算力</div>
        <div class="value">{fmt_number(hashrate)} GH/s</div>
      </div>
      <div class="onchain-item">
        <div class="label">已挖 BTC</div>
        <div class="value">{fmt_number(btc_mined)}</div>
      </div>
      <div class="onchain-item">
        <div class="label">市场价 (Blockchain)</div>
        <div class="value">{fmt_price(onchain.get('market_price_usd'))}</div>
      </div>
      <div class="onchain-item">
        <div class="label">当前高度</div>
        <div class="value">{fmt_number(onchain.get('latest_block_height'))}</div>
      </div>
    </div>
  </div>

  <!-- Footer -->
  <div class="footer">
    ₿ Bitcoin Monitor · 数据来源: CoinGecko / Blockchain.info<br>
    ⚠️ 以上分析仅供参考，不构成投资建议
  </div>

</div>

<script>
document.addEventListener('DOMContentLoaded', function() {{
  // Price Chart
  const priceCtx = document.getElementById('priceChart').getContext('2d');

  const priceHistory = {price_history_json};
  let chartData = [];

  if (Array.isArray(priceHistory) && priceHistory.length > 0) {{
    if (Array.isArray(priceHistory[0])) {{
      // [timestamp, price] format
      chartData = priceHistory.map(p => ({{ t: new Date(p[0]), y: p[1] }}));
    }} else {{
      // plain price array (sparkline)
      const now = new Date();
      chartData = priceHistory.map((p, i) => ({{
        t: new Date(now.getTime() - (priceHistory.length - i) * 3600000),
        y: p
      }}));
    }}
  }}

  new Chart(priceCtx, {{
    type: 'line',
    data: {{
      datasets: [{{
        label: 'BTC/USD',
        data: chartData,
        borderColor: '#f7931a',
        backgroundColor: (ctx) => {{
          const gradient = ctx.chart.ctx.createLinearGradient(0, 0, 0, 280);
          gradient.addColorStop(0, 'rgba(247, 147, 26, 0.2)');
          gradient.addColorStop(1, 'rgba(247, 147, 26, 0)');
          return gradient;
        }},
        fill: true,
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.3,
      }}]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      interaction: {{ mode: 'index', intersect: false }},
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{
          backgroundColor: 'rgba(15,23,42,0.9)',
          borderColor: 'rgba(247,147,26,0.3)',
          borderWidth: 1,
          callbacks: {{
            title: (items) => {{
              if (items[0]?.parsed?.x) {{
                return new Date(items[0].parsed.x).toLocaleString('zh-CN', {{
                  month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
                }});
              }}
              return '';
            }},
            label: (ctx) => '$' + Number(ctx.parsed.y).toLocaleString('en-US', {{minimumFractionDigits: 0, maximumFractionDigits: 0}})
          }}
        }}
      }},
      scales: {{
        x: {{
          type: 'time',
          time: {{ unit: 'day', displayFormats: {{ day: 'MM/dd' }} }},
          grid: {{ color: 'rgba(255,255,255,0.03)' }},
          ticks: {{ color: '#64748b', maxTicksLimit: 8 }}
        }},
        y: {{
          grid: {{ color: 'rgba(255,255,255,0.03)' }},
          ticks: {{
            color: '#64748b',
            callback: (v) => '$' + Number(v).toLocaleString('en-US')
          }}
        }}
      }}
    }}
  }});
}});
</script>
</body>
</html>"""


def run():
    """Generate the dashboard HTML file."""
    data = _load_latest_data()
    if not data:
        cfg.logger.warning("No data found. Run the pipeline first.")
        print("❌ 没有找到数据，请先运行 python scripts/orchestrator.py")
        return

    html = generate_dashboard(data)

    today = datetime.now().strftime("%Y%m%d")
    output_path = cfg.REPORTS_DIR / f"btc_dashboard_{today}.html"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    cfg.logger.info(f"✅ Dashboard generated: {output_path}")
    print(f"✅ 仪表盘已生成: {output_path}")
    print(f"💡 在浏览器中打开查看: file://{output_path}")
    return output_path


if __name__ == "__main__":
    run()
