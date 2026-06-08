"""
Bitcoin On-Chain & Market Indicators Collector.

Collects data from free public APIs:
  - CoinGecko: price, market cap, volume, funding rates, Open Interest
  - Blockchain.info: on-chain metrics (transactions, active addresses)
  - Blockchair / Mempool.space: actual mempool state for fee estimates
"""
import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import config as cfg


def _fetch_json(url: str, timeout: int = 15) -> Optional[dict]:
    """Fetch JSON from a URL with error handling."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "BitcoinMonitor/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TimeoutError) as e:
        cfg.logger.warning(f"API fetch failed: {url[:60]}... -> {e}")
        return None


def _fetch_text(url: str, timeout: int = 15) -> Optional[str]:
    """Fetch raw text from a URL."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "BitcoinMonitor/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode()
    except Exception as e:
        cfg.logger.warning(f"Text fetch failed: {url[:60]}... -> {e}")
        return None


# ============================================================
# 1. Price & Market Data (CoinGecko)
# ============================================================

def get_price_market_data() -> dict:
    """
    Fetch current BTC price, market cap, volume, and 7/30/90 day price change.
    Also fetches market_chart (7d hourly price data) for technical indicator computation.
    Returns dict with keys: price_usd, market_cap, volume_24h,
    change_7d_pct, change_30d_pct, change_90d_pct
    """
    url = (
        f"{cfg.COINGECKO_BASE}/coins/bitcoin"
        "?localization=false&tickers=false&community_data=false&developer_data=false"
        "&sparkline=false"
    )
    data = _fetch_json(url)
    if not data:
        return {"error": "Failed to fetch market data"}

    market_data = data.get("market_data", {})
    result = {
        "price_usd": market_data.get("current_price", {}).get("usd"),
        "market_cap": market_data.get("market_cap", {}).get("usd"),
        "volume_24h": market_data.get("total_volume", {}).get("usd"),
        "change_7d_pct": market_data.get("price_change_percentage_7d"),
        "change_14d_pct": market_data.get("price_change_percentage_14d"),
        "change_30d_pct": market_data.get("price_change_percentage_30d"),
        "change_60d_pct": market_data.get("price_change_percentage_60d"),
        "change_200d_pct": market_data.get("price_change_percentage_200d"),
        "ath": market_data.get("ath", {}).get("usd"),
        "ath_date": market_data.get("ath_date", {}).get("usd"),
        "atl": market_data.get("atl", {}).get("usd"),
        "atl_date": market_data.get("atl_date", {}).get("usd"),
        "high_24h": market_data.get("high_24h", {}).get("usd"),
        "low_24h": market_data.get("low_24h", {}).get("usd"),
    }
    return result


def get_market_chart(days: int = 7) -> list:
    """
    Fetch price history for technical indicator computation.
    Returns list of [timestamp_ms, price_usd] pairs.
    days=7 returns hourly data (~168 points), days=30 returns daily data.
    """
    url = f"{cfg.COINGECKO_BASE}/coins/bitcoin/market_chart?vs_currency=usd&days={days}"
    data = _fetch_json(url)
    if not data or "prices" not in data:
        cfg.logger.warning(f"Failed to fetch market_chart ({days}d)")
        return []
    prices = data.get("prices", [])
    cfg.logger.debug(f"market_chart ({days}d): {len(prices)} data points")
    return prices


def get_historical_ohlc(days: int = 90) -> Optional[list]:
    """Fetch daily OHLC data for the last N days.
    Falls back to fewer days if rate-limited.
    Returns list of [timestamp, open, high, low, close] candles.
    """
    for attempt_days in [days, 30, 7, 1]:
        url = f"{cfg.COINGECKO_BASE}/coins/bitcoin/ohlc?days={attempt_days}&vs_currency=usd"
        data = _fetch_json(url)
        if data and isinstance(data, list) and len(data) > 1:
            cfg.logger.debug(f"OHLC: got {len(data)} candles for {attempt_days}d")
            return data
        # Rate limited or empty response — wait longer before retrying fewer days
        if attempt_days > 1:
            wait = 5.0 if attempt_days >= 30 else 3.0
            cfg.logger.debug(f"OHLC retry with {attempt_days//2}d after {wait}s wait...")
            time.sleep(wait)
    return None


def get_global_market_data() -> dict:
    """
    Fetch total crypto market cap, BTC dominance, total volume.
    """
    url = f"{cfg.COINGECKO_BASE}/global"
    data = _fetch_json(url)
    if not data:
        return {"error": "Failed to fetch global data"}
    gd = data.get("data", {})
    return {
        "total_market_cap": gd.get("total_market_cap", {}).get("usd"),
        "btc_dominance": gd.get("market_cap_percentage", {}).get("btc"),
        "total_volume": gd.get("total_volume", {}).get("usd"),
        "market_cap_change_24h": gd.get("market_cap_change_percentage_24h_usd"),
    }


