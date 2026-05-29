#!/bin/bash
# Pipeline 启动脚本
# 用法: bash run_pipeline.sh [--no-resume] [--debug]

export PATH="/usr/local/texlive/2026/bin/x86_64-linux:$PATH"
cd /home/bigboss/code/paper-writing-assistant

LOG_FILE="output/pipeline_run.log"
mkdir -p output

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting pipeline..." > "$LOG_FILE"
echo "Args: $@" >> "$LOG_FILE"

/home/bigboss/miniconda3/envs/py311/bin/python -u pipeline.py "$@" >> "$LOG_FILE" 2>&1

EXIT_CODE=$?
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Pipeline exited with code $EXIT_CODE" >> "$LOG_FILE"
exit $EXIT_CODE
