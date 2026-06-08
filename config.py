"""
Bitcoin Monitor Configuration
"""
import os
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(os.path.expanduser("~/bitcoin-monitor"))
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = DATA_DIR / "reports"
ARCHIVE_DIR = DATA_DIR / "archive"
LOGS_DIR = BASE_DIR / "logs"
SCRIPTS_DIR = BASE_DIR / "scripts"

for d in [DATA_DIR, REPORTS_DIR, ARCHIVE_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# API 配置
COINGECKO_BASE = "https://api.coingecko.com/api/v3"
BLOCKCHAIN_INFO_BASE = "https://blockchain.info"

# 监控参数
LOOKBACK_DAYS = 90  # 指标回看天数
FETCH_INTERVAL_HOURS = 12  # 自动更新间隔

# 报告输出
REPORT_TEMPLATE_FILE = SCRIPTS_DIR / "report_template.md"

# Logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "bitcoin_monitor.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("bitcoin_monitor")
