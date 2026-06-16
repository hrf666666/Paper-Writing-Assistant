# -*- coding: utf-8 -*-
"""
统一 LLM 调用客户端

所有大模型调用统一归口到此模块：
- OpenAI 系（智谱GLM、阿里百炼、OpenAI o1/o3 等）→ openai SDK
- Anthropic 系（Claude）→ anthropic SDK

设计原则：
1. 两种 API 系列，仅 import 不同，调用结果处理完全一致
2. 配置驱动：模型列表从 config/api_config.py 的 PROVIDERS 读取
3. 流式支持：推理模型（QwQ/o1/o3 等）自动启用流式并提取答案
4. 参考 auto_research_agent 的 AgentDispatcher._call_llm() 设计
"""

import time
import base64
import logging
from typing import Optional, Dict, Any, List, Union

logger = logging.getLogger(__name__)


# ==================== 智谱 GLM 专用客户端（zai SDK） ====================

class ZhipuAIClient:
    """
    智谱 GLM 系列专用客户端（基于 zai SDK）

    解决的问题：
    - openai SDK 无法正确获取 reasoning_content（思考过程）
    - zai SDK 原生支持 thinking 参数和 reasoning_content 字段
    - 适用于所有 GLM 模型：glm-5.1, glm-5, glm-4.7, glm-4.6v 等
    """

    def __init__(self, api_key: str, model: str,
                 base_url: str,
                 max_tokens: int = 8192, temperature: float = 0.7,
                 stream: bool = False, timeout: int = 300):
        from zai._client import ZhipuAiClient as _ZhipuAiClient

        # fail-fast：Coding Plan 模式下 base_url 必须显式指定，
        # 否则 zai SDK 默认走标准 PAAS 端点 (api/paas/v4)，
        # 而 Coding Plan 的 key 在标准端点上无效（401）。
        if not base_url:
            raise ValueError(
                "ZhipuAIClient 必须显式传入 base_url（Coding Plan 端点）。"
                "用 api_config.ZHIPU_GLM_BASE_URL，"
                "禁止依赖 zai SDK 的默认标准 PAAS 端点。"
            )

        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.stream = stream
        self.timeout = timeout

        self._client = _ZhipuAiClient(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
        )

    def query(self, prompt: str, system_prompt: str = None,
              temperature: float = None, max_tokens: int = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        temp = temperature if temperature is not None else self.temperature
        max_tok = max_tokens if max_tokens is not None else self.max_tokens

        # GLM 思考模型走流式路径以正确获取 reasoning_content
        is_thinking = self._is_thinking_model()

        try:
            if is_thinking or self.stream:
                result = self._query_stream(messages, temp, max_tok)
            else:
                result = self._query_sync(messages, temp, max_tok)
            return result if result is not None else ""
        except Exception as e:
            logger.error(f"[ZhipuAI] {self.model} 调用失败: {e}")
            raise

    def _query_sync(self, messages: list, temperature: float, max_tokens: int) -> str:
        kwargs = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        # 思考模型启用 thinking 参数
        if self._is_thinking_model():
            kwargs["thinking"] = {"type": "enabled"}
        else:
            kwargs["temperature"] = temperature

        try:
            completion = self._client.chat.completions.create(**kwargs)
            msg = completion.choices[0].message
            # 优先取 content，为空取 reasoning_content
            content = msg.content if msg.content else ""
            if not content and hasattr(msg, 'reasoning_content') and msg.reasoning_content:
                content = msg.reasoning_content
            return content if content is not None else ""
        except IndexError:
            logger.error(f"[ZhipuAI] {self.model} 返回空 choices")
            return ""
        except Exception as e:
            logger.error(f"[ZhipuAI] {self.model} 同步调用失败: {e}")
            raise

    def _query_stream(self, messages: list, temperature: float, max_tokens: int) -> str:
        answer_content = ""
        reasoning_fallback = ""

        kwargs = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if self._is_thinking_model():
            kwargs["thinking"] = {"type": "enabled"}
        else:
            kwargs["temperature"] = temperature

        try:
            completion = self._client.chat.completions.create(**kwargs)
        except Exception as e:
            logger.error(f"[ZhipuAI] {self.model} 流式调用失败: {e}")
            raise

        try:
            for chunk in completion:
                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta

                # 收集 reasoning_content（思考过程）作为备用
                if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                    reasoning_fallback += delta.reasoning_content
                    continue

                if delta.content:
                    answer_content += delta.content
        except Exception as e:
            logger.error(f"[ZhipuAI] {self.model} 流式读取中断: {e}")
            if not answer_content and not reasoning_fallback:
                raise

        # 优先用 content，为空时用 reasoning_content
        if answer_content:
            return answer_content
        if reasoning_fallback:
            logger.info(f"[ZhipuAI] {self.model} content 为空，使用 reasoning_content ({len(reasoning_fallback)} chars)")
            return reasoning_fallback
        return ""

    def query_vision(self, text_prompt: str,
                     image_paths: List[str] = None,
                     image_base64_list: List[str] = None,
                     temperature: float = None,
                     max_tokens: int = None) -> str:
        """
        多模态视觉查询 — 发送文本 + 图片给视觉模型 (如 glm-4.6v)
        """
        content_parts = [{"type": "text", "text": text_prompt}]

        if image_paths:
            for path in image_paths:
                with open(path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                ext = path.rsplit(".", 1)[-1].lower()
                mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                        "gif": "image/gif", "webp": "image/webp"}.get(ext, "image/png")
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{b64}"}
                })

        if image_base64_list:
            for b64 in image_base64_list:
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}"}
                })

        messages = [{"role": "user", "content": content_parts}]
        temp = temperature if temperature is not None else self.temperature
        max_tok = max_tokens if max_tokens is not None else self.max_tokens

        try:
            completion = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tok,
                temperature=temp,
            )
            result = completion.choices[0].message.content
            return result if result is not None else ""
        except Exception as e:
            logger.error(f"[ZhipuAI Vision] {self.model} 调用失败: {e}")
            raise

    def _is_thinking_model(self) -> bool:
        """GLM 系列中支持思考的模型"""
        thinking_models = ["glm-5.2", "glm-5.1", "glm-5", "glm-4.7", "glm-4.8"]
        model_lower = self.model.lower()
        return any(m in model_lower for m in thinking_models)

    def __repr__(self):
        return f"ZhipuAIClient(model={self.model})"