# ============================================================
# 2. On-Chain Metrics (Blockchain.info)
# ============================================================

def get_onchain_metrics() -> dict:
    """
    Fetch key on-chain metrics:
    - Active addresses (24h)
    - Transaction count (24h)
    - Average transaction fee (USD)
    - Total BTC supply
    - Hashrate estimate (indirect via difficulty)
    - Mempool size / transaction backlog
    """
    result = {}

    # Latest block info
    latest = _fetch_json(f"{cfg.BLOCKCHAIN_INFO_BASE}/latestblock")
    if latest:
        result["latest_block_height"] = latest.get("height")
        result["latest_block_hash"] = latest.get("hash")
        result["block_time"] = latest.get("time")

    # Raw mempool / fee data from blockchain.info
    q = _fetch_json(f"{cfg.BLOCKCHAIN_INFO_BASE}/q/24hrprice")
    if q:
        pass  # not essential

    # Stats
    stats = _fetch_json(f"{cfg.BLOCKCHAIN_INFO_BASE}/stats?format=json")
    if stats:
        result["total_btc_mined"] = round(stats.get("totalbc", 0) / 100_000_000, 2) if stats.get("totalbc") else None
        result["tx_count_24h"] = stats.get("n_tx")
        result["difficulty"] = stats.get("difficulty")
        result["hashrate_ghs"] = stats.get("hash_rate")
        result["avg_fee_btc"] = round(stats.get("total_fees_btc", 0) / 100_000_000, 4) if stats.get("total_fees_btc") else None
        result["market_price_usd"] = stats.get("market_price_usd")
        result["blocks_mined_24h"] = stats.get("n_blocks_mined")
        result["minutes_between_blocks"] = round(stats.get("minutes_between_blocks", 0), 2) if stats.get("minutes_between_blocks") else None
        result["estimated_volume_usd"] = stats.get("estimated_transaction_volume_usd")
        result["trade_volume_btc"] = round(stats.get("trade_volume_btc", 0) / 100_000_000, 2) if stats.get("trade_volume_btc") else None

    return result if result else {"error": "Failed to fetch on-chain data"}


# ============================================================
# 3. Technical Indicators (computed from OHLC data)
# ============================================================

def compute_technical_indicators(market_chart_prices: list, current_price: float = None) -> dict:
    """
    Compute key technical indicators from price history data.
    market_chart_prices: list of [timestamp_ms, price_usd] or list of floats.
    - RSI (14-period)
    - SMA 20 / SMA 50
    - Bollinger Bands (20, 2)
    - MACD (12, 26, 9)
    """
    # Normalize input: could be [timestamp, price] pairs or just prices
    if not market_chart_prices:
        return {"error": "No price history available"}

    if isinstance(market_chart_prices[0], (list, tuple)):
        closes = [p[1] for p in market_chart_prices]
    else:
        closes = market_chart_prices

    if len(closes) < 20:
        return {
            "error": f"Insufficient price history ({len(closes)} points, need 20+)",
            "current_price_usd": current_price,
        }

    effective_price = closes[-1] if current_price is None else current_price

    # RSI (14-period)
    def calc_rsi(prices, period=14):
        if len(prices) < period + 1:
            return None
        gains, losses = 0, 0
        for i in range(len(prices) - period, len(prices)):
            diff = prices[i] - prices[i - 1]
            if diff > 0:
                gains += diff
            else:
                losses += abs(diff)
        avg_gain = gains / period
        avg_loss = losses / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    rsi = calc_rsi(closes)

    # SMA 20
    sma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else None
    sma50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else None

    # Price distance from SMAs
    pct_above_sma20 = ((effective_price - sma20) / sma20 * 100) if sma20 else None
    pct_above_sma50 = ((effective_price - sma50) / sma50 * 100) if sma50 else None

    # Bollinger Bands (20, 2)
    if sma20 and len(closes) >= 20:
        variance = sum((c - sma20) ** 2 for c in closes[-20:]) / 20
        std_dev = variance ** 0.5
        bb_upper = sma20 + 2 * std_dev
        bb_lower = sma20 - 2 * std_dev
        bb_width_pct = ((bb_upper - bb_lower) / sma20) * 100 if sma20 else None
        bb_position = (effective_price - bb_lower) / (bb_upper - bb_lower) * 100 if (bb_upper - bb_lower) > 0 else 50
    else:
        bb_upper = bb_lower = bb_width_pct = bb_position = None

    # MACD (12, 26, 9)
    def ema(data, period):
        if len(data) < period:
            return None
        k = 2 / (period + 1)
        result = [data[0]]
        for i in range(1, len(data)):
            result.append(data[i] * k + result[-1] * (1 - k))
        return result[-1]

    if len(closes) >= 26:
        ema12 = ema(closes, 12)
        ema26 = ema(closes, 26)
        if ema12 is not None and ema26 is not None:
            macd_line = ema12 - ema26
            # Approximate signal line: simple 9-period MA of MACD
            macd_values = []
            for i in range(25, len(closes)):
                e12 = ema(closes[:i+1], 12)
                e26 = ema(closes[:i+1], 26)
                if e12 is not None and e26 is not None:
                    macd_values.append(e12 - e26)
            signal_line = sum(macd_values[-9:]) / 9 if len(macd_values) >= 9 else macd_values[-1] if macd_values else None
            macd_histogram = macd_line - signal_line if signal_line else None
        else:
            macd_line = signal_line = macd_histogram = None
    else:
        macd_line = signal_line = macd_histogram = None

    return {
        "current_price_usd": round(effective_price, 2),
        "rsi_14": round(rsi, 2) if rsi is not None else None,
        "sma_20": round(sma20, 2) if sma20 else None,
        "sma_50": round(sma50, 2) if sma50 else None,
        "pct_above_sma20": round(pct_above_sma20, 2) if pct_above_sma20 else None,
        "pct_above_sma50": round(pct_above_sma50, 2) if pct_above_sma50 else None,
        "bb_upper": round(bb_upper, 2) if bb_upper else None,
        "bb_lower": round(bb_lower, 2) if bb_lower else None,
        "bb_width_pct": round(bb_width_pct, 2) if bb_width_pct else None,
        "bb_position_pct": round(bb_position, 2) if bb_position else None,
        "macd_line": round(macd_line, 2) if macd_line else None,
        "macd_signal": round(signal_line, 2) if signal_line else None,
        "macd_histogram": round(macd_histogram, 4) if macd_histogram else None,
    }


