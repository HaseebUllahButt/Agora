#!/usr/bin/env bash
# Start the marketplace + x402 facilitator on :8000
set -euo pipefail

cd "$(dirname "$0")/.."

# Use uvicorn directly so --reload works in dev.
exec python -m uvicorn facilitator.api:app --host 0.0.0.0 --port "${PORT:-8000}" --reload
