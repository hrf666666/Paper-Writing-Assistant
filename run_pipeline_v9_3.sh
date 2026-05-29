#!/bin/bash
# v9.3 Pipeline 启动脚本

cd /home/bigboss/code/paper-writing-assistant

# 加载环境变量
source ~/.bashrc

# 设置 PATH
export PATH="/usr/local/texlive/2026/bin/x86_64-linux:$PATH"

# 清理旧输出
echo "清理旧输出..."
rm -rf output/chapter* output/abstract output/*.json output/*.md output/.checkpoints 2>/dev/null

# 启动 pipeline
echo "启动 Pipeline v9.3..."
echo "时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "PID: $$"

/home/bigboss/miniconda3/envs/py311/bin/python -u pipeline.py --no-resume 2>&1 | tee output/pipeline_v9_3.log

echo "Pipeline 完成: $(date '+%Y-%m-%d %H:%M:%S')"
