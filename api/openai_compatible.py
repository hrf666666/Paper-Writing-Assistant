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
        try:
            completion = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            content = completion.choices[0].message.content
            return content if content is not None else ""
        except IndexError:
            logger.error(f"[OpenAI] {self.model} 返回空 choices")
            return ""
        except Exception as e:
            logger.error(f"[OpenAI] {self.model} 同步调用失败: {e}")
            raise

    def _query_stream(self, messages: list, temperature: float, max_tokens: int) -> str:
        answer_content = ""

        kwargs = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": True,
        }
        # 推理模型不支持 temperature 参数
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

                # 推理模型有 reasoning_content 字段，跳过思考过程
                if hasattr(delta, 'reasoning_content') and delta.reasoning_content is not None:
                    continue
                else:
                    if delta.content:
                        answer_content += delta.content
        except Exception as e:
            logger.error(f"[OpenAI] {self.model} 流式读取中断: {e}")
            if not answer_content:
                raise

        return answer_content if answer_content else ""

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

def create_client(provider_config: Dict) -> object:
    """
    根据 provider 配置自动创建对应的客户端实例。

    Args:
        provider_config: 包含 api_key, base_url, model_id, non_openai 等字段的字典

    Returns:
        OpenAIClient 或 AnthropicClient 实例
    """
    if provider_config.get("non_openai"):
        return AnthropicClient(
            api_key=provider_config["api_key"],
            model=provider_config["model_id"],
            max_tokens=provider_config.get("max_tokens", 8192),
            temperature=provider_config.get("temperature", 1.0),
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


def query_glm(prompt: str, model: str = None, **kwargs) -> str:
    """调用智谱GLM模型"""
    from config.api_config import ZHIPU_GLM_API_KEY, ZHIPU_GLM_BASE_URL
    if not ZHIPU_GLM_API_KEY:
        raise ValueError("智谱GLM API Key 未配置，请在 .env 中设置 ZHIPU_GLM_API_KEY")
    cfg = _get_model_config("glm_5_1")
    client = OpenAIClient(
        api_key=ZHIPU_GLM_API_KEY,
        base_url=ZHIPU_GLM_BASE_URL,
        model=model or cfg.get("model_id", "glm-5.1"),
        max_tokens=kwargs.pop("max_tokens", cfg.get("max_tokens", 8192)),
        temperature=kwargs.pop("temperature", cfg.get("temperature", 0.7)),
        **kwargs
    )
    return client.query(prompt)


def query_qwen(prompt: str, model: str = None, **kwargs) -> str:
    """调用阿里云百炼模型"""
    from config.api_config import ALI_BAILIAN_API_KEY, ALI_BAILIAN_BASE_URL
    if not ALI_BAILIAN_API_KEY:
        raise ValueError("阿里云百炼 API Key 未配置，请在 .env 中设置 ALI_BAILIAN_API_KEY")
    cfg = _get_model_config("qwen_plus")
    client = OpenAIClient(
        api_key=ALI_BAILIAN_API_KEY,
        base_url=ALI_BAILIAN_BASE_URL,
        model=model or cfg.get("model_id", "qwen-plus"),
        max_tokens=kwargs.pop("max_tokens", cfg.get("max_tokens", 4096)),
        temperature=kwargs.pop("temperature", cfg.get("temperature", 0.5)),
        **kwargs
    )
    return client.query(prompt)


def query_openai_compatible(prompt: str, api_key: str, base_url: str,
                            model: str, **kwargs) -> str:
    """通用OpenAI兼容调用"""
    client = OpenAIClient(
        api_key=api_key,
        base_url=base_url,
        model=model,
        **kwargs
    )
    return client.query(prompt)


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
    base_url = provider_config.get("base_url", "https://api.openai.com/v1")

    if cfg.get("non_openai"):
        client = AnthropicClient(api_key=api_key, model=model_id,
                                 max_tokens=max_tokens, temperature=temperature)
    else:
        client = OpenAIClient(api_key=api_key, base_url=base_url, model=model_id,
                              max_tokens=max_tokens, temperature=temperature, stream=stream)
    return client.query(prompt)