# ==================== OpenAI 系统一客户端 ====================

class OpenAIClient:
    """
    OpenAI 兼容 API 统一客户端

    支持：智谱GLM、阿里百炼、OpenAI、以及任何 OpenAI 兼容端点。
    """

    def __init__(self, api_key: str, base_url: str, model: str,
                 max_tokens: int = 8192, temperature: float = 0.7,
                 stream: bool = False, timeout: int = 300):
        from openai import OpenAI

        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.stream = stream
        self.timeout = timeout

        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
        )

    def query(self, prompt: str, system_prompt: str = None,
              temperature: float = None, max_tokens: int = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        temp = temperature if temperature is not None else self.temperature
        max_tok = max_tokens if max_tokens is not None else self.max_tokens

        # 推理模型走流式路径
        is_reasoning = self._is_reasoning_model()

        try:
            if is_reasoning or self.stream:
                result = self._query_stream(messages, temp, max_tok)
            else:
                result = self._query_sync(messages, temp, max_tok)
            return result if result is not None else ""
        except Exception as e:
            logger.error(f"[OpenAI] {self.model} 调用失败: {e}")
            raise

    def _query_sync(self, messages: list, temperature: float, max_tokens: int) -> str:
        kwargs = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if not self._is_reasoning_model():
            kwargs["temperature"] = temperature

        try:
            completion = self._client.chat.completions.create(**kwargs)
            msg = completion.choices[0].message
            # 优先取 content，如果为空则取 reasoning_content（某些模型把答案放在 thinking 里）
            content = msg.content if msg.content else ""
            if not content and hasattr(msg, 'reasoning_content') and msg.reasoning_content:
                content = msg.reasoning_content
            return content if content is not None else ""
        except IndexError:
            logger.error(f"[OpenAI] {self.model} 返回空 choices")
            return ""
        except Exception as e:
            logger.error(f"[OpenAI] {self.model} 同步调用失败: {e}")
            raise

    def _query_stream(self, messages: list, temperature: float, max_tokens: int) -> str:
        answer_content = ""
        reasoning_fallback = ""

        kwargs = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if not self._is_reasoning_model():
            kwargs["temperature"] = temperature

        try:
            completion = self._client.chat.completions.create(**kwargs)
        except Exception as e:
            logger.error(f"[OpenAI] {self.model} 流式调用失败: {e}")
            raise

        try:
            for chunk in completion:
                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta

                # 收集 reasoning_content 作为备用（某些模型把答案放在 thinking 里）
                if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                    reasoning_fallback += delta.reasoning_content
                    continue

                if delta.content:
                    answer_content += delta.content
        except Exception as e:
            logger.error(f"[OpenAI] {self.model} 流式读取中断: {e}")
            if not answer_content and not reasoning_fallback:
                raise

        # 优先用 content，为空时用 reasoning_content
        if answer_content:
            return answer_content
        if reasoning_fallback:
            logger.info(f"[OpenAI] {self.model} content 为空，使用 reasoning_content ({len(reasoning_fallback)} chars)")
            return reasoning_fallback
        return ""

    def query_vision(self, text_prompt: str,
                     image_paths: List[str] = None,
                     image_base64_list: List[str] = None,
                     temperature: float = None,
                     max_tokens: int = None) -> str:
        """
        多模态视觉查询 — 发送文本 + 图片给视觉模型 (如 glm-5v-turbo)

        Args:
            text_prompt: 文本提示
            image_paths: 本地图片路径列表（自动 base64 编码）
            image_base64_list: 已 base64 编码的图片列表
            temperature: 温度
            max_tokens: 最大 token 数

        Returns:
            模型文本回复
        """
        content_parts = [{"type": "text", "text": text_prompt}]

        # 从本地文件加载图片
        if image_paths:
            for path in image_paths:
                with open(path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                ext = path.rsplit(".", 1)[-1].lower()
                mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                        "gif": "image/gif", "webp": "image/webp"}.get(ext, "image/png")
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{b64}"}
                })

        # 从 base64 列表添加
        if image_base64_list:
            for b64 in image_base64_list:
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}"}
                })

        messages = [{"role": "user", "content": content_parts}]
        temp = temperature if temperature is not None else self.temperature
        max_tok = max_tokens if max_tokens is not None else self.max_tokens

        try:
            completion = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tok,
                temperature=temp,
            )
            result = completion.choices[0].message.content
            return result if result is not None else ""
        except Exception as e:
            logger.error(f"[OpenAI Vision] {self.model} 调用失败: {e}")
            raise

    def _is_reasoning_model(self) -> bool:
        reasoning_keywords = ["qwq", "o1", "o3", "deepseek-r", "reasoning"]
        return any(kw in self.model.lower() for kw in reasoning_keywords)

    def __repr__(self):
        return f"OpenAIClient(model={self.model})"