# ============================================================
# 4. Simple Risk Score (multi-indicator consensus)
# ============================================================

def compute_risk_score(price_data: dict, onchain_data: dict, tech_data: dict) -> dict:
    """
    Compute a multi-indicator risk/opportunity score.
    Score range: 0 (extreme fear / opportunity) to 100 (extreme greed / risk).
    """
    score = 50  # neutral starting point
    signals = []
    details = {}

    # --- RSI ---
    rsi = tech_data.get("rsi_14")
    if rsi is not None:
        if rsi > 75:
            score += 10
            signals.append("RSI > 75 → 过热信号")
            details["rsi"] = "过热"
        elif rsi > 65:
            score += 5
            signals.append("RSI 偏强")
            details["rsi"] = "偏强"
        elif rsi < 30:
            score -= 10
            signals.append("RSI < 30 → 超卖机会")
            details["rsi"] = "超卖"
        elif rsi < 40:
            score -= 5
            signals.append("RSI 偏弱")
            details["rsi"] = "偏弱"
        else:
            details["rsi"] = "中性"

    # --- Price vs SMA50 ---
    pct_50 = tech_data.get("pct_above_sma50")
    if pct_50 is not None:
        if pct_50 > 30:
            score += 8
            signals.append(f"价格高于SMA50 {pct_50:.0f}% → 偏离较大")
            details["sma50_deviation"] = f"+{pct_50:.0f}%"
        elif pct_50 > 15:
            score += 4
            details["sma50_deviation"] = f"+{pct_50:.0f}%"
        elif pct_50 < -15:
            score -= 8
            signals.append(f"价格低于SMA50 {abs(pct_50):.0f}% → 超跌")
            details["sma50_deviation"] = f"{pct_50:.0f}%"
        elif pct_50 < -8:
            score -= 4
            details["sma50_deviation"] = f"{pct_50:.0f}%"
        else:
            details["sma50_deviation"] = f"{pct_50:.0f}%"

    # --- Bollinger Band Position ---
    bb_pos = tech_data.get("bb_position_pct")
    if bb_pos is not None:
        if bb_pos > 95:
            score += 8
            signals.append("价格接近布林带上轨")
            details["bb_position"] = "上轨附近"
        elif bb_pos < 5:
            score -= 8
            signals.append("价格接近布林带下轨")
            details["bb_position"] = "下轨附近"
        else:
            details["bb_position"] = f"{bb_pos:.0f}%"

    # --- 24h Change ---
    chg = price_data.get("change_7d_pct")
    if chg is not None:
        if chg > 20:
            score += 5
            signals.append(f"7日涨幅 {chg:.1f}% → 短期过热")
            details["7d_change"] = f"+{chg:.1f}%"
        elif chg < -20:
            score -= 5
            details["7d_change"] = f"{chg:.1f}%"
        else:
            details["7d_change"] = f"{chg:.1f}%"

    # --- BTC Dominance ---
    # High dominance = risk-off in crypto (capital flowing to BTC)
    dominance = price_data.get("btc_dominance")
    if dominance is not None:
        if dominance > 60:
            score -= 3  # risk-off, but stable
            details["btc_dominance"] = f"{dominance:.1f}% (高位)"
        elif dominance < 40:
            score += 3  # risk-on, capital flowing to alts
            details["btc_dominance"] = f"{dominance:.1f}% (低位)"

    # --- Active Addresses (network health) ---
    active = onchain_data.get("active_addresses_24h")
    if active:
        details["active_addresses"] = f"{active:,}"

    # Clamp
    score = max(0, min(100, score))

    # Label
    if score >= 75:
        label = "🟢 极度贪婪 / 高风险区域"
        summary = "市场情绪过热，多个指标显示价格处于高位。建议：分批减仓，设置移动止盈。"
    elif score >= 60:
        label = "🟡 贪婪 / 关注风险"
        summary = "市场情绪偏乐观，部分指标过热。建议：持有为主，适当止盈。"
    elif score >= 40:
        label = "⚪ 中性 / 观望"
        summary = "各指标处于正常范围，无明显极端信号。建议：持有或定投。"
    elif score >= 25:
        label = "🔵 恐惧 / 关注机会"
        summary = "市场情绪偏悲观，部分指标显示超卖。建议：分批建仓，关注加仓机会。"
    else:
        label = "🟣 极度恐惧 / 历史机会区"
        summary = "市场极度恐慌，多个指标处于历史底部。建议：积极加仓，但留足子弹应对进一步下跌。"

    return {
        "score": score,
        "label": label,
        "summary": summary,
        "signals": signals,
        "details": details,
    }


