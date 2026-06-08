"""
Bitcoin Monitor Dashboard Server.

A lightweight Python HTTP server that serves a live-updating dashboard.
Access at http://localhost:8765

Usage:
  python scripts/server.py          # Start server (default port 8765)
  python scripts/server.py --port 8888  # Custom port
"""
import json
import os
import sys
import urllib.parse
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import config as cfg
from scripts.strategy_engine import (
    list_strategies, get_strategy, save_strategy, delete_strategy,
    activate_strategy, deactivate_strategy, get_active_strategy,
    evaluate_strategy, evaluate_active_strategy,
    INDICATOR_REGISTRY, OPERATORS, init_default_strategies, get_default_strategies,
)

PORT = 8765
HOST = "127.0.0.1"

# ── Dashboard HTML (embedded for single-file deployment) ──────────────────

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>₿ 比特币实时监控面板</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: #0f172a;
  color: #e2e8f0;
  min-height: 100vh;
  padding: 20px;
}
.container { max-width: 1400px; margin: 0 auto; }

/* Header */
.header {
  text-align: center;
  padding: 24px 20px 16px;
  margin-bottom: 20px;
}
.header h1 {
  font-size: 2rem;
  background: linear-gradient(135deg, #f7931a, #ffd700);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.header .subtitle { color: #64748b; margin-top: 4px; font-size: 0.85rem; }
.header .status-bar {
  display: flex; justify-content: center; align-items: center; gap: 20px;
  margin-top: 10px; font-size: 0.8rem; color: #64748b;
}
.live-dot {
  display: inline-block; width: 8px; height: 8px; border-radius: 50%;
  background: #22c55e; margin-right: 4px; animation: pulse 2s infinite;
}
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }

/* Glassmorphism Cards */
.card {
  background: rgba(30, 41, 59, 0.6);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  padding: 20px;
  position: relative;
  overflow: hidden;
}
.card::before {
  content: '';
  position: absolute; top: 0; left: 0; right: 0; height: 3px;
  background: linear-gradient(90deg, #f7931a, #ffd700, #f7931a);
  opacity: 0.4;
}

/* Price Banner */
.price-banner {
  background: linear-gradient(135deg, rgba(247,147,26,0.12), rgba(255,215,0,0.05));
  border: 1px solid rgba(247,147,26,0.2);
  border-radius: 20px;
  padding: 28px 36px;
  margin-bottom: 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
}
.price-main .label { font-size: 0.8rem; color: #64748b; letter-spacing: 1px; }
.price-main .price {
  font-size: 3rem; font-weight: 700; color: #f8fafc;
  letter-spacing: -1px; line-height: 1.2;
}
.price-main .price span { font-size: 1.2rem; color: #64748b; font-weight: 400; }
.price-changes { display: flex; gap: 20px; }
.change-item { text-align: center; }
.change-item .period { font-size: 0.7rem; color: #64748b; letter-spacing: 0.5px; }
.change-item .value { font-size: 1.2rem; font-weight: 600; margin-top: 4px; }

/* Grid */
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; }
@media (max-width: 1024px) { .grid-2, .grid-3 { grid-template-columns: 1fr 1fr; } }
@media (max-width: 640px) {
  .grid-2, .grid-3 { grid-template-columns: 1fr; }
  .price-main .price { font-size: 2rem; }
}

/* Risk Gauge */
.risk-gauge { text-align: center; padding: 16px; }
.risk-score { font-size: 3.2rem; font-weight: 700; line-height: 1; }
.risk-label { font-size: 1rem; font-weight: 500; margin: 6px 0 4px; }
.risk-bar {
  width: 100%; height: 8px; background: rgba(255,255,255,0.1);
  border-radius: 4px; margin: 10px 0; overflow: hidden;
}
.risk-fill { height: 100%; border-radius: 4px; transition: width 0.8s ease; }
.risk-advice { font-size: 0.82rem; color: #94a3b8; line-height: 1.5; margin-top: 6px; }

/* Metric Card */
.metric-card { padding: 12px; }
.metric-card .metric-label { font-size: 0.72rem; color: #64748b; letter-spacing: 0.5px; }
.metric-card .metric-value { font-size: 1.4rem; font-weight: 600; margin-top: 4px; color: #f1f5f9; }
.metric-card .metric-sub { font-size: 0.8rem; color: #94a3b8; margin-top: 2px; }

/* Chart */
.chart-container { position: relative; height: 260px; margin-top: 10px; }

/* Section Title */
.section-title {
  font-size: 1rem; font-weight: 600; color: #f1f5f9;
  margin-bottom: 12px; padding-bottom: 6px;
  border-bottom: 1px solid rgba(255,255,255,0.06);
}
.section-title .badge {
  font-size: 0.65rem; background: rgba(247,147,26,0.2);
  color: #f7931a; padding: 2px 8px; border-radius: 10px; margin-left: 6px;
}

/* Table */
.data-table { width: 100%; border-collapse: collapse; }
.data-table td {
  padding: 6px 10px; border-bottom: 1px solid rgba(255,255,255,0.04);
  font-size: 0.85rem;
}
.data-table td:last-child { text-align: right; font-weight: 500; }
.data-table tr:last-child td { border-bottom: none; }

/* Signal badges */
.signal { display: inline-block; padding: 2px 8px; border-radius: 6px; font-size: 0.78rem; font-weight: 500; }
.signal-bull { background:rgba(34,197,94,0.15); color:#22c55e; }
.signal-bear { background:rgba(239,68,68,0.15); color:#ef4444; }
.signal-neutral { background:rgba(148,163,184,0.15); color:#94a3b8; }
.signal-hot { background:rgba(239,68,68,0.2); color:#ef4444; }
.signal-cold { background:rgba(6,182,212,0.15); color:#06b6d4; }

/* On-chain grid */
.onchain-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 10px; }
.onchain-item {
  background: rgba(255,255,255,0.03); border-radius: 10px; padding: 12px;
}
.onchain-item .olabel { font-size: 0.7rem; color: #64748b; }
.onchain-item .ovalue { font-size: 1rem; font-weight: 600; margin-top: 3px; }

/* Signals */
.signals-list { margin-top: 10px; }
.signals-list li { list-style: none; padding: 4px 0; font-size: 0.85rem; color: #94a3b8; }
.signals-list li::before { content: '🔔 '; }

/* Loading */
#loading {
  position: fixed; inset: 0; display: flex; align-items: center; justify-content: center;
  background: #0f172a; z-index: 9999; font-size: 1.2rem; color: #64748b;
}
#loading .spinner {
  width: 40px; height: 40px; border: 3px solid rgba(247,147,26,0.2);
  border-top-color: #f7931a; border-radius: 50%; animation: spin 0.8s linear infinite;
  margin-bottom: 12px;
}
@keyframes spin { to { transform: rotate(360deg); } }
#main-content { display: none; }

/* Footer */
.footer { text-align: center; color: #475569; font-size: 0.75rem; padding: 32px 0 16px; border-top: 1px solid rgba(255,255,255,0.05); margin-top: 32px; }
</style>
</head>
<body>
<div id="loading">
  <div style="text-align:center"><div class="spinner"></div>加载中...</div>
</div>

<div id="main-content" class="container">
  <div class="header">
    <div style="display:flex;justify-content:center;gap:10px;margin-bottom:10px">
      <a href="/" style="display:inline-block;padding:6px 18px;border-radius:8px;text-decoration:none;font-size:0.82rem;font-weight:500;background:rgba(247,147,26,0.2);color:#f7931a;border:1px solid rgba(247,147,26,0.3)">📊 监控面板</a>
      <a href="/strategies" style="display:inline-block;padding:6px 18px;border-radius:8px;text-decoration:none;font-size:0.82rem;font-weight:500;background:rgba(255,255,255,0.05);color:#64748b">🎯 策略管理</a>
    </div>
    <h1>₿ 比特币实时监控面板</h1>
    <div class="subtitle" id="update-time">加载中...</div>
    <div class="status-bar">
      <span><span class="live-dot"></span>实时更新</span>
      <span id="next-update">60s后刷新</span>
      <span><a href="#" onclick="location.reload()" style="color:#64748b;text-decoration:none">⟳ 手动刷新</a></span>
    </div>
  </div>

  <!-- Price Banner -->
  <div class="price-banner" id="price-banner">
    <div class="price-main">
      <div class="label">Bitcoin / USD</div>
      <div class="price" id="btc-price">— <span>USD</span></div>
    </div>
    <div class="price-changes" id="price-changes"></div>
  </div>

  <!-- Row 1 -->
  <div class="grid-3" style="margin-bottom:20px">
    <div class="card risk-gauge" id="risk-card">
      <div class="risk-score" id="risk-score">—</div>
      <div class="risk-label" id="risk-label">—</div>
      <div class="risk-bar"><div class="risk-fill" id="risk-fill" style="width:50%;background:linear-gradient(90deg,#06b6d4,#22c55e,#f59e0b,#ef4444)"></div></div>
      <div class="risk-advice" id="risk-advice">加载中...</div>
    </div>

    <div class="card">
      <div class="section-title">📊 关键指标</div>
      <table class="data-table" id="metrics-table"></table>
    </div>

    <div class="card">
      <div class="section-title">🔬 技术速览</div>
      <table class="data-table" id="tech-table"></table>
      <div class="signals-list" id="signals-list"></div>
    </div>
  </div>

  <!-- Row 2 -->
  <div class="grid-2" style="margin-bottom:20px">
    <div class="card">
      <div class="section-title">📈 价格走势 <span class="badge">7日·每小时</span></div>
      <div class="chart-container"><canvas id="priceChart"></canvas></div>
    </div>
    <div class="card">
      <div class="section-title">🎯 技术指标详表</div>
      <table class="data-table" id="tech-detail-table"></table>
    </div>
  </div>

  <!-- Row 3 -->
  <div class="card" style="margin-bottom:20px">
    <div class="section-title">⛓️ 链上数据 <span class="badge">Blockchain.info</span></div>
    <div class="onchain-grid" id="onchain-grid"></div>
  </div>

  <div class="footer">
    ₿ Bitcoin Monitor · 数据来源: CoinGecko / Blockchain.info · 每12小时自动采集<br>
    ⚠️ 以上分析仅供参考，不构成投资建议
  </div>
</div>

<script>
let priceChart = null;
let updateTimer = null;
let countdown = 60;

function fmtPrice(v) {
  if (v == null) return '—';
  v = Number(v);
  if (v >= 1000) return '$' + v.toLocaleString('en-US', {minimumFractionDigits:0});
  return '$' + v.toFixed(2);
}

function fmtNumber(v) {
  if (v == null) return '—';
  v = Number(v);
  if (v >= 1e12) return (v/1e12).toFixed(2) + 'T';
  if (v >= 1e9) return (v/1e9).toFixed(2) + 'B';
  if (v >= 1e6) return (v/1e6).toFixed(2) + 'M';
  if (v >= 1e3) return (v/1e3).toFixed(1) + 'K';
  return v.toLocaleString('en-US');
}

function fmtPct(v) {
  if (v == null) return '—';
  v = Number(v);
  return (v > 0 ? '+' : '') + v.toFixed(2) + '%';
}

function updateCountdown() {
  countdown--;
  if (countdown <= 0) countdown = 60;
  document.getElementById('next-update').textContent = countdown + 's后刷新';
}

async function fetchData() {
  try {
    const resp = await fetch('/api/data');
    const data = await resp.json();
    renderDashboard(data);
    document.getElementById('update-time').textContent = '数据更新于 ' + (data.timestamp || new Date().toISOString()).replace('T',' ').substring(0,19) + ' UTC';
    document.getElementById('loading').style.display = 'none';
    document.getElementById('main-content').style.display = 'block';
    countdown = 60;
  } catch (e) {
    console.error('Fetch failed:', e);
  }
}

function renderDashboard(d) {
  const price = d.price || {};
  const tech = d.technical || {};
  const risk = d.risk || {};
  const onchain = d.onchain || {};
  const btcPrice = price.price_usd || onchain.market_price_usd || tech.current_price_usd;

  // ── Price Banner ──
  document.getElementById('btc-price').innerHTML = fmtPrice(btcPrice) + ' <span>USD</span>';

  const changesHtml = [
    {period:'7日', val: price.change_7d_pct, color: price.change_7d_pct > 0 ? '#22c55e' : '#ef4444'},
    {period:'30日', val: price.change_30d_pct, color: price.change_30d_pct > 0 ? '#22c55e' : '#ef4444'},
    {period:'RSI', val: tech.rsi_14, color: tech.rsi_14 > 70 ? '#ef4444' : tech.rsi_14 < 30 ? '#06b6d4' : '#3b82f6'},
    {period:'风险', val: risk.score, color: risk.score > 60 ? '#ef4444' : risk.score < 30 ? '#06b6d4' : '#3b82f6'},
  ].map(c => `<div class="change-item"><div class="period">${c.period}</div><div class="value" style="color:${c.color}">${c.val != null ? Number(c.val).toFixed(1) : '—'}</div></div>`).join('');
  document.getElementById('price-changes').innerHTML = changesHtml;

  // ── Risk Score ──
  const score = risk.score || 50;
  const label = risk.label || '中性';
  let rcolor;
  if (score >= 75) rcolor = '#ef4444';
  else if (score >= 60) rcolor = '#f59e0b';
  else if (score >= 40) rcolor = '#3b82f6';
  else if (score >= 25) rcolor = '#8b5cf6';
  else rcolor = '#06b6d4';
  document.getElementById('risk-score').textContent = score;
  document.getElementById('risk-score').style.color = rcolor;
  document.getElementById('risk-label').textContent = label;
  document.getElementById('risk-label').style.color = rcolor;
  document.getElementById('risk-fill').style.width = score + '%';
  document.getElementById('risk-advice').textContent = risk.summary || '—';

  // ── Key Metrics ──
  document.getElementById('metrics-table').innerHTML = [
    ['市值', fmtNumber(price.market_cap)],
    ['24h交易量', fmtNumber(price.volume_24h)],
    ['BTC市占率', price.btc_dominance != null ? price.btc_dominance.toFixed(1) + '%' : '—'],
    ['ATH', fmtPrice(price.ath)],
    ['24h最高', fmtPrice(price.high_24h)],
    ['24h最低', fmtPrice(price.low_24h)],
  ].map(r => `<tr><td>${r[0]}</td><td style="color:#f1f5f9">${r[1]}</td></tr>`).join('');

  // ── Tech Snapshot ──
  const rsi = tech.rsi_14;
  const rsiCls = rsi > 70 ? 'signal-hot' : rsi < 30 ? 'signal-cold' : 'signal-neutral';
  const rsiLbl = rsi > 70 ? '过热' : rsi > 60 ? '偏强' : rsi < 30 ? '超卖' : rsi < 40 ? '偏弱' : '中性';

  const pct20 = tech.pct_above_sma20;
  const pct50 = tech.pct_above_sma50;
  const bbPos = tech.bb_position_pct;
  const bbCls = bbPos > 80 ? 'signal-hot' : bbPos < 20 ? 'signal-cold' : 'signal-neutral';
  const macdStatus = tech.macd_line != null && tech.macd_signal != null
    ? (tech.macd_line > tech.macd_signal ? '多头' : '空头') : '—';
  const macdCls = macdStatus === '多头' ? 'signal-bull' : macdStatus === '空头' ? 'signal-bear' : 'signal-neutral';

  document.getElementById('tech-table').innerHTML = [
    ['RSI(14)', `<span class="signal ${rsiCls}">${rsi != null ? rsi.toFixed(1) : '—'} · ${rsiLbl}</span>`],
    ['SMA 20', `${fmtPrice(tech.sma_20)} <span style="font-size:0.78rem;color:${pct20 > 0 ? '#22c55e' : '#ef4444'}">${fmtPct(pct20)}</span>`],
    ['SMA 50', `${fmtPrice(tech.sma_50)} <span style="font-size:0.78rem;color:${pct50 > 0 ? '#22c55e' : '#ef4444'}">${fmtPct(pct50)}</span>`],
    ['布林带位置', `<span class="signal ${bbCls}">${bbPos != null ? bbPos.toFixed(0) + '%' : '—'}</span>`],
    ['MACD', `<span class="signal ${macdCls}">${macdStatus}</span>`],
  ].map(r => `<tr><td>${r[0]}</td><td>${r[1]}</td></tr>`).join('');

  // Signals
  const signals = risk.signals || [];
  document.getElementById('signals-list').innerHTML = signals.length
    ? '<ul>' + signals.map(s => `<li>${s}</li>`).join('') + '</ul>'
    : '';

  // ── Tech Detail Table ──
  document.getElementById('tech-detail-table').innerHTML = [
    ['RSI(14)', rsi != null ? rsi.toFixed(2) : '—'],
    ['布林带上轨', fmtPrice(tech.bb_upper)],
    ['布林带下轨', fmtPrice(tech.bb_lower)],
    ['布林带宽度', tech.bb_width_pct != null ? tech.bb_width_pct.toFixed(2) + '%' : '—'],
    ['MACD快线', tech.macd_line != null ? tech.macd_line.toFixed(2) : '—'],
    ['MACD信号线', tech.macd_signal != null ? tech.macd_signal.toFixed(2) : '—'],
    ['MACD柱', tech.macd_histogram != null ? tech.macd_histogram.toFixed(4) : '—'],
  ].map(r => `<tr><td>${r[0]}</td><td style="color:#f1f5f9;font-weight:600">${r[1]}</td></tr>`).join('');

  // ── On-chain Grid ──
  const onchainItems = [
    ['24h交易数', fmtNumber(onchain.tx_count_24h)],
    ['24h出块数', onchain.blocks_mined_24h != null ? Number(onchain.blocks_mined_24h).toFixed(0) : '—'],
    ['出块间隔', onchain.minutes_between_blocks != null ? onchain.minutes_between_blocks + ' min' : '—'],
    ['挖矿难度', fmtNumber(onchain.difficulty)],
    ['算力', fmtNumber(onchain.hashrate_ghs) + ' GH/s'],
    ['已挖BTC', fmtNumber(onchain.total_btc_mined)],
    ['市场价(Bchain)', fmtPrice(onchain.market_price_usd)],
    ['区块高度', fmtNumber(onchain.latest_block_height)],
  ];
  document.getElementById('onchain-grid').innerHTML = onchainItems
    .map(r => `<div class="onchain-item"><div class="olabel">${r[0]}</div><div class="ovalue">${r[1]}</div></div>`)
    .join('');

  // ── Price Chart ──
  updatePriceChart(d.market_chart_7d);
}

function updatePriceChart(marketChart) {
  let chartData = [];
  if (marketChart && marketChart.length > 0) {
    chartData = marketChart.map(p => ({ t: new Date(p[0]), y: p[1] }));
  }

  const ctx = document.getElementById('priceChart').getContext('2d');

  if (priceChart) {
    priceChart.data.datasets[0].data = chartData;
    priceChart.update('none');
    return;
  }

  priceChart = new Chart(ctx, {
    type: 'line',
    data: {
      datasets: [{
        label: 'BTC/USD',
        data: chartData,
        borderColor: '#f7931a',
        backgroundColor: function(ctx) {
          const g = ctx.chart.ctx.createLinearGradient(0, 0, 0, 260);
          g.addColorStop(0, 'rgba(247,147,26,0.2)');
          g.addColorStop(1, 'rgba(247,147,26,0)');
          return g;
        },
        fill: true,
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.3,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      animation: { duration: 400 },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: 'rgba(15,23,42,0.9)',
          borderColor: 'rgba(247,147,26,0.3)', borderWidth: 1,
          callbacks: {
            title: items => items[0]?.parsed?.x
              ? new Date(items[0].parsed.x).toLocaleString('zh-CN', {month:'short', day:'numeric', hour:'2-digit', minute:'2-digit'})
              : '',
            label: ctx => '$' + Number(ctx.parsed.y).toLocaleString('en-US', {minimumFractionDigits:0})
          }
        }
      },
      scales: {
        x: {
          type: 'time', time: { unit: 'day', displayFormats: { day: 'MM/dd' } },
          grid: { color: 'rgba(255,255,255,0.03)' },
          ticks: { color: '#64748b', maxTicksLimit: 8 }
        },
        y: {
          grid: { color: 'rgba(255,255,255,0.03)' },
          ticks: { color: '#64748b', callback: v => '$' + Number(v).toLocaleString('en-US') }
        }
      }
    }
  });
}

// Auto-refresh
fetchData();
updateTimer = setInterval(fetchData, 60000);
setInterval(updateCountdown, 1000);
</script>
</body>
</html>"""


# ── Strategy Page HTML ─────────────────────────────────────────────────

STRATEGY_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>₿ 策略管理 — Bitcoin Monitor</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: #0f172a; color: #e2e8f0; min-height: 100vh; padding: 20px;
}
.container { max-width: 1400px; margin: 0 auto; }

/* Nav */
.nav {
  display: flex; justify-content: center; gap: 12px; margin-bottom: 24px;
}
.nav a {
  display: inline-block; padding: 8px 24px; border-radius: 10px;
  text-decoration: none; font-size: 0.9rem; font-weight: 500;
  background: rgba(255,255,255,0.05); color: #64748b;
  transition: all 0.2s;
}
.nav a:hover { background: rgba(247,147,26,0.15); color: #f7931a; }
.nav a.active { background: rgba(247,147,26,0.2); color: #f7931a; border: 1px solid rgba(247,147,26,0.3); }

/* Page Header */
.page-header { text-align: center; margin-bottom: 24px; }
.page-header h1 { font-size: 1.8rem; background: linear-gradient(135deg,#f7931a,#ffd700); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
.page-header .subtitle { color: #64748b; margin-top: 4px; font-size: 0.85rem; }

/* Glass Card */
.card {
  background: rgba(30,41,59,0.6); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; padding: 24px; margin-bottom: 20px;
}
.card::before {
  content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px;
  background: linear-gradient(90deg,#f7931a,#ffd700,#f7931a); opacity: 0.4;
}
.card { position: relative; overflow: hidden; }

/* Grid */
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
@media (max-width: 900px) { .grid-2 { grid-template-columns: 1fr; } }

/* Section Title */
.section-title {
  font-size: 1rem; font-weight: 600; color: #f1f5f9;
  margin-bottom: 12px; padding-bottom: 6px;
  border-bottom: 1px solid rgba(255,255,255,0.06);
}

/* Strategy List */
.strategy-item {
  background: rgba(255,255,255,0.03); border-radius: 12px; padding: 16px;
  margin-bottom: 10px; border: 1px solid rgba(255,255,255,0.06);
  cursor: pointer; transition: all 0.2s;
}
.strategy-item:hover { border-color: rgba(247,147,26,0.3); background: rgba(247,147,26,0.05); }
.strategy-item.active { border-color: #22c55e; background: rgba(34,197,94,0.08); }
.strategy-item .sname { font-size: 1rem; font-weight: 600; }
.strategy-item .sdesc { font-size: 0.82rem; color: #64748b; margin-top: 4px; }
.strategy-item .smeta { display: flex; gap: 16px; margin-top: 8px; font-size: 0.78rem; color: #475569; }
.strategy-badge {
  display: inline-block; font-size: 0.7rem; padding: 2px 8px; border-radius: 8px;
}
.badge-active { background: rgba(34,197,94,0.15); color: #22c55e; }
.badge-inactive { background: rgba(100,116,139,0.15); color: #64748b; }

/* Active Strategy Signal */
.signal-card { text-align: center; padding: 20px; }
.signal-display { font-size: 1.6rem; font-weight: 700; margin: 10px 0; }
.signal-display.strong_buy { color: #22c55e; }
.signal-display.buy { color: #84cc16; }
.signal-display.neutral { color: #3b82f6; }
.signal-display.sell { color: #f59e0b; }
.signal-display.strong_sell { color: #ef4444; }
.signal-score { font-size: 0.9rem; color: #94a3b8; display: flex; justify-content: center; gap: 20px; margin: 6px 0; }
.signal-summary { font-size: 0.82rem; color: #94a3b8; line-height: 1.6; margin-top: 8px; text-align: left; white-space: pre-wrap; }

/* Buttons */
.btn {
  display: inline-block; padding: 8px 18px; border-radius: 8px; font-size: 0.85rem;
  font-weight: 500; border: none; cursor: pointer; transition: all 0.2s;
  text-decoration: none;
}
.btn-primary { background: rgba(247,147,26,0.2); color: #f7931a; border: 1px solid rgba(247,147,26,0.3); }
.btn-primary:hover { background: rgba(247,147,26,0.3); }
.btn-danger { background: rgba(239,68,68,0.15); color: #ef4444; border: 1px solid rgba(239,68,68,0.2); }
.btn-danger:hover { background: rgba(239,68,68,0.25); }
.btn-success { background: rgba(34,197,94,0.15); color: #22c55e; border: 1px solid rgba(34,197,94,0.2); }
.btn-success:hover { background: rgba(34,197,94,0.25); }
.btn-sm { padding: 4px 12px; font-size: 0.78rem; }

/* Form */
.form-group { margin-bottom: 14px; }
.form-group label { display: block; font-size: 0.82rem; color: #94a3b8; margin-bottom: 4px; }
.form-group input, .form-group textarea, .form-group select {
  width: 100%; padding: 10px 14px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.1);
  background: rgba(15,23,42,0.8); color: #e2e8f0; font-size: 0.9rem; outline: none;
}
.form-group input:focus, .form-group textarea:focus, .form-group select:focus {
  border-color: #f7931a;
}
.form-group textarea { resize: vertical; min-height: 60px; font-family: inherit; }

.form-actions { display: flex; gap: 10px; margin-top: 16px; }
.form-row { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.form-row .form-group { flex: 1; min-width: 120px; }

/* Condition Card */
.condition-card {
  background: rgba(255,255,255,0.03); border-radius: 10px; padding: 14px;
  margin-bottom: 10px; border: 1px solid rgba(255,255,255,0.06);
}

/* Tags */
.tag {
  display: inline-block; padding: 3px 10px; border-radius: 6px; font-size: 0.72rem; font-weight: 500;
}
.tag-bull { background: rgba(34,197,94,0.12); color: #22c55e; }
.tag-bear { background: rgba(239,68,68,0.12); color: #ef4444; }
.tag-muted { background: rgba(100,116,139,0.12); color: #64748b; }

/* Tab buttons */
.tab-bar { display: flex; gap: 6px; margin-bottom: 16px; }
.tab-btn {
  padding: 6px 16px; border-radius: 8px; border: none; font-size: 0.82rem; cursor: pointer;
  background: rgba(255,255,255,0.05); color: #64748b; transition: all 0.2s;
}
.tab-btn:hover { background: rgba(247,147,26,0.1); color: #f7931a; }
.tab-btn.active { background: rgba(247,147,26,0.2); color: #f7931a; }
.tab-content { display: none; }
.tab-content.active { display: block; }

/* Empty state */
.empty-state { text-align: center; padding: 40px; color: #64748b; }
.empty-state .icon { font-size: 3rem; margin-bottom: 12px; }

/* Footer */
.footer { text-align: center; color: #475569; font-size: 0.75rem; padding: 24px 0 12px; border-top: 1px solid rgba(255,255,255,0.05); margin-top: 20px; }

/* Loading */
#loading { position: fixed; inset: 0; display: flex; align-items: center; justify-content: center; background: #0f172a; z-index: 9999; }
#loading .spinner { width: 36px; height: 36px; border: 3px solid rgba(247,147,26,0.2); border-top-color: #f7931a; border-radius: 50%; animation: spin .8s linear infinite; margin-bottom: 10px; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
</head>
<body>
<div id="loading"><div style="text-align:center"><div class="spinner"></div>加载中...</div></div>

<div class="container">
  <div class="nav">
    <a href="/">📊 监控面板</a>
    <a href="/strategies" class="active">🎯 策略管理</a>
  </div>

  <div class="page-header">
    <h1>🎯 交易策略管理</h1>
    <div class="subtitle">创建、编辑、激活交易策略 · 系统评估并生成信号</div>
  </div>

  <!-- Row: Active Signal + Quick Actions -->
  <div class="grid-2">
    <div class="card signal-card" id="active-signal-card">
      <div class="section-title">📡 激活策略信号</div>
      <div id="active-signal-content">
        <div style="color:#64748b;padding:20px">加载中...</div>
      </div>
    </div>
    <div class="card">
      <div class="section-title">⚡ 快捷操作</div>
      <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:8px">
        <button class="btn btn-primary" onclick="openNewStrategy()">＋ 新建策略</button>
        <button class="btn btn-success" onclick="loadDefaultStrategy('RSI超卖反弹')">📥 载入:RSI超卖反弹</button>
        <button class="btn btn-success" onclick="loadDefaultStrategy('趋势跟踪')">📥 载入:趋势跟踪</button>
        <button class="btn btn-success" onclick="loadDefaultStrategy('风险控制')">📥 载入:风险控制</button>
        <button class="btn btn-sm" onclick="refreshStrategies()">⟳ 刷新列表</button>
      </div>
      <div style="margin-top:12px;font-size:0.82rem;color:#475569">
        💡 基于技术指标和链上数据，自定义条件组合<br>
        多条件加权评分 → 买卖信号
      </div>
    </div>
  </div>

  <!-- Main: Strategy List + Editor -->
  <div class="grid-2">
    <!-- Left: Strategy List -->
    <div class="card">
      <div class="section-title">📋 我的策略 <span class="tag tag-muted" id="strategy-count">0</span></div>
      <div id="strategy-list"><div class="empty-state"><div class="icon">📭</div><p>暂无策略</p></div></div>
    </div>

    <!-- Right: Editor -->
    <div class="card" id="editor-card">
      <div class="section-title" id="editor-title">✏️ 新建策略</div>
      
      <div class="form-group">
        <label>策略名称 *</label>
        <input id="strategy-name" placeholder="例如: RSI超卖反弹" value="">
      </div>
      <div class="form-group">
        <label>描述</label>
        <textarea id="strategy-desc" placeholder="策略说明..."></textarea>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label>条件逻辑</label>
          <select id="strategy-logic">
            <option value="AND">AND (全部满足)</option>
            <option value="OR">OR (任一满足)</option>
          </select>
        </div>
        <div class="form-group">
          <label>最低触发分</label>
          <input id="strategy-min-score" type="number" step="0.5" value="1.5">
        </div>
      </div>

      <div class="section-title" style="font-size:0.9rem;margin-top:16px">📐 条件规则</div>
      <div id="conditions-container"></div>
      
      <button class="btn btn-sm" onclick="addCondition()" style="margin-top:8px">＋ 添加条件</button>

      <div class="form-actions">
        <button class="btn btn-primary" onclick="saveCurrentStrategy()">💾 保存策略</button>
        <button class="btn btn-success" onclick="activateAndSave()">🚀 保存并激活</button>
        <button class="btn btn-sm" onclick="clearEditor()">🗑 清空</button>
      </div>
    </div>
  </div>

  <div class="footer">
    ₿ Bitcoin Monitor · 策略基于多指标加权评分 · 仅供参考，不构成投资建议
  </div>
</div>

<script>
let allStrategies = [];
let editingName = null;
let indicatorRegistry = {};
let operators = [];

async function api(path, method='GET', body=null) {
  const opts = { method, headers: {} };
  if (body) { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
  const resp = await fetch(path, opts);
  return resp.json();
}

async function init() {
  try {
    const [indResp, opResp] = await Promise.all([api('/api/strategy/indicators'), api('/api/strategy/operators')]);
    indicatorRegistry = indResp;
    operators = opResp;
  } catch(e) {}
  await refreshStrategies();
  await refreshActiveSignal();
  document.getElementById('loading').style.display = 'none';
}

async function refreshStrategies() {
  const data = await api('/api/strategies');
  allStrategies = Array.isArray(data) ? data : [];
  document.getElementById('strategy-count').textContent = allStrategies.length;
  
  const list = document.getElementById('strategy-list');
  if (allStrategies.length === 0) {
    list.innerHTML = '<div class="empty-state"><div class="icon">📭</div><p>还没有策略，点击"新建策略"创建</p></div>';
    return;
  }
  
  list.innerHTML = allStrategies.map(s => `
    <div class="strategy-item ${s.active ? 'active' : ''}" onclick="editStrategy('${s.name}')">
      <div class="sname">${s.name} ${s.active ? '<span class="strategy-badge badge-active">✅ 激活中</span>' : '<span class="strategy-badge badge-inactive">未激活</span>'}</div>
      <div class="sdesc">${s.description || '无描述'}</div>
      <div class="smeta">
        <span>条件: ${s.condition_count}</span>
        <span>创建: ${s.created_at ? s.created_at.substring(0,10) : '—'}</span>
      </div>
    </div>
  `).join('');
}

async function refreshActiveSignal() {
  const result = await api('/api/strategy/evaluate');
  const content = document.getElementById('active-signal-content');
  
  if (result.error) {
    content.innerHTML = `<div style="color:#64748b;padding:10px">${result.summary || result.error}</div>`;
    return;
  }
  
  const signalLabels = { strong_buy:'🔴 强烈买入', buy:'🟡 买入', neutral:'⚪ 中性', sell:'🟠 卖出', strong_sell:'🔴 强烈卖出' };
  const signal = result.signal || 'neutral';
  
  content.innerHTML = `
    <div style="font-size:0.9rem;color:#94a3b8">${result.strategy_name}</div>
    <div class="signal-display ${signal}">${signalLabels[signal] || '⚪ 中性'}</div>
    <div class="signal-score">
      <span>评分: ${result.score ?? '—'}</span>
      <span>触发: ${result.satisfied_count ?? 0}/${result.total_count ?? 0}</span>
    </div>
    <div class="signal-summary">${result.summary || ''}</div>
  `;
}

function openNewStrategy() { clearEditor(); editingName = null; }

function clearEditor() {
  document.getElementById('strategy-name').value = '';
  document.getElementById('strategy-desc').value = '';
  document.getElementById('strategy-logic').value = 'AND';
  document.getElementById('strategy-min-score').value = '1.5';
  document.getElementById('conditions-container').innerHTML = '';
  document.getElementById('editor-title').textContent = '✏️ 新建策略';
  editingName = null;
}

async function editStrategy(name) {
  const s = await api('/api/strategy/' + encodeURIComponent(name));
  if (!s || s.error) return;
  
  document.getElementById('strategy-name').value = s.name || '';
  document.getElementById('strategy-desc').value = s.description || '';
  document.getElementById('strategy-logic').value = s.logic || 'AND';
  document.getElementById('strategy-min-score').value = s.min_score ?? 1.5;
  document.getElementById('editor-title').textContent = '✏️ 编辑: ' + s.name;
  editingName = s.name;
  
  const container = document.getElementById('conditions-container');
  container.innerHTML = '';
  (s.conditions || []).forEach(c => addCondition(c));
  if ((s.conditions || []).length === 0) addCondition();
}

function addCondition(data) {
  data = data || { id: 'c_' + Date.now(), label: '', indicator: '', operator: '>', value: 0, weight: 1 };
  const container = document.getElementById('conditions-container');
  const div = document.createElement('div');
  div.className = 'condition-card';
  div.id = 'cond-' + data.id;
  
  const indOpts = Object.entries(indicatorRegistry).map(([k,v]) => `<option value="${k}" ${k===data.indicator?'selected':''}>${v.label}</option>`).join('');
  const opOpts = operators.map(o => `<option value="${o.id}" ${o.id===data.operator?'selected':''}>${o.label}</option>`).join('');
  
  div.innerHTML = `
    <div class="form-row">
      <div class="form-group" style="flex:2">
        <label>指标</label>
        <select onchange="updateConditionLabel('${data.id}')" id="ind-${data.id}">${indOpts}</select>
      </div>
      <div class="form-group" style="flex:1">
        <label>条件</label>
        <select id="op-${data.id}">${opOpts}</select>
      </div>
      <div class="form-group" style="flex:1">
        <label>阈值</label>
        <input id="val-${data.id}" type="number" step="any" value="${data.value}">
      </div>
    </div>
    <div class="form-row">
      <div class="form-group" style="flex:2">
        <label>条件标签</label>
        <input id="lbl-${data.id}" value="${data.label || ''}" placeholder="例如: RSI超卖">
      </div>
      <div class="form-group" style="flex:1">
        <label>权重 ${data.weight >= 0 ? '📈' : '📉'}</label>
        <input id="wt-${data.id}" type="number" step="0.5" value="${data.weight}">
      </div>
      <div style="display:flex;align-items:flex-end;padding-bottom:4px">
        <button class="btn btn-sm btn-danger" onclick="removeCondition('${data.id}')">✕</button>
      </div>
    </div>
  `;
  container.appendChild(div);
}

function removeCondition(id) {
  const el = document.getElementById('cond-' + id);
  if (el) el.remove();
}

function updateConditionLabel(id) {
  const sel = document.getElementById('ind-' + id);
  const lbl = document.getElementById('lbl-' + id);
  if (sel && lbl && !lbl.value) {
    const info = indicatorRegistry[sel.value];
    if (info) lbl.value = info.label;
  }
}

function getConditions() {
  const cards = document.querySelectorAll('#conditions-container .condition-card');
  return Array.from(cards).map(card => {
    const id = card.id.replace('cond-', '');
    return {
      id: id,
      label: document.getElementById('lbl-' + id)?.value || '',
      indicator: document.getElementById('ind-' + id)?.value || '',
      operator: document.getElementById('op-' + id)?.value || '>',
      value: parseFloat(document.getElementById('val-' + id)?.value) || 0,
      weight: parseFloat(document.getElementById('wt-' + id)?.value) || 1,
    };
  }).filter(c => c.indicator);
}

async function saveCurrentStrategy() {
  const name = document.getElementById('strategy-name').value.trim();
  if (!name) { alert('请输入策略名称'); return; }
  
  const conditions = getConditions();
  if (conditions.length === 0) { alert('请至少添加一个条件'); return; }
  
  const strategy = {
    name: name,
    description: document.getElementById('strategy-desc').value.trim(),
    logic: document.getElementById('strategy-logic').value,
    min_score: parseFloat(document.getElementById('strategy-min-score').value) || 1.5,
    conditions: conditions,
  };
  
  const result = await api('/api/strategy', 'POST', strategy);
  if (result.error) { alert('保存失败: ' + result.error); return; }
  
  editingName = name;
  document.getElementById('editor-title').textContent = '✏️ 编辑: ' + name;
  await refreshStrategies();
}

async function activateAndSave() {
  await saveCurrentStrategy();
  const name = document.getElementById('strategy-name').value.trim();
  if (name) {
    await api('/api/strategy/' + encodeURIComponent(name) + '/activate', 'POST');
    await refreshStrategies();
    await refreshActiveSignal();
  }
}

async function deleteStrategy(name) {
  if (!confirm('确定删除策略「' + name + '」？')) return;
  await api('/api/strategy/' + encodeURIComponent(name), 'DELETE');
  if (editingName === name) clearEditor();
  await refreshStrategies();
  await refreshActiveSignal();
}

async function activateStrategy(name) {
  await api('/api/strategy/' + encodeURIComponent(name) + '/activate', 'POST');
  await refreshStrategies();
  await refreshActiveSignal();
}

async function loadDefaultStrategy(name) {
  clearEditor();
  const defaultStrats = await api('/api/strategy/defaults');
  const ds = defaultStrats.find(s => s.name === name);
  if (!ds) return;
  
  document.getElementById('strategy-name').value = ds.name;
  document.getElementById('strategy-desc').value = ds.description || '';
  document.getElementById('strategy-logic').value = ds.logic || 'AND';
  document.getElementById('strategy-min-score').value = ds.min_score ?? 1.5;
  document.getElementById('editor-title').textContent = '✏️ 编辑: ' + ds.name;
  
  const container = document.getElementById('conditions-container');
  container.innerHTML = '';
  (ds.conditions || []).forEach(c => addCondition(c));
}

// Deactivate
async function deactivateStrategy(name) {
  await api('/api/strategy/deactivate', 'POST');
  await refreshStrategies();
  await refreshActiveSignal();
}

init();
setInterval(refreshActiveSignal, 30000);  // Refresh signal every 30s
</script>
</body>
</html>"""

class DashboardHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the Bitcoin dashboard."""

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # ── Strategy pages ──
        if path == "/strategies" or path == "/strategies/":
            self._serve_strategy_html()
            return

        # ── Strategy API ──
        if path == "/api/strategies":
            self._send_json(list_strategies())
            return
        if path == "/api/strategy/defaults":
            self._send_json(get_default_strategies())
            return
        if path == "/api/strategy/indicators":
            self._send_json(INDICATOR_REGISTRY)
            return
        if path == "/api/strategy/operators":
            self._send_json(OPERATORS)
            return
        if path == "/api/strategy/evaluate":
            self._handle_strategy_evaluate()
            return
        if path.startswith("/api/strategy/"):
            parts = path.split("/")
            if len(parts) >= 4:
                name = urllib.parse.unquote(parts[3])
                if len(parts) == 4:
                    self._send_json(get_strategy(name) or {"error": "Not found"})
                    return
                elif len(parts) == 5 and parts[4] == "activate":
                    self._send_json(activate_strategy(name))
                    return

        # ── Main page ──
        if path == "/" or path == "/index.html":
            self._serve_html()
            return

        # ── Data API ──
        if path == "/api/data":
            self._serve_json()
            return

        self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # Read body
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b"{}"
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            data = {}

        # ── Strategy CRUD ──
        if path == "/api/strategy":
            result = save_strategy(data)
            self._send_json(result)
            return

        if path == "/api/strategy/deactivate":
            self._send_json(deactivate_strategy())
            return

        if path.startswith("/api/strategy/"):
            parts = path.split("/")
            if len(parts) >= 4:
                name = urllib.parse.unquote(parts[3])
                if len(parts) == 4:
                    # DELETE
                    self._send_json(delete_strategy(name))
                    return
                elif len(parts) == 5 and parts[4] == "activate":
                    self._send_json(activate_strategy(name))
                    return

        self._send_json({"error": "Not found"}, 404)

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/strategy/"):
            parts = path.split("/")
            if len(parts) >= 4:
                name = urllib.parse.unquote(parts[3])
                self._send_json(delete_strategy(name))
                return

        self._send_json({"error": "Not found"}, 404)

    # ── Helpers ──

    def _handle_strategy_evaluate(self):
        """Evaluate the active strategy against latest data."""
        # Load latest data
        raw_files = sorted(
            cfg.DATA_DIR.glob("raw_*.json"),
            key=lambda f: f.stat().st_mtime, reverse=True,
        )
        data = {}
        if raw_files:
            try:
                with open(raw_files[0], "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}

        # Initialize defaults if needed
        init_default_strategies()

        result = evaluate_active_strategy(data)
        self._send_json(result)

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str, ensure_ascii=False).encode("utf-8"))

    def _serve_html(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(DASHBOARD_HTML.encode("utf-8"))

    def _serve_strategy_html(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(STRATEGY_HTML.encode("utf-8"))

    def _serve_json(self):
        # Load latest raw data
        raw_files = sorted(
            cfg.DATA_DIR.glob("raw_*.json"),
            key=lambda f: f.stat().st_mtime, reverse=True,
        )
        data = {}
        if raw_files:
            try:
                with open(raw_files[0], "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                data = {"error": str(e)}

        data["_server_time"] = datetime.now(timezone.utc).isoformat()
        data["_data_file"] = raw_files[0].name if raw_files else None

        self._send_json(data)

    def log_message(self, format, *args):
        cfg.logger.info(f"[Dashboard] {args[0]} {args[1]} {args[2]}")


def run_server(port: int = PORT):
    server = HTTPServer((HOST, port), DashboardHandler)
    cfg.logger.info(f"✅ Bitcoin Dashboard started at http://{HOST}:{port}")
    cfg.logger.info(f"💡 在浏览器中打开: http://localhost:{port}")
    cfg.logger.info(f"📡 API 接口: http://localhost:{port}/api/data")
    cfg.logger.info(f"⏹  Ctrl+C 停止服务器")
    print(f"\n{'='*50}")
    print(f"  ₿ Bitcoin Dashboard Server")
    print(f"  URL:  http://localhost:{port}")
    print(f"  API:  http://localhost:{port}/api/data")
    print(f"  Stop: Ctrl+C")
    print(f"{'='*50}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped.")
        server.server_close()


if __name__ == "__main__":
    port = PORT
    if "--port" in sys.argv:
        idx = sys.argv.index("--port")
        if idx + 1 < len(sys.argv):
            port = int(sys.argv[idx + 1])
    run_server(port)
