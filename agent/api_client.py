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

        采用指数退避重试策略
        """
        errors = []

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
                    error_msg = f"{model_name} 第{attempt}次调用失败: {e}"
                    logger.warning(error_msg)
                    errors.append(error_msg)

                    if attempt < max_retries:
                        wait_time = backoff_base * (2 ** (attempt - 1))
                        logger.info(f"等待 {wait_time}s 后重试...")
                        time.sleep(wait_time)

        # 所有模型都失败
        raise APIError(
            f"所有模型调用失败:\n" + "\n".join(errors),
            model="all", attempt=max_retries
        )

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
        """统一的OpenAI兼容API调用"""
        from api.openai_compatible import OpenAIClient

        client = OpenAIClient(
            api_key=config["api_key"],
            base_url=config["base_url"],
            model=config["model_id"],
            max_tokens=config.get("max_tokens", 8192),
            temperature=config.get("temperature", 0.7),
            stream=config.get("stream", False),
        )
        return client.query(prompt)

    def _call_anthropic(self, prompt: str, config: Dict) -> str:
        """Anthropic原生API调用（使用 anthropic SDK）"""
        from api.openai_compatible import AnthropicClient

        client = AnthropicClient(
            api_key=config["api_key"],
            model=config["model_id"],
            max_tokens=config.get("max_tokens", 23333),
            temperature=config.get("temperature", 1.0),
        )
        return client.query(prompt)

    def _call_zhipuai(self, prompt: str, config: Dict) -> str:
        """智谱 GLM 调用（使用 zai SDK，原生支持 thinking）"""
        from api.openai_compatible import ZhipuAIClient

        client = ZhipuAIClient(
            api_key=config["api_key"],
            base_url=config.get("base_url"),
            model=config["model_id"],
            max_tokens=config.get("max_tokens", 8192),
            temperature=config.get("temperature", 0.7),
            stream=config.get("stream", False),
        )
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
