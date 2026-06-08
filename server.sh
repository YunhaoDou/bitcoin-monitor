#!/bin/bash
# Bitcoin Monitor Manager
# Usage: ./server.sh <command> [options]
#
# Commands:
#   dashboard start|stop|status|restart  — 管理可视化面板
#   scheduler start|stop|status          — 管理后台调度器
#   run                                  — 立即运行一次管线
#   help                                 — 显示帮助

PORT=8765
BASE_DIR="$HOME/bitcoin-monitor"
DASH_PID="/tmp/bitcoin-dashboard.pid"
DASH_LOG="$BASE_DIR/logs/server.log"
SCRIPT_DIR="$BASE_DIR/scripts"

# ── Dashboard ──────────────────────────────────────────────────────────

dashboard_start() {
  if [ -f "$DASH_PID" ] && kill -0 $(cat "$DASH_PID") 2>/dev/null; then
    echo "❌ 面板已在运行 (PID: $(cat $DASH_PID))"
    return 1
  fi

  cd "$BASE_DIR"
  nohup python3 "$SCRIPT_DIR/server.py" --port "$PORT" > "$DASH_LOG" 2>&1 &
  PID=$!
  echo $PID > "$DASH_PID"

  sleep 2
  if kill -0 $PID 2>/dev/null; then
    echo "✅ 面板已启动"
    echo "   http://localhost:$PORT"
    echo "   PID: $PID"
  else
    echo "❌ 启动失败，检查日志: $DASH_LOG"
    return 1
  fi
}

dashboard_stop() {
  if [ ! -f "$DASH_PID" ]; then
    echo "❌ 面板未运行"
    return 1
  fi
  PID=$(cat "$DASH_PID")
  kill $PID 2>/dev/null
  rm -f "$DASH_PID"
  echo "🛑 面板已停止 (PID: $PID)"
}

dashboard_status() {
  if [ -f "$DASH_PID" ] && kill -0 $(cat "$DASH_PID") 2>/dev/null; then
    echo "✅ 面板运行中 (PID: $(cat $DASH_PID))"
    echo "   http://localhost:$PORT"
  else
    echo "❌ 面板未运行"
    [ -f "$DASH_PID" ] && rm -f "$DASH_PID"
  fi
}

# ── Scheduler ──────────────────────────────────────────────────────────

scheduler_start() {
  cd "$BASE_DIR"
  python3 "$SCRIPT_DIR/scheduler.py" --daemon
}

scheduler_stop() {
  cd "$BASE_DIR"
  python3 "$SCRIPT_DIR/scheduler.py" --stop
}

scheduler_status() {
  cd "$BASE_DIR"
  python3 "$SCRIPT_DIR/scheduler.py" --status
}

# ── Help ───────────────────────────────────────────────────────────────

print_help() {
  echo ""
  echo "Bitcoin Monitor — 管理脚本"
  echo ""
  echo "用法: ./server.sh <command> [subcommand]"
  echo ""
  echo "面板管理:"
  echo "  dashboard start     启动可视化面板 (localhost:$PORT)"
  echo "  dashboard stop      停止面板"
  echo "  dashboard status    查看面板状态"
  echo "  dashboard restart   重启面板"
  echo ""
  echo "调度器管理:"
  echo "  scheduler start     启动后台调度器 (每12h自动采集)"
  echo "  scheduler stop      停止调度器"
  echo "  scheduler status    查看调度器状态"
  echo ""
  echo "其他:"
  echo "  run                 立即运行一次管线 (采集+报告+仪表盘)"
  echo "  help                显示此帮助"
  echo ""
  echo "示例:"
  echo "  ./server.sh dashboard start     # 启动面板"
  echo "  ./server.sh scheduler start     # 启动自动采集"
  echo "  ./server.sh run                 # 立即采集一次"
  echo ""
}

# ── Main ───────────────────────────────────────────────────────────────

CMD="${1:-help}"
SUB="${2:-}"

case "$CMD" in
  dashboard)
    case "$SUB" in
      start)   dashboard_start ;;
      stop)    dashboard_stop ;;
      status)  dashboard_status ;;
      restart) dashboard_stop; sleep 1; dashboard_start ;;
      *)       echo "用法: ./server.sh dashboard start|stop|status|restart" ;;
    esac
    ;;
  scheduler)
    case "$SUB" in
      start)   scheduler_start ;;
      stop)    scheduler_stop ;;
      status)  scheduler_status ;;
      *)       echo "用法: ./server.sh scheduler start|stop|status" ;;
    esac
    ;;
  run)
    cd "$BASE_DIR"
    python3 "$SCRIPT_DIR/scheduler.py"
    ;;
  help|--help|-h)
    print_help
    ;;
  status)
    echo "=== 面板状态 ==="
    dashboard_status
    echo ""
    echo "=== 调度器状态 ==="
    scheduler_status
    ;;
  *)
    print_help
    ;;
esac
