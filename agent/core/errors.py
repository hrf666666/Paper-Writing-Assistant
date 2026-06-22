# -*- coding: utf-8 -*-
"""
错误分级内核 (v13) — 治理 loop.py 的 42 处 except Exception 静默降级。

设计原则：
- 瞬时错误 (TransientError) → 重试（带退避），可望自愈
- 永久错误 (PermanentError) → 标记 failed，禁止降级为 "completed + 空值"
- 降级产物 (DegradedResult) → 唯一允许的降级，但必须显式标记，下游必须识别

classify() 把 SDK 原生异常映射到上述分级，是 api_client 的分类闸口。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# 异常分级
# ──────────────────────────────────────────────────────────────

class TransientError(Exception):
    """瞬时错误：重试可望自愈。

    触发：429 配额/限流、网络超时、连接重置、5xx 服务端临时故障。
    策略：退避重试（指数 / 按 Retry-After），或切换到其他 provider。
    """

    def __init__(self, message: str, *, retry_after: Optional[float] = None,
                 original: Optional[BaseException] = None):
        self.retry_after = retry_after      # 建议等待秒数（None=未知，由调用方退避）
        self.original = original            # 原始异常，保留完整 traceback
        super().__init__(message)


class PermanentError(Exception):
    """永久错误：重试无意义，必须显式失败。

    触发：401/403 鉴权失败、400 参数错误、JSON 解析失败、逻辑 bug、
    资源缺失（关键文件/模型不可用）。
    策略：标记任务 failed，禁止 "置空 + completed" 降级。
    """

    def __init__(self, message: str, *, original: Optional[BaseException] = None,
                 hint: str = ""):
        self.original = original
        self.hint = hint                    # 给人类的修复提示
        super().__init__(message)


class AllProvidersExhausted(PermanentError):
    """所有 provider/模型都失败。属于永久错误（本轮无法恢复），但可换时间窗重跑。"""


# ──────────────────────────────────────────────────────────────
# DegradedResult —— 唯一允许的降级产物
# ──────────────────────────────────────────────────────────────

@dataclass
class DegradedResult:
    """显式声明的降级产物。

    替代旧的 "返回空串 / 返回占位符 / 返回硬编码字符串" 静默降级模式。
    下游（验收器、注入器、编译器）必须检查 .degraded 标志，
    不得把 DegradedResult 当作正常产物送进最终 PDF。
    """
    content: str
    reason: str                             # 为什么降级（人类可读）
    source: str = ""                        # 产生方标识，如 "ch5_conclusion"
    degraded: bool = True                   # 永远为 True（语义标记）

    def __bool__(self) -> bool:
        # 注意：DegradedResult 永远是"失败"，即便 content 非空。
        # 这样 `if result:` 这种判空检查不会把降级产物当成功。
        return False


# ──────────────────────────────────────────────────────────────
# classify() —— SDK 原生异常 → 分级（api_client 的分类闸口）
# ──────────────────────────────────────────────────────────────

# 配额/限流的文本特征（zai/openai SDK 的 message 里都含这些）
_QUOTA_PATTERNS = (
    "429", "rate limit", "rate_limit", "ratelimit",
    "使用上限", "配额", "quota", "too many requests", "reach limit",
    "reach_limit",
)
# 瞬时网络/服务端特征的文本
_TRANSIENT_PATTERNS = (
    "timeout", "timed out", "connection reset", "connection refused",
    "temporarily unavailable", "500", "502", "503", "504",
    "internal server error", "bad gateway", "server error",
    "service unavailable", "gateway timeout", "connection aborted",
)
# 模型不存在/不可用特征的文本（v14 缺口1：覆盖 qwen/dashscope）
# 归 permanent：换模型可解，重试同一模型无意义（api_client 收到 permanent 立即 failover）
_MODEL_NOT_FOUND_PATTERNS = (
    "model not exist", "model_not_found", "model does not exist",
    "model not found", "no such model", "invalid model",
    "model unavailable", "model is not available",
)


def _retry_after_from_message(message: str) -> Optional[float]:
    """从配额错误消息里解析重置时间，返回建议等待秒数。

    例：智谱 "您的限额将在 2026-06-15 19:42:06 重置" → 解析出剩余秒数。
    解析失败返回 None（由调用方走默认退避）。
    """
    from datetime import datetime
    # 智谱格式：YYYY-MM-DD HH:MM:SS 重置
    m = re.search(r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})", message)
    if m:
        try:
            reset_at = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
            from datetime import datetime as _dt
            now = _dt.now()
            wait = (reset_at - now).total_seconds()
            # 合理范围：10s ~ 5h。超出说明时钟漂移，放弃解析。
            if 10 <= wait <= 5 * 3600:
                return wait
        except (ValueError, OSError):
            pass
    # Retry-After 头风格：纯秒数
    m = re.search(r"retry[- ]after[:\s]+(\d+)", message, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return None


def classify(exc: BaseException) -> tuple[str, Optional[float], Optional[BaseException]]:
    """把任意异常映射到分级。

    Returns:
        (level, retry_after, original)
        level: "transient" | "permanent" | "unknown"
        retry_after: 建议等待秒数（仅 transient 可能有值）
        original: 透传原异常

    分类优先级（从精确到模糊）：
        1. SDK 类型名精确匹配（APIReachLimitError / RateLimitError / APITimeoutError …）
        2. 异常 message 文本特征匹配（429 / 使用上限 / timeout …）
        3. 兜底 unknown（调用方按 permanent 处理更安全）
    """
    type_name = type(exc).__name__
    message = str(exc)

    # ── 1. 类型名精确匹配（覆盖 zai + openai SDK）──
    # zai: APIReachLimitError / APITimeoutError / APIRequestFailedError / APIServerFlowExceedError
    # openai: RateLimitError / APITimeoutError / APIConnectionError / InternalServerError
    if type_name in ("APIReachLimitError", "RateLimitError", "APIServerFlowExceedError"):
        return "transient", _retry_after_from_message(message), exc
    if type_name in ("APITimeoutError", "APIConnectionError", "APIRequestFailedError",
                     "TimeoutError", "ConnectionError", "ConnectionResetError"):
        return "transient", None, exc
    if type_name in ("InternalServerError", "APIInternalError"):
        return "transient", None, exc
    # 永久：鉴权/参数类
    if type_name in ("APIAuthenticationError", "AuthenticationError",
                     "PermissionDeniedError", "BadRequestError", "NotFoundError",
                     "UnprocessableEntityError", "ValueError", "KeyError"):
        return "permanent", None, exc

    # ── 2. message 文本特征匹配（SDK 把 HTTP 状态码塞进 message）──
    msg_lower = message.lower()
    if any(p in msg_lower for p in _QUOTA_PATTERNS):
        return "transient", _retry_after_from_message(message), exc
    if any(p in msg_lower for p in _TRANSIENT_PATTERNS):
        return "transient", None, exc
    # 鉴权/参数类文本
    if any(p in msg_lower for p in ("401", "403", "unauthorized", "forbidden",
                                     "invalid api key", "authentication")):
        return "permanent", None, exc
    # 模型不存在/不可用（v14 缺口1：换模型可解，归 permanent → 立即 failover）
    if any(p in msg_lower for p in _MODEL_NOT_FOUND_PATTERNS):
        return "permanent", None, exc

    # ── 3. 兜底 ──
    return "unknown", None, exc


def to_transient(exc: BaseException) -> TransientError:
    """把任意异常包装成 TransientError（带 retry_after）。"""
    level, retry_after, _ = classify(exc)
    wait = retry_after if level == "transient" else None
    return TransientError(str(exc), retry_after=wait, original=exc)


def to_permanent(exc: BaseException, hint: str = "") -> PermanentError:
    """把任意异常包装成 PermanentError。"""
    return PermanentError(str(exc), original=exc, hint=hint)


# ──────────────────────────────────────────────────────────────
# 辅助：让旧代码平滑迁移
# ──────────────────────────────────────────────────────────────

def is_transient(exc: BaseException) -> bool:
    """快速判断：是否瞬时错误。供不想破坏控制流的最小改动点使用。"""
    level, _, _ = classify(exc)
    return level == "transient"


def should_retry(exc: BaseException) -> bool:
    """是否值得重试。unknown 按 transient 处理（宁可重试一次再判定）。"""
    level, _, _ = classify(exc)
    return level in ("transient", "unknown")
