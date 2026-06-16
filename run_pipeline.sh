#!/bin/bash
# Pipeline 启动脚本
# 用法: bash run_pipeline.sh [--no-resume] [--debug]

export PATH="/usr/local/texlive/2026/bin/x86_64-linux:$PATH"
cd /home/bigboss/code/paper-writing-assistant

# v14: 显式从 ~/.bashrc 提取 API keys（非交互 shell 的 source ~/.bashrc 会被 PS1 检查拦截）
for _kv in ALI_TOKEN_PLAN_API_KEY ALI_API_KEY ZHIPU_GLM_API_KEY GLM_CODING_PLAN_API_KEY OPENAI_API_KEY; do
    _val=$(grep "^export ${_kv}=" ~/.bashrc 2>/dev/null | head -1 | sed "s/^export ${_kv}=//" | tr -d '"' | tr -d "'")
    [ -n "$_val" ] && export "$_kv=$_val"
done

LOG_FILE="output/pipeline_run.log"
mkdir -p output

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting pipeline..." > "$LOG_FILE"
echo "Args: $@" >> "$LOG_FILE"

/home/bigboss/miniconda3/envs/py311/bin/python -u pipeline.py "$@" >> "$LOG_FILE" 2>&1

EXIT_CODE=$?
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Pipeline exited with code $EXIT_CODE" >> "$LOG_FILE"
exit $EXIT_CODE
