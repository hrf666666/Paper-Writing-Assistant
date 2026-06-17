#!/bin/bash
export PATH="/usr/local/texlive/2026/bin/x86_64-linux:$PATH"
cd /home/bigboss/code/paper-writing-assistant

for _kv in ALI_TOKEN_PLAN_API_KEY ALI_API_KEY ZHIPU_GLM_API_KEY GLM_CODING_PLAN_API_KEY OPENAI_API_KEY; do
    _val=$(grep "^export ${_kv}=" ~/.bashrc 2>/dev/null | head -1 | sed "s/^export ${_kv}=//" | tr -d '"' | tr -d "'")
    [ -n "$_val" ] && export "$_kv=$_val"
done

# 日志写到固定路径（不受 output/ 归档影响）
LOG_FILE="/tmp/pipeline_run.log"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting pipeline... Args: $@" > "$LOG_FILE"
/home/bigboss/miniconda3/envs/py311/bin/python -u pipeline.py "$@" >> "$LOG_FILE" 2>&1
EXIT_CODE=$?
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Pipeline exited with code $EXIT_CODE" >> "$LOG_FILE"
# 拷贝到 output（pipeline 跑完后 output/ 是最新的）
cp "$LOG_FILE" output/pipeline_run.log 2>/dev/null
exit $EXIT_CODE
