# -*- coding: utf-8 -*-
"""
统一API客户端 v2.0 - 配置驱动的Provider体系

核心升级：
1. 配置驱动：从 api_config.PROVIDERS 动态发现所有可用模型
2. 国内优先：默认使用智谱GLM/阿里云百炼等国内API
3. 统一OpenAI兼容：所有OpenAI兼容API走同一调用路径
4. 智能降级：按优先级列表自动切换，跳过不可用的Provider
5. 健康检查：启动时验证API Key可用性
"""

import time
import json
import re
import logging
import threading
from typing import Optional, List, Dict, Any

from config.api_config import (
    PROVIDERS, MODEL_ALIASES,
    ZHIPU_GLM_API_KEY, ALI_BAILIAN_API_KEY,
    CLAUDE_API_KEY, OPENAI_API_KEY,
)
from config.project_config import API_CALL_INTERVAL

logger = logging.getLogger(__name__)


class APIError(Exception):
    """API调用失败异常"""
    def __init__(self, message: str, model: str = "", provider: str = "", attempt: int = 0):
        self.model = model
        self.provider = provider
        self.attempt = attempt
        super().__init__(message)


class UnifiedAPIClient:
    """
    统一API客户端 v2.0

    特性：
    1. 配置驱动：从 PROVIDERS 自动发现和构建客户端
    2. 统一重试策略（指数退避）
    3. 模型降级（按优先级列表自动切换）
    4. 统一超时配置
    5. 健康检查：过滤掉不可用的Provider
    """

    def __init__(self, call_interval: float = None):
        self.call_interval = call_interval if call_interval is not None else API_CALL_INTERVAL
        self._last_call_time = 0.0
        self._call_stats: Dict[str, Dict[str, int]] = {}
        self._available_models: Dict[str, Dict] = {}
        self._client_pool: Dict[str, object] = {}  # pooled SDK clients by alias (avoid re-init per call)
        self._prompt_chars_total = 0   # v13: 累计注入字符数（上下文可观测）
        self._prompt_calls_logged = 0  # 用于采样日志，避免每条都打

        # 启动时检测可用模型
        self._detect_available_models()

    def _detect_available_models(self):
        """检测所有配置了API Key的可用模型"""
        for alias, config in MODEL_ALIASES.items():
            provider_name = config["provider"]
            provider_config = PROVIDERS.get(provider_name, {})
            api_key_env = provider_config.get("api_key_env", "")
            api_key = _get_api_key_by_env(api_key_env)

            if api_key:
                self._available_models[alias] = {
                    **config,
                    "api_key": api_key,
                    "base_url": provider_config.get("base_url", ""),
                }
                logger.debug(f"模型可用: {alias} ({config['model_id']} @ {provider_name})")
            else:
                logger.debug(f"模型不可用（缺少API Key）: {alias}")

        available = list(self._available_models.keys())
        logger.info(f"检测到 {len(available)} 个可用模型: {available}")

    def _enforce_interval(self):
        """强制API调用间隔"""
        elapsed = time.time() - self._last_call_time
        if elapsed < self.call_interval:
            sleep_time = self.call_interval - elapsed
            logger.debug(f"API间隔等待 {sleep_time:.1f}s")
            time.sleep(sleep_time)
        self._last_call_time = time.time()

    def _record_stats(self, model: str, success: bool):
        """记录调用统计"""
        if model not in self._call_stats:
            self._call_stats[model] = {"success": 0, "failure": 0}
        if success:
            self._call_stats[model]["success"] += 1
        else:
            self._call_stats[model]["failure"] += 1

    def call_generation(self, prompt: str, model_list: List[str] = None,
                        max_retries: int = 2, backoff_base: float = 30.0) -> str:
        """调用生成模型（按优先级降级）"""
        if model_list is None:
            from config.project_config import GENERATION_MODELS
            model_list = GENERATION_MODELS
        return self._call_with_fallback(prompt, model_list, max_retries, backoff_base)

    def call_reasoning(self, prompt: str, model_list: List[str] = None,
                       max_retries: int = 2, backoff_base: float = 30.0) -> str:
        """调用推理模型（按优先级降级）"""
        if model_list is None:
            from config.project_config import REASONING_MODELS
            model_list = REASONING_MODELS
        return self._call_with_fallback(prompt, model_list, max_retries, backoff_base)

    def call_light(self, prompt: str, model_list: List[str] = None,
                   max_retries: int = 2, backoff_base: float = 30.0) -> str:
        """调用轻量模型（分类/判断等小任务）"""
        if model_list is None:
            from config.project_config import LIGHT_MODELS
            model_list = LIGHT_MODELS
        return self._call_with_fallback(prompt, model_list, max_retries, backoff_base)

    def call_evaluation(self, prompt: str, model_list: List[str] = None,
                        max_retries: int = 2, backoff_base: float = 30.0) -> str:
        """
        调用评价模型 — 与执行模型来自不同 provider，避免自我审查盲区。

        模型列表由 resolve_eval_models() 动态决定：
        - qwen3.7-max 执行 → glm_5_1 评价
        - glm_5.1 执行 → qwen3.7-max 评价
        - 仅 Qwen → qwen3.7-max 执行, qwen3.6-plus 评价
        """
        if model_list is None:
            from config.project_config import get_eval_models
            model_list = get_eval_models()
        return self._call_with_fallback(prompt, model_list, max_retries, backoff_base)

    def _call_with_fallback(self, prompt: str, model_list: List[str],
                            max_retries: int, backoff_base: float) -> str:
        """
        按优先级尝试调用模型，失败时自动降级到下一个模型

        v13: 错误分级驱动重试策略（替代旧的"所有异常一刀切指数退避"）
        - 瞬时错误（429 配额/超时）：有 retry_after 则按它等，否则指数退避；同一 provider
          耗尽后 failover 到下一个 provider。
        - 永久错误（401/403/参数）：不重试同一模型，直接 failover。
        - 不再把瞬时配额错误（如 GLM 5 小时上限）静默为"重试 30s 两次就放弃"。
        """
        from agent.core.errors import classify

        errors = []
        # 记录 prompt 规模（上下文可观测；采样打日志避免刷屏）
        prompt_chars = len(prompt)
        self._prompt_chars_total += prompt_chars
        self._prompt_calls_logged += 1
        if self._prompt_calls_logged % 20 == 0 or prompt_chars > 60000:
            logger.info(f"[ctx] 累计注入 {self._prompt_chars_total} 字符 "
                        f"(本次 {prompt_chars}, 调用 #{self._prompt_calls_logged})"
                        + (" [超大prompt!]" if prompt_chars > 60000 else ""))

        for model_name in model_list:
            # 跳过不可用的模型
            if model_name not in self._available_models:
                logger.debug(f"跳过不可用模型: {model_name}")
                continue

            for attempt in range(1, max_retries + 1):
                try:
                    self._enforce_interval()
                    result = self._dispatch_call(model_name, prompt)
                    self._record_stats(model_name, True)
                    return result
                except Exception as e:
                    self._record_stats(model_name, False)
                    level, retry_after, _ = classify(e)
                    error_msg = f"{model_name} 第{attempt}次调用失败 [{level}]: {e}"
                    logger.warning(error_msg)
                    errors.append(error_msg)

                    # 永久错误：不重试同一模型，直接 failover
                    if level == "permanent":
                        logger.info(f"{model_name} 永久错误，跳过重试，failover")
                        break

                    # 瞬时错误：决定等待时间
                    if level == "transient":
                        if retry_after:
                            # 配额类（如 GLM 5h 上限）：按重置时间等
                            wait_time = min(retry_after, 3600.0)  # 上限 1h，避免死等
                            logger.info(f"{model_name} 配额受限，等待 {wait_time:.0f}s 后重试 "
                                        f"(重置时间已解析)")
                        elif attempt < max_retries:
                            wait_time = backoff_base * (2 ** (attempt - 1))
                            logger.info(f"等待 {wait_time}s 后重试...")
                        else:
                            break
                        time.sleep(wait_time)
                    else:
                        # unknown：保留旧行为（退避重试），保守可恢复
                        if attempt < max_retries:
                            wait_time = backoff_base * (2 ** (attempt - 1))
                            logger.info(f"等待 {wait_time}s 后重试 (unknown)...")
                            time.sleep(wait_time)

        # 所有模型都失败 — 把分级附在 APIError 上，供调用方判断
        all_exhausted = APIError(
            f"所有模型调用失败:\n" + "\n".join(errors),
            model="all", attempt=max_retries
        )
        # v13 P1: error_level 死代码移除（loop 从不 except APIError、从不读 .error_level）。
        # 分级信息已在每条 error_msg 的 [level] 标签里。
        raise all_exhausted

    def _get_client(self, model_name: str):
        """Get (or lazily create) a pooled SDK client by alias.

        v2.2: SDK clients are cached per-alias so HTTP connection pools /
        TLS state are reused across the hundreds of calls in a run,
        instead of being rebuilt on every single call.
        """
        if model_name in self._client_pool:
            return self._client_pool[model_name]
        config = self._available_models.get(model_name)
        if not config:
            raise ValueError(f"未知或不可用的模型: {model_name}")
        client = self._build_client(config)
        self._client_pool[model_name] = client
        return client

    def _build_client(self, config: Dict):
        """Build a SDK client based on model type (runs once per alias)."""
        from api.openai_compatible import OpenAIClient, ZhipuAIClient, AnthropicClient
        if config.get("non_openai"):
            return AnthropicClient(api_key=config["api_key"], model=config["model_id"],
                                   max_tokens=config.get("max_tokens", 23333),
                                   temperature=config.get("temperature", 1.0))
        if config.get("use_zai"):
            return ZhipuAIClient(api_key=config["api_key"], base_url=config.get("base_url"),
                                 model=config["model_id"], max_tokens=config.get("max_tokens", 8192),
                                 temperature=config.get("temperature", 0.7),
                                 stream=config.get("stream", False))
        return OpenAIClient(api_key=config["api_key"], base_url=config["base_url"],
                            model=config["model_id"], max_tokens=config.get("max_tokens", 8192),
                            temperature=config.get("temperature", 0.7),
                            stream=config.get("stream", False))

    def _find_alias_by_config(self, config: Dict) -> str:
        """Reverse-lookup alias from config object identity (pool keyed by alias)."""
        for alias, cfg in self._available_models.items():
            if cfg is config:
                return alias
        return ""

    def _dispatch_call(self, model_name: str, prompt: str) -> str:
        """
        根据模型名称分发调用

        v2.0: 基于 PROVIDERS 配置动态分发，而非硬编码 if-else
        v2.1: GLM 系列走 zai SDK（支持 thinking + reasoning_content）
        """
        config = self._available_models.get(model_name)
        if not config:
            raise ValueError(f"未知或不可用的模型: {model_name}")

        # Anthropic原生API走特殊路径
        if config.get("non_openai"):
            return self._call_anthropic(prompt, config)

        # GLM 系列走 zai SDK
        if config.get("use_zai"):
            return self._call_zhipuai(prompt, config)

        # 所有OpenAI兼容API走统一路径
        return self._call_openai_compatible(prompt, config)

    def _call_openai_compatible(self, prompt: str, config: Dict) -> str:
        """OpenAI-compatible call via pooled client."""
        alias = self._find_alias_by_config(config)
        client = self._get_client(alias)
        return client.query(prompt)

    def _call_anthropic(self, prompt: str, config: Dict) -> str:
        """Anthropic native call via pooled client."""
        alias = self._find_alias_by_config(config)
        client = self._get_client(alias)
        return client.query(prompt)

    def _call_zhipuai(self, prompt: str, config: Dict) -> str:
        """GLM call via pooled client (zai SDK, native thinking support)."""
        alias = self._find_alias_by_config(config)
        client = self._get_client(alias)
        return client.query(prompt)

    def parse_json_response(self, response: str, default=None):
        """安全解析LLM返回中的JSON内容"""
        try:
            result = _extract_json_from_string(response)
            return result
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"JSON解析失败: {e}")
            return default


    def get_stats(self) -> Dict[str, Dict[str, int]]:
        """获取调用统计"""
        return self._call_stats.copy()

    def get_context_stats(self) -> Dict[str, int]:
        """v13: 获取上下文注入统计（prompt 字符累计 + 调用次数）"""
        return {
            "prompt_chars_total": self._prompt_chars_total,
            "prompt_calls": self._prompt_calls_logged,
        }

    def get_available_models(self) -> List[str]:
        """获取所有可用模型列表"""
        return list(self._available_models.keys())

    def reset_stats(self):
        """重置调用统计"""
        self._call_stats.clear()


from utils.json_utils import extract_json_from_string as _extract_json_from_string


def _get_api_key_by_env(env_var: str) -> str:
    """根据环境变量名获取API Key（直接从config模块读取，确保经过回退链处理）"""
    # 直接从 config.api_config 模块读取同名变量
    # 不用 os.getenv，因为 dotenv 可能加载过期 key 覆盖环境变量
    try:
        import config.api_config as _cfg
        return getattr(_cfg, env_var, "")
    except Exception:
        import os
        return os.getenv(env_var, "")


# 全局单例
_default_client: Optional[UnifiedAPIClient] = None
_client_lock = threading.Lock()


def get_api_client() -> UnifiedAPIClient:
    """获取全局API客户端单例（线程安全）"""
    global _default_client
    if _default_client is None:
        with _client_lock:
            if _default_client is None:
                _default_client = UnifiedAPIClient()
    return _default_client
