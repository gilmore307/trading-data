#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
mkdir -p logs/data-fetch

PY="./.venv/bin/python"
CANDLE="scripts/data/fetch_okx_history_candles.py"

run_candle() {
  local inst_id="$1"
  local out_path="$2"
  local log_path="$3"
  echo "[$(date -Is)] start candle ${inst_id}" | tee -a "$log_path"
  "$PY" "$CANDLE" \
    --inst-id "$inst_id" \
    --bar 1m \
    --start 2022-01-01T00:00:00Z \
    --output "$out_path" \
    --resume \
    --sleep-seconds 0.35 \
    --progress-every 200 \
    --checkpoint-every 25 \
    >> "$log_path" 2>&1
  echo "[$(date -Is)] done candle ${inst_id}" | tee -a "$log_path"
  sleep 8
}

run_candle "BTC-USDT-SWAP" "data/raw/BTC-USDT-SWAP/candles/BTC-USDT-SWAP.jsonl" "logs/data-fetch/btc_usdt_swap_1m_20220101_now.log"
run_candle "BTC-USDT" "data/raw/BTC-USDT/candles/BTC-USDT.jsonl" "logs/data-fetch/btc_usdt_1m_20220101_now.log"
run_candle "ETH-USDT-SWAP" "data/raw/ETH-USDT-SWAP/candles/ETH-USDT-SWAP.jsonl" "logs/data-fetch/eth_usdt_swap_1m_20220101_now.log"
run_candle "ETH-USDT" "data/raw/ETH-USDT/candles/ETH-USDT.jsonl" "logs/data-fetch/eth_usdt_1m_20220101_now.log"
run_candle "SOL-USDT-SWAP" "data/raw/SOL-USDT-SWAP/candles/SOL-USDT-SWAP.jsonl" "logs/data-fetch/sol_usdt_swap_1m_20220101_now.log"
run_candle "SOL-USDT" "data/raw/SOL-USDT/candles/SOL-USDT.jsonl" "logs/data-fetch/sol_usdt_1m_20220101_now.log"

echo "[$(date -Is)] initial history backfill finished" | tee -a logs/data-fetch/backfill-master.log