# ==================== Anthropic 系统一客户端 ====================

class AnthropicClient:
    """
    Anthropic 原生 API 统一客户端

    使用 anthropic SDK（非 requests.post），与 OpenAI 系客户端接口一致。
    """

    def __init__(self, api_key: str, model: str,
                 max_tokens: int = 8192, temperature: float = 1.0,
                 timeout: int = 300, **kwargs):
        import anthropic

        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout

        self._client = anthropic.Anthropic(
            api_key=api_key,
            timeout=timeout,
        )

    def query(self, prompt: str, system_prompt: str = None,
              temperature: float = None, max_tokens: int = None) -> str:
        temp = temperature if temperature is not None else self.temperature
        max_tok = max_tokens if max_tokens is not None else self.max_tokens

        kwargs = {
            "model": self.model,
            "max_tokens": max_tok,
            "messages": [{"role": "user", "content": prompt}],
        }
        if temp is not None:
            kwargs["temperature"] = temp
        if system_prompt:
            kwargs["system"] = system_prompt

        try:
            response = self._client.messages.create(**kwargs)
            # 提取文本内容
            for block in response.content:
                if block.type == "text":
                    return block.text
            return ""
        except Exception as e:
            logger.error(f"[Anthropic] {self.model} 调用失败: {e}")
            raise

    def __repr__(self):
        return f"AnthropicClient(model={self.model})"


# ==================== 统一工厂函数 ====================

