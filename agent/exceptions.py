# -*- coding: utf-8 -*-
"""
统一异常类体系

所有自定义异常的基类和子类，提供结构化的错误信息。
下游代码可以按需捕获特定异常类型，而非通用的 Exception。
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class PipelineError(Exception):
    """Pipeline 执行过程中的基础异常"""

    def __init__(self, message: str, phase: str = "", task_id: str = ""):
        self.phase = phase
        self.task_id = task_id
        super().__init__(message)


class ConfigError(PipelineError):
    """配置加载/解析错误"""

    def __init__(self, message: str, config_key: str = "", **kwargs):
        self.config_key = config_key
        super().__init__(message, **kwargs)


class FileIOError(PipelineError):
    """文件读写错误"""

    def __init__(self, message: str, filepath: str = "", operation: str = "", **kwargs):
        self.filepath = filepath
        self.operation = operation
        super().__init__(message, **kwargs)


class ValidationError(PipelineError):
    """数据验证/格式错误"""

    def __init__(self, message: str, field: str = "", **kwargs):
        self.field = field
        super().__init__(message, **kwargs)


def safe_execute(func, error_msg: str = "", default=None, log_level: str = "warning"):
    """
    安全执行函数，捕获所有异常并记录日志

    Args:
        func: 要执行的函数（无参 callable）
        error_msg: 错误消息前缀
        default: 异常时的默认返回值
        log_level: 日志级别 ("debug", "info", "warning", "error")

    Returns:
        函数返回值，或 default（异常时）
    """
    try:
        return func()
    except Exception as e:
        msg = f"{error_msg}: {e}" if error_msg else str(e)
        _logger_func = getattr(logger, log_level, logger.warning)
        _logger_func(msg)
        return default
