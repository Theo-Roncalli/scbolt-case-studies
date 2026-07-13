#!/usr/bin/env bash

set -euo pipefail

APL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APL_DIR"

PARAMS="${PARAMS:-params-gsm.mk}"
INTERVAL="${TURBOSTAT_INTERVAL:-5}"
OUT_DIR="${SCBOLT_STATS_DIR:-$APL_DIR/stat}"
RUN_ID="$(date +%Y%m%d-%H%M%S)"

TURBOSTAT_LOG="$OUT_DIR/${RUN_ID}.turbostat.txt"
TURBOSTAT_SUMMARY="$OUT_DIR/${RUN_ID}.turbostat-summary.tsv"
PIPELINE_LOG="$OUT_DIR/${RUN_ID}.pipeline.log"
TIME_LOG="$OUT_DIR/${RUN_ID}.time.txt"
RAM_LOG="$OUT_DIR/${RUN_ID}.ram.tsv"
VMSTAT_LOG="$OUT_DIR/${RUN_ID}.vmstat.txt"
METADATA_LOG="$OUT_DIR/${RUN_ID}.metadata.txt"
SUMMARY_TSV="$OUT_DIR/${RUN_ID}.summary.tsv"

TARGETS=("$@")
if [ "${#TARGETS[@]}" -eq 0 ]; then
    TARGETS=(bn-submin)
fi

RESET_TARGETS_TEXT="${SCBOLT_RESET_TARGETS-load-matrix load-cc load-go}"
RESET_TARGETS=()
if [ -n "$RESET_TARGETS_TEXT" ]; then
    read -r -a RESET_TARGETS <<<"$RESET_TARGETS_TEXT"
fi
export SCBOLT_RESET_TARGETS_TEXT="$RESET_TARGETS_TEXT"

command -v scbolt >/dev/null
command -v turbostat >/dev/null
command -v python3 >/dev/null
test -x /usr/bin/time

mkdir -p "$OUT_DIR"

echo "[run] APL directory: $APL_DIR"
echo "[run] parameter file: $PARAMS"
echo "[run] targets: ${TARGETS[*]}"
echo "[run] reset targets: ${RESET_TARGETS[*]:-none}"
echo "[run] turbostat log: $TURBOSTAT_LOG"
echo "[run] pipeline log: $PIPELINE_LOG"
echo "[run] summary: $SUMMARY_TSV"

{
    echo "run_id: $RUN_ID"
    echo "timestamp: $(date --iso-8601=seconds)"
    echo "apl_dir: $APL_DIR"
    echo "params: $PARAMS"
    echo "targets: ${TARGETS[*]}"
    echo "reset_targets: ${RESET_TARGETS[*]:-none}"
    echo "conda_default_env: ${CONDA_DEFAULT_ENV:-}"
    echo "scbolt: $(command -v scbolt)"
    echo "make: $(command -v make)"
    echo
    echo "== scbolt version =="
    scbolt version 2>&1 || true
    echo
    echo "== python =="
    python3 --version 2>&1 || true
    echo
    echo "== kernel =="
    uname -a
    echo
    echo "== cpu =="
    lscpu 2>&1 || true
    echo
    echo "== memory before run =="
    free -h 2>&1 || true
    echo
    echo "== disk before run =="
    df -h "$APL_DIR" 2>&1 || true
    echo
    echo "== git =="
    git -C "$APL_DIR" rev-parse --show-toplevel 2>/dev/null || true
    git -C "$APL_DIR" rev-parse HEAD 2>/dev/null || true
    git -C "$APL_DIR" status --short 2>/dev/null || true
} >"$METADATA_LOG"

sudo -v

while true; do
    sudo -n true
    sleep 60
done &
SUDO_KEEPALIVE_PID="$!"

(
    printf "timestamp_epoch\ttimestamp\tmem_total_kb\tmem_available_kb\tmem_used_kb\tswap_total_kb\tswap_free_kb\tswap_used_kb\n"
    while true; do
        awk -v epoch="$(date +%s)" -v iso="$(date --iso-8601=seconds)" '
            /^MemTotal:/ { mem_total = $2 }
            /^MemAvailable:/ { mem_available = $2 }
            /^SwapTotal:/ { swap_total = $2 }
            /^SwapFree:/ { swap_free = $2 }
            END {
                print epoch "\t" iso "\t" mem_total "\t" mem_available "\t" \
                      mem_total - mem_available "\t" swap_total "\t" \
                      swap_free "\t" swap_total - swap_free
            }
        ' /proc/meminfo
        sleep "$INTERVAL"
    done
) >"$RAM_LOG" &
RAM_MONITOR_PID="$!"

