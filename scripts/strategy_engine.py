"""
Strategy Engine for Bitcoin Monitor.

Defines strategy format, storage, and evaluation logic.

Strategy Structure:
  {
    "name": str,              # Unique strategy name
    "description": str,       # Human-readable description
    "created_at": str,        # ISO timestamp
    "updated_at": str,        # ISO timestamp
    "active": bool,           # Only one strategy can be active at a time
    "logic": "AND"|"OR",     # How conditions combine
    "min_score": float,       # Minimum weighted score to trigger a signal
    "conditions": [           # List of conditions to evaluate
      {
        "id": str,            # Unique condition ID
        "label": str,         # Human-readable label (e.g. "RSI超卖")
        "indicator": str,     # Dot-path to indicator (e.g. "technical.rsi_14")
        "operator": str,      # One of: "<", "<=", ">", ">=", "==", "!=", "between"
        "value": float|list,  # Threshold value; list for "between" [min, max]
        "weight": float       # Weight for scoring (positive=bullish, negative=bearish)
      }
    ]
  }

Evaluation Output:
  {
    "strategy_name": str,
    "timestamp": str,
    "active": bool,
    "score": float,          # Weighted sum of all triggered conditions
    "max_possible_score": float,  # Sum of positive weights
    "min_possible_score": float,  # Sum of negative weights
    "signal": "strong_buy"|"buy"|"neutral"|"sell"|"strong_sell",
    "triggered": [            # List of triggered conditions
      {
        "id": str,
        "label": str,
        "actual_value": float,
        "threshold": float,
        "weight": float,
        "satisfied": bool,
        "direction": "bullish"|"bearish"
      }
    ],
    "summary": str           # Human-readable summary in Chinese
  }
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import config as cfg

STRATEGIES_DIR = cfg.DATA_DIR / "strategies"
STRATEGIES_DIR.mkdir(parents=True, exist_ok=True)
ACTIVE_LINK = STRATEGIES_DIR / ".active"


# ── Available Indicators (for the strategy editor) ─────────────────────

INDICATOR_REGISTRY = {
    # Price
    "price.price_usd": {"label": "当前价格 (USD)", "type": "number", "source": "CoinGecko"},
    "price.change_7d_pct": {"label": "7日涨跌幅 (%)", "type": "percent", "source": "CoinGecko"},
    "price.change_30d_pct": {"label": "30日涨跌幅 (%)", "type": "percent", "source": "CoinGecko"},
    "price.change_60d_pct": {"label": "60日涨跌幅 (%)", "type": "percent", "source": "CoinGecko"},
    "price.btc_dominance": {"label": "BTC市占率 (%)", "type": "percent", "source": "CoinGecko"},
    "price.market_cap": {"label": "市值 (USD)", "type": "number", "source": "CoinGecko"},
    "price.volume_24h": {"label": "24h交易量 (USD)", "type": "number", "source": "CoinGecko"},
    "price.ath": {"label": "历史最高价 (USD)", "type": "number", "source": "CoinGecko"},
    
    # Technical
    "technical.rsi_14": {"label": "RSI (14)", "type": "rsi", "source": "计算值"},
    "technical.sma_20": {"label": "SMA 20 (USD)", "type": "number", "source": "计算值"},
    "technical.sma_50": {"label": "SMA 50 (USD)", "type": "number", "source": "计算值"},
    "technical.pct_above_sma20": {"label": "价格偏离SMA20 (%)", "type": "percent", "source": "计算值"},
    "technical.pct_above_sma50": {"label": "价格偏离SMA50 (%)", "type": "percent", "source": "计算值"},
    "technical.bb_upper": {"label": "布林带上轨 (USD)", "type": "number", "source": "计算值"},
    "technical.bb_lower": {"label": "布林带下轨 (USD)", "type": "number", "source": "计算值"},
    "technical.bb_width_pct": {"label": "布林带宽度 (%)", "type": "percent", "source": "计算值"},
    "technical.bb_position_pct": {"label": "布林带位置 (%)", "type": "percent_0_100", "source": "计算值"},
    "technical.macd_line": {"label": "MACD快线", "type": "number", "source": "计算值"},
    "technical.macd_signal": {"label": "MACD信号线", "type": "number", "source": "计算值"},
    "technical.macd_histogram": {"label": "MACD柱", "type": "number", "source": "计算值"},
    
    # On-chain
    "onchain.tx_count_24h": {"label": "24h交易数", "type": "number", "source": "Blockchain.info"},
    "onchain.blocks_mined_24h": {"label": "24h出块数", "type": "number", "source": "Blockchain.info"},
    "onchain.minutes_between_blocks": {"label": "出块间隔 (分钟)", "type": "number", "source": "Blockchain.info"},
    "onchain.difficulty": {"label": "挖矿难度", "type": "number", "source": "Blockchain.info"},
    "onchain.total_btc_mined": {"label": "已挖BTC", "type": "number", "source": "Blockchain.info"},
    
    # Risk
    "risk.score": {"label": "综合风险评分", "type": "percent_0_100", "source": "多指标"},
}

OPERATORS = [
    {"id": "<", "label": "小于"},
    {"id": "<=", "label": "小于等于"},
    {"id": ">", "label": "大于"},
    {"id": ">=", "label": "大于等于"},
    {"id": "==", "label": "等于"},
    {"id": "!=", "label": "不等于"},
    {"id": "between", "label": "介于"},
]


# ── Storage ────────────────────────────────────────────────────────────

def _strategy_path(name: str) -> Path:
    """Get the file path for a strategy by name."""
    safe = name.replace(" ", "_").replace("/", "_")
    return STRATEGIES_DIR / f"{safe}.json"


def list_strategies() -> list[dict]:
    """List all saved strategies (without full condition details)."""
    strategies = []
    for f in sorted(STRATEGIES_DIR.glob("*.json")):
        if f.name == ".active" or f.name.startswith("."):
            continue
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            strategies.append({
                "name": data.get("name", f.stem),
                "description": data.get("description", ""),
                "active": data.get("active", False),
                "created_at": data.get("created_at", ""),
                "updated_at": data.get("updated_at", ""),
                "condition_count": len(data.get("conditions", [])),
            })
        except (json.JSONDecodeError, OSError):
            continue
    return strategies


def get_strategy(name: str) -> Optional[dict]:
    """Load a full strategy by name."""
    path = _strategy_path(name)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def save_strategy(strategy: dict) -> dict:
    """Create or update a strategy. Returns the saved strategy."""
    now = datetime.now(timezone.utc).isoformat()
    
    # Validate required fields
    if not strategy.get("name"):
        return {"error": "策略名称不能为空"}
    
    existing = get_strategy(strategy["name"])
    
    strategy["updated_at"] = now
    if not existing:
        strategy["created_at"] = now
    
    # Ensure conditions have IDs
    for i, cond in enumerate(strategy.get("conditions", [])):
        if not cond.get("id"):
            cond["id"] = f"c_{i}"
    
    path = _strategy_path(strategy["name"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(strategy, f, indent=2, ensure_ascii=False)
    
    return get_strategy(strategy["name"]) or strategy


def delete_strategy(name: str) -> dict:
    """Delete a strategy."""
    path = _strategy_path(name)
    if not path.exists():
        return {"error": f"策略 '{name}' 不存在"}
    
    # Deactivate if active
    strategy = get_strategy(name)
    if strategy and strategy.get("active"):
        deactivate_strategy()
    
    path.unlink()
    return {"success": True, "name": name}


def activate_strategy(name: str) -> dict:
    """Activate a strategy (deactivates all others)."""
    strategy = get_strategy(name)
    if not strategy:
        return {"error": f"策略 '{name}' 不存在"}
    
    # Deactivate all strategies
    for s in list_strategies():
        s_full = get_strategy(s["name"])
        if s_full and s_full.get("active"):
            s_full["active"] = False
            with open(_strategy_path(s["name"]), "w", encoding="utf-8") as f:
                json.dump(s_full, f, indent=2, ensure_ascii=False)
    
    # Activate target
    strategy["active"] = True
    with open(_strategy_path(name), "w", encoding="utf-8") as f:
        json.dump(strategy, f, indent=2, ensure_ascii=False)
    
    # Write active link
    ACTIVE_LINK.write_text(name, encoding="utf-8")
    
    return {"success": True, "name": name, "active": True}


def deactivate_strategy() -> dict:
    """Deactivate the current active strategy."""
    active_name = get_active_strategy_name()
    if active_name:
        strategy = get_strategy(active_name)
        if strategy:
            strategy["active"] = False
            with open(_strategy_path(active_name), "w", encoding="utf-8") as f:
                json.dump(strategy, f, indent=2, ensure_ascii=False)
    if ACTIVE_LINK.exists():
        ACTIVE_LINK.unlink()
    return {"success": True, "active": False}


def get_active_strategy_name() -> Optional[str]:
    """Get the name of the currently active strategy."""
    if ACTIVE_LINK.exists():
        return ACTIVE_LINK.read_text(encoding="utf-8").strip()
    # Fallback: scan all strategies
    for s in list_strategies():
        if s.get("active"):
            return s["name"]
    return None


def get_active_strategy() -> Optional[dict]:
    """Get the full active strategy."""
    name = get_active_strategy_name()
    if name:
        return get_strategy(name)
    return None


# ── Evaluation ─────────────────────────────────────────────────────────

def _resolve_indicator(data: dict, dot_path: str) -> Optional[float]:
    """Resolve a dot-path like 'technical.rsi_14' from the data dict."""
    parts = dot_path.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def evaluate_condition(condition: dict, data: dict) -> dict:
    """
    Evaluate a single condition against the data.
    Returns dict with: id, label, actual_value, threshold, weight, satisfied, direction
    """
    indicator_path = condition.get("indicator", "")
    operator = condition.get("operator", ">")
    threshold = condition.get("value", 0)
    weight = condition.get("weight", 1)
    
    actual_value = _resolve_indicator(data, indicator_path)
    
    satisfied = False
    direction = "bullish" if weight > 0 else "bearish"
    
    if actual_value is not None:
        try:
            actual = float(actual_value)
            if operator == ">":
                satisfied = actual > float(threshold)
            elif operator == ">=":
                satisfied = actual >= float(threshold)
            elif operator == "<":
                satisfied = actual < float(threshold)
            elif operator == "<=":
                satisfied = actual <= float(threshold)
            elif operator == "==":
                satisfied = abs(actual - float(threshold)) < 0.001
            elif operator == "!=":
                satisfied = abs(actual - float(threshold)) >= 0.001
            elif operator == "between":
                if isinstance(threshold, (list, tuple)) and len(threshold) == 2:
                    satisfied = float(threshold[0]) <= actual <= float(threshold[1])
        except (ValueError, TypeError):
            satisfied = False
    else:
        actual_value = None
    
    return {
        "id": condition.get("id", ""),
        "label": condition.get("label", indicator_path),
        "actual_value": actual_value,
        "threshold": threshold,
        "weight": weight,
        "satisfied": satisfied,
        "direction": direction,
    }


def _get_signal(score: float, max_pos: float, min_neg: float, min_score: float) -> str:
    """Determine the signal level based on score thresholds.
    
    Positive score = bullish direction, negative score = bearish direction.
    Strength is based on % of max_possible (for bullish) or % of min_possible (for bearish).
    """
    if max_pos == 0 and min_neg == 0:
        return "neutral"
    
    # Bullish signal
    if score > 0:
        if max_pos == 0:
            return "neutral"
        pct = score / max_pos
        if pct < 0.3 or score < min_score:
            return "neutral"
        elif pct >= 0.7:
            return "strong_buy"
        else:
            return "buy"
    
    # Bearish signal
    elif score < 0:
        if min_neg == 0:
            return "neutral"
        pct = score / min_neg  # negative / negative = positive
        if pct < 0.3 or abs(score) < min_score:
            return "neutral"
        elif pct >= 0.7:
            return "strong_sell"
        else:
            return "sell"
    
    return "neutral"


def evaluate_strategy(strategy: dict, data: dict) -> dict:
    """
    Evaluate a full strategy against the latest market data.
    Returns evaluation results with score, signal, and triggered conditions.
    """
    if not strategy:
        return {"error": "No strategy provided"}
    
    conditions = strategy.get("conditions", [])
    logic = strategy.get("logic", "AND").upper()
    min_score = strategy.get("min_score", 1.0)
    
    # Evaluate all conditions
    results = [evaluate_condition(c, data) for c in conditions]
    
    # Calculate scores
    score = 0.0
    max_possible = 0.0
    min_possible = 0.0
    triggered = []
    
    for r in results:
        triggered.append(r)
        if r["satisfied"]:
            score += r["weight"]
        if r["weight"] > 0:
            max_possible += r["weight"]
        else:
            min_possible += r["weight"]
    
    # Determine signal
    signal = _get_signal(score, max_possible, min_possible, min_score)
    
    # Generate Chinese summary
    summary = _generate_summary(signal, score, triggered, strategy.get("name", ""))
    
    return {
        "strategy_name": strategy["name"],
        "strategy_description": strategy.get("description", ""),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "active": strategy.get("active", False),
        "score": round(score, 2),
        "max_possible_score": max_possible,
        "min_possible_score": min_possible,
        "signal": signal,
        "triggered": triggered,
        "satisfied_count": sum(1 for r in results if r["satisfied"]),
        "total_count": len(results),
        "summary": summary,
    }


def _generate_summary(signal: str, score: float, triggered: list, name: str) -> str:
    """Generate a human-readable Chinese summary of the evaluation."""
    # Count bullish/bearish triggered
    bullish = [r for r in triggered if r["satisfied"] and r["direction"] == "bullish"]
    bearish = [r for r in triggered if r["satisfied"] and r["direction"] == "bearish"]
    
    lines = []
    
    signal_map = {
        "strong_buy": "🟢 强烈买入信号",
        "buy": "🟡 买入信号",
        "neutral": "⚪ 无明确信号",
        "sell": "🟠 卖出信号",
        "strong_sell": "🔴 强烈卖出信号",
    }
    lines.append(f"策略「{name}」评估: {signal_map.get(signal, '未知')} (综合评分: {score})")
    
    if triggered:
        satisfied = [r for r in triggered if r["satisfied"]]
        if satisfied:
            lines.append(f"触发条件 ({len(satisfied)}/{len(triggered)}):")
            for r in satisfied:
                emoji = "📈" if r["direction"] == "bullish" else "📉"
                actual = f"{r['actual_value']:.2f}" if r['actual_value'] is not None else "N/A"
                lines.append(f"  {emoji} {r['label']}: 当前={actual}, 阈值={r['threshold']}")
    
    return "\n".join(lines)


def evaluate_active_strategy(data: dict) -> dict:
    """Evaluate the currently active strategy against the data."""
    strategy = get_active_strategy()
    if not strategy:
        return {
            "error": "没有激活的策略",
            "signal": "neutral",
            "summary": "⚠️ 请先在策略页面创建并激活一个策略",
        }
    return evaluate_strategy(strategy, data)


def get_default_strategies() -> list[dict]:
    """Return built-in example strategies."""
    return [
        {
            "name": "RSI超卖反弹",
            "description": "当RSI进入超卖区域且价格接近布林带下轨时，产生买入信号。适合震荡市场。",
            "logic": "AND",
            "min_score": 2.0,
            "conditions": [
                {
                    "id": "rsi_buy",
                    "label": "RSI超卖 (<35)",
                    "indicator": "technical.rsi_14",
                    "operator": "<",
                    "value": 35,
                    "weight": 2.0
                },
                {
                    "id": "bb_buy",
                    "label": "布林带下轨附近 (<30%)",
                    "indicator": "technical.bb_position_pct",
                    "operator": "<",
                    "value": 30,
                    "weight": 1.5
                },
                {
                    "id": "sma_buy",
                    "label": "价格低于SMA50",
                    "indicator": "technical.pct_above_sma50",
                    "operator": "<",
                    "value": 0,
                    "weight": 1.0
                }
            ]
        },
        {
            "name": "趋势跟踪",
            "description": "当价格在SMA50上方且MACD多头时，跟随趋势。适合趋势市场。",
            "logic": "AND",
            "min_score": 2.0,
            "conditions": [
                {
                    "id": "price_above_sma",
                    "label": "价格高于SMA50",
                    "indicator": "technical.pct_above_sma50",
                    "operator": ">",
                    "value": 0,
                    "weight": 1.5
                },
                {
                    "id": "macd_bull",
                    "label": "MACD多头 (快线>信号线)",
                    "indicator": "technical.macd_histogram",
                    "operator": ">",
                    "value": 0,
                    "weight": 1.5
                },
                {
                    "id": "rsi_mid",
                    "label": "RSI中性偏强 (>55)",
                    "indicator": "technical.rsi_14",
                    "operator": ">",
                    "value": 55,
                    "weight": 1.0
                }
            ]
        },
        {
            "name": "风险控制",
            "description": "当多个过热信号同时出现时，产生卖出信号。用于风险管理。",
            "logic": "OR",
            "min_score": 1.5,
            "conditions": [
                {
                    "id": "rsi_overheat",
                    "label": "RSI过热 (>75)",
                    "indicator": "technical.rsi_14",
                    "operator": ">",
                    "value": 75,
                    "weight": -2.0
                },
                {
                    "id": "bb_overheat",
                    "label": "布林带上轨 (>90%)",
                    "indicator": "technical.bb_position_pct",
                    "operator": ">",
                    "value": 90,
                    "weight": -1.5
                },
                {
                    "id": "macd_bear",
                    "label": "MACD空头 (快线<信号线)",
                    "indicator": "technical.macd_histogram",
                    "operator": "<",
                    "value": 0,
                    "weight": -1.5
                },
                {
                    "id": "risk_high",
                    "label": "综合风险分>70",
                    "indicator": "risk.score",
                    "operator": ">",
                    "value": 70,
                    "weight": -1.0
                }
            ]
        },
    ]


def init_default_strategies():
    """Initialize built-in strategies if none exist."""
    existing = list_strategies()
    if existing:
        return
    
    for s in get_default_strategies():
        save_strategy(s)
    
    cfg.logger.info(f"已初始化 {len(get_default_strategies())} 个默认策略")


if __name__ == "__main__":
    import pprint
    
    # Test: initialize and evaluate
    init_default_strategies()
    
    print("\n=== 默认策略列表 ===")
    for s in list_strategies():
        print(f"  {s['name']}: {s['description'][:40]}... ({s['condition_count']} conditions)")
    
    # Try to load latest data
    import json
    raw_files = sorted(cfg.DATA_DIR.glob("raw_*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    if raw_files:
        with open(raw_files[0]) as f:
            data = json.load(f)
        
        print("\n=== 策略评估 ===")
        for s in list_strategies():
            strat = get_strategy(s["name"])
            result = evaluate_strategy(strat, data)
            print(f"\n  [{s['name']}]")
            print(f"  Signal: {result['signal']} | Score: {result['score']} | 触发: {result['satisfied_count']}/{result['total_count']}")
            for r in result["triggered"]:
                if r["satisfied"]:
                    print(f"    ✓ {r['label']}: {r['actual_value']} (权重:{r['weight']})")
