#!/usr/bin/env python3
"""Pipeline wrapper — 日志同时写入文件"""

import sys
import os
import logging
import datetime

# 确保 texlive 在 PATH 中
os.environ["PATH"] = "/usr/local/texlive/2026/bin/x86_64-linux:" + os.environ.get("PATH", "")

# 创建输出目录
os.makedirs("output", exist_ok=True)

LOG_FILE = os.path.join(os.getcwd(), "pipeline_run.log")  # 放在项目根目录，不被 output 归档影响


class LogTee(logging.StreamHandler):
    """将 logging 输出同时写入终端和文件"""
    def __init__(self, log_path):
        super().__init__()
        self.terminal = sys.__stdout__
        self.log_fh = open(log_path, "w", buffering=1, encoding="utf-8")

    def emit(self, record):
        msg = self.format(record) + "\n"
        try:
            self.terminal.write(msg)
            self.terminal.flush()
        except Exception:
            pass
        try:
            self.log_fh.write(msg)
            self.log_fh.flush()
        except Exception:
            pass

    def close(self):
        self.log_fh.close()
        super().close()


# 配置日志 — 覆盖 pipeline.py 的 basicConfig
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
# 清除已有 handler
root_logger.handlers.clear()
# 添加 Tee handler
tee = LogTee(LOG_FILE)
tee.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S"))
root_logger.addHandler(tee)

logger = logging.getLogger("pipeline_wrapper")
logger.info(f"PID={os.getpid()} Pipeline starting at {datetime.datetime.now()}")
logger.info(f"Args: {sys.argv[1:]}")

# 运行 pipeline（不再让 pipeline.py 的 basicConfig 覆盖）
# 通过设一个标记阻止 pipeline.py 重新配置 logging
logging.basicConfig = lambda *a, **kw: None

sys.argv = ["pipeline.py"] + sys.argv[1:]

try:
    from pipeline import main
    main()
except Exception as e:
    logger.critical(f"Pipeline crashed: {e}", exc_info=True)
    sys.exit(1)
finally:
    tee.close()