if command -v vmstat >/dev/null; then
    vmstat -t "$INTERVAL" >"$VMSTAT_LOG" &
    VMSTAT_PID="$!"
else
    VMSTAT_PID=""
    echo "vmstat not found" >"$VMSTAT_LOG"
fi

sudo turbostat \
    --quiet \
    --Summary \
    --interval "$INTERVAL" \
    --out "$TURBOSTAT_LOG" &
TURBOSTAT_PID="$!"

cleanup() {
    if [ -n "${RAM_MONITOR_PID:-}" ] && kill -0 "$RAM_MONITOR_PID" 2>/dev/null; then
        kill "$RAM_MONITOR_PID" 2>/dev/null || true
        wait "$RAM_MONITOR_PID" 2>/dev/null || true
    fi

    if [ -n "${VMSTAT_PID:-}" ] && kill -0 "$VMSTAT_PID" 2>/dev/null; then
        kill "$VMSTAT_PID" 2>/dev/null || true
        wait "$VMSTAT_PID" 2>/dev/null || true
    fi

    if kill -0 "$TURBOSTAT_PID" 2>/dev/null; then
        sudo -n kill -INT "$TURBOSTAT_PID" 2>/dev/null || true
        wait "$TURBOSTAT_PID" 2>/dev/null || true
    fi

    if kill -0 "$SUDO_KEEPALIVE_PID" 2>/dev/null; then
        kill "$SUDO_KEEPALIVE_PID" 2>/dev/null || true
        wait "$SUDO_KEEPALIVE_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

summarize_turbostat() {
    python3 - "$TURBOSTAT_LOG" "$TURBOSTAT_SUMMARY" <<'PY' || true
from __future__ import annotations

import math
import statistics
import sys

infile, outfile = sys.argv[1], sys.argv[2]
header = None
values: dict[str, list[float]] = {}
header_markers = {"Avg_MHz", "Busy%", "Bzy_MHz", "PkgWatt", "CorWatt", "Pkg_J"}

with open(infile) as reader:
    for line in reader:
        tokens = line.split()
        if not tokens:
            continue
        if header_markers.intersection(tokens):
            header = tokens
            continue
        if header is None or len(tokens) != len(header):
            continue

        for name, token in zip(header, tokens):
            try:
                value = float(token)
            except ValueError:
                continue
            if math.isfinite(value):
                values.setdefault(name, []).append(value)

with open(outfile, "w") as writer:
    writer.write("metric\tn\tmean\tmin\tmax\n")
    for name in sorted(values):
        column = values[name]
        writer.write(
            f"{name}\t{len(column)}\t{statistics.fmean(column):.6g}\t"
            f"{min(column):.6g}\t{max(column):.6g}\n"
        )
PY
}

write_summary() {
    local status="$1"
    local start_epoch="$2"
    local end_epoch="$3"
    local start_iso="$4"
    local end_iso="$5"
    local wall_seconds="$((end_epoch - start_epoch))"
    local peak_mem_kb
    local peak_swap_kb
    local max_rss_kb
    local cpu_percent
    local user_seconds
    local system_seconds
    local fs_inputs
    local fs_outputs

    peak_mem_kb="$(awk 'NR > 1 && $5 > max { max = $5 } END { print max + 0 }' "$RAM_LOG")"
    peak_swap_kb="$(awk 'NR > 1 && $8 > max { max = $8 } END { print max + 0 }' "$RAM_LOG")"
    max_rss_kb="$(awk -F: '/Maximum resident set size/ { gsub(/^[ \t]+/, "", $2); print $2 }' "$TIME_LOG")"
    cpu_percent="$(awk -F: '/Percent of CPU/ { gsub(/^[ \t]+/, "", $2); print $2 }' "$TIME_LOG")"
    user_seconds="$(awk -F: '/User time/ { gsub(/^[ \t]+/, "", $2); print $2 }' "$TIME_LOG")"
    system_seconds="$(awk -F: '/System time/ { gsub(/^[ \t]+/, "", $2); print $2 }' "$TIME_LOG")"
    fs_inputs="$(awk -F: '/File system inputs/ { gsub(/^[ \t]+/, "", $2); print $2 }' "$TIME_LOG")"
    fs_outputs="$(awk -F: '/File system outputs/ { gsub(/^[ \t]+/, "", $2); print $2 }' "$TIME_LOG")"

    {
        printf "metric\tvalue\n"
        printf "run_id\t%s\n" "$RUN_ID"
        printf "status\t%s\n" "$status"
        printf "start\t%s\n" "$start_iso"
        printf "end\t%s\n" "$end_iso"
        printf "wall_seconds\t%s\n" "$wall_seconds"
        printf "params\t%s\n" "$PARAMS"
        printf "targets\t%s\n" "${TARGETS[*]}"
        printf "reset_targets\t%s\n" "${RESET_TARGETS[*]:-none}"
        printf "peak_system_mem_used_kb\t%s\n" "$peak_mem_kb"
        printf "peak_system_mem_used_gib\t%.3f\n" "$(awk -v x="$peak_mem_kb" 'BEGIN { print x / 1024 / 1024 }')"
        printf "peak_system_swap_used_kb\t%s\n" "$peak_swap_kb"
        printf "gnu_time_max_rss_kb\t%s\n" "${max_rss_kb:-}"
        printf "gnu_time_cpu_percent\t%s\n" "${cpu_percent:-}"
        printf "gnu_time_user_seconds\t%s\n" "${user_seconds:-}"
        printf "gnu_time_system_seconds\t%s\n" "${system_seconds:-}"
        printf "gnu_time_fs_inputs\t%s\n" "${fs_inputs:-}"
        printf "gnu_time_fs_outputs\t%s\n" "${fs_outputs:-}"
        printf "pipeline_log\t%s\n" "$PIPELINE_LOG"
        printf "time_log\t%s\n" "$TIME_LOG"
        printf "ram_log\t%s\n" "$RAM_LOG"
        printf "vmstat_log\t%s\n" "$VMSTAT_LOG"
        printf "turbostat_log\t%s\n" "$TURBOSTAT_LOG"
        printf "turbostat_summary\t%s\n" "$TURBOSTAT_SUMMARY"
        printf "metadata_log\t%s\n" "$METADATA_LOG"
    } >"$SUMMARY_TSV"
}

START_EPOCH="$(date +%s)"
START_ISO="$(date --iso-8601=seconds)"

set +e
{
    /usr/bin/time -v -o "$TIME_LOG" bash -s -- "$PARAMS" "${TARGETS[@]}" <<'PIPELINE'
set -euo pipefail

PARAMS="$1"
shift
RESET_TARGETS=()
if [ -n "${SCBOLT_RESET_TARGETS_TEXT:-}" ]; then
    read -r -a RESET_TARGETS <<<"$SCBOLT_RESET_TARGETS_TEXT"
fi

echo "[pipeline] scbolt init $PARAMS"
scbolt init "$PARAMS"

for target in "$@"; do
    if [ "${#RESET_TARGETS[@]}" -gt 0 ]; then
        echo "[pipeline] scbolt $target --reset-target ${RESET_TARGETS[*]}"
        scbolt "$target" --reset-target "${RESET_TARGETS[@]}"
    else
        echo "[pipeline] scbolt $target"
        scbolt "$target"
    fi
done
PIPELINE
} 2>&1 | tee "$PIPELINE_LOG"
PIPELINE_STATUS="${PIPESTATUS[0]}"
set -e

END_EPOCH="$(date +%s)"
END_ISO="$(date --iso-8601=seconds)"

cleanup
summarize_turbostat
write_summary "$PIPELINE_STATUS" "$START_EPOCH" "$END_EPOCH" "$START_ISO" "$END_ISO"

echo "[run] status: $PIPELINE_STATUS"
echo "[run] summary: $SUMMARY_TSV"

exit "$PIPELINE_STATUS"
