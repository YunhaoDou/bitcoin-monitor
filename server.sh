#!/bin/bash
# Bitcoin Dashboard Server Manager
# Usage: ./server.sh start|stop|status|restart

PORT=8765
PID_FILE="/tmp/bitcoin-dashboard.pid"
LOG_FILE="$HOME/bitcoin-monitor/logs/server.log"

start() {
  if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
    echo "❌ 服务器已在运行 (PID: $(cat $PID_FILE))"
    return 1
  fi

  cd "$HOME/bitcoin-monitor"
  nohup python3 scripts/server.py --port "$PORT" > "$LOG_FILE" 2>&1 &
  PID=$!
  echo $PID > "$PID_FILE"

  sleep 2
  if kill -0 $PID 2>/dev/null; then
    echo "✅ Bitcoin Dashboard 已启动"
    echo "   URL:  http://localhost:$PORT"
    echo "   PID:  $PID"
  else
    echo "❌ 启动失败，检查日志: $LOG_FILE"
    return 1
  fi
}

stop() {
  if [ ! -f "$PID_FILE" ]; then
    echo "❌ 服务器未运行"
    return 1
  fi

  PID=$(cat "$PID_FILE")
  kill $PID 2>/dev/null
  rm -f "$PID_FILE"
  echo "🛑 服务器已停止 (PID: $PID)"
}

status() {
  if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
    echo "✅ 运行中 (PID: $(cat $PID_FILE))"
    echo "   http://localhost:$PORT"
  else
    echo "❌ 未运行"
    if [ -f "$PID_FILE" ]; then rm -f "$PID_FILE"; fi
  fi
}

case "${1:-status}" in
  start)   start ;;
  stop)    stop ;;
  restart) stop; sleep 1; start ;;
  status|*) status ;;
esac
