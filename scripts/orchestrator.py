#!/usr/bin/env python3
"""
Bitcoin Monitor Pipeline Orchestrator.

Runs the full pipeline:
  1. Collect Indicators → Fetch on-chain, price, technical data
  2. Compute Risk Score → Multi-indicator consensus
  3. Generate Report → Chinese markdown analysis
  4. Summary → Print result for cron delivery
"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import config as cfg
from scripts.indicators import collect_all, save_raw_data
from scripts.report_generator import run as run_report_generator


def run_pipeline():
    """Run the complete Bitcoin monitoring pipeline."""
    start_time = datetime.now()
    cfg.logger.info(f"{'='*60}")
    cfg.logger.info(f"BITCOIN MONITOR PIPELINE STARTED at {start_time.isoformat()}")
    cfg.logger.info(f"{'='*60}")

    results = {
        "started_at": start_time.isoformat(),
        "completed_at": "",
        "data_collected": False,
        "report_generated": False,
        "errors": [],
        "summary": "",
    }

    # Step 1: Collect indicators
    cfg.logger.info("\n[Step 1/2] Collecting indicators...")
    try:
        data = collect_all()
        save_raw_data(data)
        results["data_collected"] = True
        score = data.get("risk", {}).get("score", 50)
        cfg.logger.info(f"✓ Data collected. Risk score: {score}/100")
    except Exception as e:
        cfg.logger.error(f"Step 1 failed: {e}")
        results["errors"].append(f"Indicator Collection: {e}")
        return results

    # Brief pause
    time.sleep(1)

    # Step 2: Generate report
    cfg.logger.info("\n[Step 2/2] Generating report...")
    try:
        report_result = run_report_generator(data=data)
        results["report_generated"] = True
        cfg.logger.info(f"✓ Report: {report_result['path']}")
    except Exception as e:
        cfg.logger.error(f"Step 2 failed: {e}")
        results["errors"].append(f"Report Generation: {e}")

    # Summary
    end_time = datetime.now()
    results["completed_at"] = end_time.isoformat()
    duration = (end_time - start_time).total_seconds()

    risk_label = data.get("risk", {}).get("label", "N/A")
    signals = data.get("risk", {}).get("signals", [])
    btc_price = data.get("price", {}).get("price_usd", "N/A")

    summary_parts = [
        f"BTC ${btc_price:,.0f}" if isinstance(btc_price, (int, float)) else f"BTC {btc_price}",
    ]
    if data.get("risk", {}).get("score") is not None:
        summary_parts.append(f"风险评分 {data['risk']['score']}/100")
        summary_parts.append(risk_label)
    if signals:
        summary_parts.append(f"信号: {'; '.join(signals[:2])}")

    results["summary"] = " | ".join(summary_parts)
    results["duration_seconds"] = round(duration, 1)

    cfg.logger.info(f"\n{'='*60}")
    cfg.logger.info(f"PIPELINE COMPLETED in {duration:.1f}s")
    cfg.logger.info(f"Results: {results['summary']}")
    cfg.logger.info(f"{'='*60}")

    return results


def print_report_paths():
    """Print paths of generated reports for cron delivery."""
    md_files = sorted(cfg.REPORTS_DIR.glob("btc_monitor_*.md"),
                      key=lambda f: f.stat().st_mtime, reverse=True)

    if md_files:
        print(f"\n📊 最新报告：")
        for f in md_files[:3]:
            size = f.stat().st_size
            print(f"  📄 {f.name} ({size:,} bytes)")
        print(f"\n报告目录：{cfg.REPORTS_DIR}")
    else:
        print("\n暂无报告")


if __name__ == "__main__":
    print("=== Bitcoin Monitor Pipeline ===")
    results = run_pipeline()

    print(f"\n{'='*60}")
    print(f"✅ 结果：{results['summary']}")
    print(f"⏱ 耗时：{results.get('duration_seconds', 0)}s")

    if results.get("errors"):
        print(f"\n❌ 错误：")
        for e in results["errors"]:
            print(f"  - {e}")

    print_report_paths()
    print(f"\n项目目录：{cfg.BASE_DIR}")
