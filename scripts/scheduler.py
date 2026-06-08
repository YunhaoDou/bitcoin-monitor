"""
Bitcoin Monitor Scheduler.

Runs the pipeline on a schedule without external cron dependencies.
Supports three modes:
  1. Loop mode  : run every N hours in a background process
  2. One-shot   : run once and exit
  3. Daemon mode: continuous loop, writes PID file for management

Usage:
  python scripts/scheduler.py              # Run once (pipeline + dashboard)
  python scripts/scheduler.py --loop       # Run every 12h in a loop
  python scripts/scheduler.py --loop --interval 6  # Every 6h
  python scripts/scheduler.py --daemon     # Run as daemon (background)
  python scripts/scheduler.py --stop       # Stop daemon

Also:
  bash server.sh scheduler start|stop|status  # Manage via server.sh
"""
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import config as cfg

PID_FILE = Path(cfg.DATA_DIR) / ".scheduler.pid"
LOG_FILE = cfg.LOGS_DIR / "scheduler.log"
DEFAULT_INTERVAL = 12  # hours


# ── Logging ────────────────────────────────────────────────────────────

def log(msg: str):
    """Log to both file and stdout."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


# ── Pipeline Runner ────────────────────────────────────────────────────

def run_pipeline() -> dict:
    """Run the full pipeline: collect indicators + generate report."""
    log("🚀 启动数据采集管线...")
    start = time.time()

    # Import and run orchestrator
    from scripts.orchestrator import run_pipeline as run_orch
    try:
        results = run_orch()
        duration = time.time() - start
        log(f"✅ 管线完成 ({duration:.1f}s)")
        log(f"📊 {results.get('summary', '完成')}")
        return results
    except Exception as e:
        log(f"❌ 管线失败: {e}")
        return {"error": str(e)}


def run_both() -> dict:
    """Run pipeline + generate dashboard HTML."""
    results = run_pipeline()

    # Also generate dashboard
    try:
        from scripts.dashboard import run as gen_dashboard
        dash_path = gen_dashboard()
        if dash_path:
            log(f"📈 仪表盘已更新: {dash_path}")
    except Exception as e:
        log(f"⚠️ 仪表盘生成跳过: {e}")

    return results


# ── Scheduler Loop ─────────────────────────────────────────────────────

def scheduler_loop(interval_hours: int = DEFAULT_INTERVAL):
    """Run the pipeline in an infinite loop."""
    log(f"⏰ 调度器启动，每 {interval_hours}h 运行一次")
    log(f"📡 面板: http://localhost:8765")
    log(f"⏹  停止: python scripts/scheduler.py --stop")
    log("-" * 50)

    # Run once at start
    run_both()

    while True:
        next_run = interval_hours * 3600
        log(f"💤 等待 {interval_hours}h 后下次运行...")
        time.sleep(next_run)
        log("-" * 50)
        run_both()


# ── Daemon Management ─────────────────────────────────────────────────

def start_daemon(interval_hours: int = DEFAULT_INTERVAL):
    """Start the scheduler as a background daemon process."""
    if PID_FILE.exists():
        try:
            with open(PID_FILE) as f:
                old_pid = int(f.read().strip())
            os.kill(old_pid, 0)  # Check if running
            log(f"❌ 调度器已在运行 (PID: {old_pid})")
            return False
        except (OSError, ValueError):
            PID_FILE.unlink(missing_ok=True)

    # Fork into background
    pid = os.fork()
    if pid > 0:
        # Parent process
        log(f"✅ 调度器已启动 (PID: {pid})")
        with open(PID_FILE, "w") as f:
            f.write(str(pid))
        return True

    # Child process (daemon)
    # Detach from parent
    os.setsid()
    # Redirect stdout/stderr to log
    sys.stdout = open(LOG_FILE, "a", encoding="utf-8")
    sys.stderr = sys.stdout

    try:
        scheduler_loop(interval_hours)
    except Exception as e:
        log(f"💥 调度器崩溃: {e}")
    finally:
        PID_FILE.unlink(missing_ok=True)


def stop_daemon():
    """Stop the running daemon."""
    if not PID_FILE.exists():
        log("❌ 调度器未运行")
        return False

    try:
        with open(PID_FILE) as f:
            pid = int(f.read().strip())
        os.kill(pid, signal.SIGTERM)
        log(f"🛑 调度器已停止 (PID: {pid})")
        PID_FILE.unlink(missing_ok=True)
        return True
    except ProcessLookupError:
        log("⚠️ 进程已不存在，清理PID文件")
        PID_FILE.unlink(missing_ok=True)
        return False
    except ValueError:
        log("⚠️ PID文件损坏，清理")
        PID_FILE.unlink(missing_ok=True)
        return False


def daemon_status() -> str:
    """Check if daemon is running."""
    if not PID_FILE.exists():
        return "stopped"

    try:
        with open(PID_FILE) as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)
        return f"running (PID: {pid})"
    except (OSError, ValueError):
        PID_FILE.unlink(missing_ok=True)
        return "stopped"


# ── CLI ────────────────────────────────────────────────────────────────

def print_help():
    print("""
Bitcoin Monitor Scheduler

USAGE:
  python scripts/scheduler.py              Run once (pipeline + dashboard)
  python scripts/scheduler.py --loop       Run every 12h in foreground loop
  python scripts/scheduler.py --loop --interval 6  Every 6h
  python scripts/scheduler.py --daemon     Start background daemon
  python scripts/scheduler.py --stop       Stop daemon
  python scripts/scheduler.py --status     Check daemon status
  python scripts/scheduler.py --help       Show this help

EXAMPLES:
  # Start daemon (runs every 12h in background)
  python scripts/scheduler.py --daemon

  # Check status
  python scripts/scheduler.py --status

  # Stop daemon
  python scripts/scheduler.py --stop

  # Run once with custom interval (for testing)
  python scripts/scheduler.py --loop --interval 0.5  # Every 30 min

MANUAL CRON (alternative):
  0 */12 * * * cd ~/bitcoin-monitor && python scripts/scheduler.py
""")


if __name__ == "__main__":
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        print_help()
        sys.exit(0)

    if "--status" in args:
        status = daemon_status()
        print(f"调度器状态: {status}")
        sys.exit(0)

    if "--stop" in args:
        stop_daemon()
        sys.exit(0)

    if "--daemon" in args:
        interval = DEFAULT_INTERVAL
        for i, a in enumerate(args):
            if a == "--interval" and i + 1 < len(args):
                interval = float(args[i + 1])
        start_daemon(interval)
        sys.exit(0)

    if "--loop" in args:
        interval = DEFAULT_INTERVAL
        for i, a in enumerate(args):
            if a == "--interval" and i + 1 < len(args):
                interval = float(args[i + 1])
        log(f"🔁 循环模式，间隔 {interval}h")
        scheduler_loop(interval)
        sys.exit(0)

    # Default: run once
    run_both()
