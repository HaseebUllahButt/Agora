#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
LOG_DIR="$ROOT_DIR/.run/logs"
PID_DIR="$ROOT_DIR/.run/pids"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "❌ Missing Python at $PYTHON_BIN"
  echo "Create the venv first: python3 -m venv $ROOT_DIR/.venv && $ROOT_DIR/.venv/bin/pip install -r $ROOT_DIR/requirements.txt"
  exit 1
fi

mkdir -p "$LOG_DIR" "$PID_DIR"

start_service() {
  local name="$1"
  local app="$2"
  local port="$3"
  local pid_file="$PID_DIR/${name}.pid"
  local log_file="$LOG_DIR/${name}.log"

  if [[ -f "$pid_file" ]]; then
    local old_pid
    old_pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [[ -n "$old_pid" ]] && kill -0 "$old_pid" 2>/dev/null; then
      echo "⏭️  $name already running (pid $old_pid)"
      return
    fi
    rm -f "$pid_file"
  fi

  (
    cd "$ROOT_DIR"
    nohup "$PYTHON_BIN" -m uvicorn "$app" --host 0.0.0.0 --port "$port" >"$log_file" 2>&1 &
    echo $! >"$pid_file"
  )

  local new_pid
  new_pid="$(cat "$pid_file")"
  sleep 0.3
  if kill -0 "$new_pid" 2>/dev/null; then
    echo "✅ $name started on :$port (pid $new_pid)"
  else
    echo "❌ Failed to start $name on :$port"
    echo "   Check logs: $log_file"
    rm -f "$pid_file"
  fi
}

start_service "web_search" "agents.web_search_agent:app" 8001
start_service "extractor" "agents.extractor_agent:app" 8002
start_service "summarizer" "agents.summarizer_agent:app" 8003
start_service "analyst" "agents.analyst_agent:app" 8004
start_service "formatter" "agents.formatter_agent:app" 8005
start_service "consultancy" "agents.consultancy_agent:app" 8006
start_service "api" "api.main:app" 8000

echo
echo "Backend startup finished."
echo "Logs: $LOG_DIR"
echo "PIDs: $PID_DIR"