def create_client_for_model(model_alias: str, **overrides) -> object:
    """
    根据模型别名自动创建正确类型的客户端实例。

    自动判断 use_zai / non_openai，调用者无需关心底层 SDK。
    适用于 visual_verifier、figure_critic 等需要按别名创建客户端的场景。

    Args:
        model_alias: 模型别名（如 "glm_4_6v", "glm_5_1"）
        **overrides: 覆盖参数（如 temperature, max_tokens）

    Returns:
        ZhipuAIClient、OpenAIClient 或 AnthropicClient 实例
    """
    import config.api_config as _cfg

    cfg = _cfg.MODEL_ALIASES.get(model_alias)
    if not cfg:
        raise ValueError(f"未知模型别名: {model_alias}")

    provider_name = cfg["provider"]
    provider_config = _cfg.PROVIDERS.get(provider_name, {})
    api_key_env = provider_config.get("api_key_env", "")
    api_key = getattr(_cfg, api_key_env, "")
    if not api_key:
        raise ValueError(f"{provider_name} API Key 未配置")

    params = {
        "api_key": api_key,
        "model": cfg["model_id"],
        "max_tokens": overrides.pop("max_tokens", cfg.get("max_tokens", 8192)),
        "temperature": overrides.pop("temperature", cfg.get("temperature", 0.7)),
        "stream": overrides.pop("stream", cfg.get("stream", False)),
    }

    if cfg.get("non_openai"):
        return AnthropicClient(**{k: v for k, v in params.items() if k != "stream"})
    elif cfg.get("use_zai"):
        params["base_url"] = provider_config.get("base_url")
        return ZhipuAIClient(**params)
    else:
        params["base_url"] = provider_config.get("base_url", "https://api.openai.com/v1")
        return OpenAIClient(**params)


def create_client(provider_config: Dict) -> object:
    """
    根据 provider 配置自动创建对应的客户端实例。

    Args:
        provider_config: 包含 api_key, base_url, model_id, non_openai 等字段的字典

    Returns:
        ZhipuAIClient、OpenAIClient 或 AnthropicClient 实例
    """
    if provider_config.get("non_openai"):
        return AnthropicClient(
            api_key=provider_config["api_key"],
            model=provider_config["model_id"],
            max_tokens=provider_config.get("max_tokens", 8192),
            temperature=provider_config.get("temperature", 1.0),
        )
    elif provider_config.get("use_zai"):
        # GLM 系列走 zai SDK，支持原生 thinking 和 reasoning_content
        return ZhipuAIClient(
            api_key=provider_config["api_key"],
            base_url=provider_config.get("base_url"),
            model=provider_config["model_id"],
            max_tokens=provider_config.get("max_tokens", 8192),
            temperature=provider_config.get("temperature", 0.7),
            stream=provider_config.get("stream", False),
        )
    else:
        return OpenAIClient(
            api_key=provider_config["api_key"],
            base_url=provider_config["base_url"],
            model=provider_config["model_id"],
            max_tokens=provider_config.get("max_tokens", 8192),
            temperature=provider_config.get("temperature", 0.7),
            stream=provider_config.get("stream", False),
        )


# ==================== 向后兼容的便捷函数 ====================

def _get_model_config(alias: str) -> Dict:
    """从 MODEL_ALIASES 获取模型配置，不存在则返回空字典"""
    from config.api_config import MODEL_ALIASES
    return MODEL_ALIASES.get(alias, {})


# ========== 统一模型查询（字典驱动） ==========

def query_model(prompt: str, alias: str, **kwargs) -> str:
    """统一模型查询入口：通过 alias 从 PROVIDERS 自动查找 key/base_url 并调用"""
    import config.api_config as _cfg

    cfg = _get_model_config(alias)
    if not cfg:
        raise ValueError(f"未知模型别名: {alias}")

    provider_name = cfg["provider"]
    provider_config = _cfg.PROVIDERS.get(provider_name, {})
    # 从 config 模块读取 key（经过回退链处理）
    api_key = getattr(_cfg, provider_config.get("api_key_env", ""), "")
    if not api_key:
        raise ValueError(f"{provider_name} API Key 未配置")

    model_id = cfg.get("model_id", alias)
    max_tokens = kwargs.pop("max_tokens", cfg.get("max_tokens", 8192))
    temperature = kwargs.pop("temperature", cfg.get("temperature", 0.7))
    stream = kwargs.pop("stream", cfg.get("stream", False))
    system_prompt = kwargs.pop("system_prompt", None)
    base_url = provider_config.get("base_url", "https://api.openai.com/v1")

    if cfg.get("non_openai"):
        client = AnthropicClient(api_key=api_key, model=model_id,
                                 max_tokens=max_tokens, temperature=temperature)
    elif cfg.get("use_zai"):
        client = ZhipuAIClient(api_key=api_key, base_url=base_url, model=model_id,
                               max_tokens=max_tokens, temperature=temperature, stream=stream)
    else:
        client = OpenAIClient(api_key=api_key, base_url=base_url, model=model_id,
                              max_tokens=max_tokens, temperature=temperature, stream=stream)
    return client.query(prompt, system_prompt=system_prompt)

