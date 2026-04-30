#!/usr/bin/env bash
# Spin up SummaryBot (:9001), MoodReader (:9002), DataWizard (:9003) in
# parallel under one shell. Logs are interleaved.
set -euo pipefail

cd "$(dirname "$0")/.."

trap 'kill 0' EXIT INT TERM

python -m agora_x402.cli run agents/summarybot/agent.py  --port 9001 &
python -m agora_x402.cli run agents/moodreader/agent.py  --port 9002 &
python -m agora_x402.cli run agents/datawizard/agent.py  --port 9003 &

wait