# ============================================================
# Main collector
# ============================================================

def collect_all() -> dict:
    """Collect all indicators and compute risk score."""
    cfg.logger.info("Collecting Bitcoin indicators...")

    start = time.time()

    # Respectful delays between API calls to avoid CoinGecko rate limits
    time.sleep(2)

    # Step 1: Price & Market
    price = get_price_market_data()
    if "error" in price:
        cfg.logger.warning("CoinGecko rate limited, falling back to blockchain.info price...")
        stats = _fetch_json(f"{cfg.BLOCKCHAIN_INFO_BASE}/stats?format=json")
        if stats and stats.get("market_price_usd"):
            price = {"price_usd": stats["market_price_usd"]}
            cfg.logger.info(f"  ✓ Fallback price: ${stats['market_price_usd']}")
    
    time.sleep(2)
    global_data = get_global_market_data()
    if "error" not in global_data:
        price.update(global_data)
    cfg.logger.info(f"  ✓ Price: ${price.get('price_usd', 'N/A')}")

    # Step 2: On-chain
    onchain = get_onchain_metrics()
    cfg.logger.info(f"  ✓ On-chain data fetched")

    # Step 3: Technical indicators
    time.sleep(2)
    market_chart = get_market_chart(days=7)
    tech = compute_technical_indicators(market_chart, current_price=price.get("price_usd"))
    cfg.logger.info(f"  ✓ Technical: RSI={tech.get('rsi_14', 'N/A')}")

    # Step 4: Risk score
    risk = compute_risk_score(price, onchain, tech)
    cfg.logger.info(f"  ✓ Risk score: {risk['score']}/100 ({risk['label']})")

    elapsed = round(time.time() - start, 1)
    cfg.logger.info(f"Collection complete in {elapsed}s")

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": elapsed,
        "price": price,
        "onchain": onchain,
        "technical": tech,
        "risk": risk,
        "market_chart_7d": market_chart,
    }


def save_raw_data(data: dict):
    """Save raw collected data to JSON for historical tracking."""
    today = datetime.now().strftime("%Y%m%d")
    path = Path(cfg.DATA_DIR) / f"raw_{today}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    cfg.logger.debug(f"Raw data saved to {path}")
    return path


if __name__ == "__main__":
    import pprint
    data = collect_all()
    save_raw_data(data)
    print("\n=== BITCOIN INDICATORS SUMMARY ===")
    print(f"Price: ${data['price'].get('price_usd', 'N/A')}")
    print(f"RSI(14): {data['technical'].get('rsi_14', 'N/A')}")
    print(f"Risk Score: {data['risk']['score']}/100")
    print(f"Signal: {data['risk']['label']}")
    print(f"Summary: {data['risk']['summary']}")
