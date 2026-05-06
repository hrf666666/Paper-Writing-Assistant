# -*- coding: utf-8 -*-
"""
统一OpenAI兼容接口

所有使用OpenAI兼容API的国内服务商（智谱GLM、阿里云百炼等）
都通过这一个模块统一调用，无需为每个模型创建单独文件。

设计原则：
1. 配置驱动：模型列表从 config/api_config.py 的 PROVIDERS 读取
2. 统一接口：所有 OpenAI 兼容 API 走同一调用路径
3. 流式支持：推理模型（QwQ等）自动启用流式并提取答案
4. 错误追踪：统一的异常和日志
"""

import time
import logging
from typing import Optional, Dict, Any, List

from openai import OpenAI

logger = logging.getLogger(__name__)


class OpenAICompatibleClient:
    """
    统一的OpenAI兼容API客户端

    支持：
    - 智谱GLM（glm-4-plus, glm-5.1 等）
    - 阿里云百炼（qwen-plus, qwen-turbo, qwen-max, qwq-32b 等）
    - 任何 OpenAI 兼容端点
    """

    def __init__(self, api_key: str, base_url: str, model: str,
                 max_tokens: int = 8192, temperature: float = 0.7,
                 stream: bool = False, timeout: int = 300):
        self.api_key = api_key
        self.base_url = base_url
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
        """
        调用模型获取响应

        Args:
            prompt: 用户输入
            system_prompt: 系统提示（可选）
            temperature: 覆盖默认温度
            max_tokens: 覆盖默认最大token数

        Returns:
            str: 模型输出文本
        """
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
                return self._query_stream(messages, temp, max_tok)
            else:
                return self._query_sync(messages, temp, max_tok)
        except Exception as e:
            logger.error(f"[OpenAICompatible] {self.model} 调用失败: {e}")
            raise

    def _query_sync(self, messages: list, temperature: float, max_tokens: int) -> str:
        """同步调用（普通模型）"""
        completion = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return completion.choices[0].message.content

    def _query_stream(self, messages: list, temperature: float, max_tokens: int) -> str:
        """流式调用（推理模型如QwQ等）"""
        answer_content = ""

        completion = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
        )

        is_answering = False
        for chunk in completion:
            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta

            # 推理模型有 reasoning_content 字段
            if hasattr(delta, 'reasoning_content') and delta.reasoning_content is not None:
                # 思考过程，跳过
                continue
            else:
                if delta.content and delta.content != "" and not is_answering:
                    is_answering = True
                if delta.content:
                    answer_content += delta.content

        return answer_content

    def _is_reasoning_model(self) -> bool:
        """判断是否为推理模型（需要流式调用）"""
        reasoning_keywords = ["qwq", "o1", "o3", "deepseek-r", "reasoning"]
        return any(kw in self.model.lower() for kw in reasoning_keywords)

    def __repr__(self):
        return f"OpenAICompatibleClient(model={self.model}, base_url={self.base_url})"


# ========== 便捷函数（兼容旧的调用方式） ==========

def query_glm(prompt: str, model: str = "glm-5.1", **kwargs) -> str:
    """调用智谱GLM模型"""
    from config.api_config import ZHIPU_GLM_API_KEY, ZHIPU_GLM_BASE_URL
    if not ZHIPU_GLM_API_KEY:
        raise ValueError("智谱GLM API Key 未配置，请在 .env 中设置 ZHIPU_GLM_API_KEY")
    client = OpenAICompatibleClient(
        api_key=ZHIPU_GLM_API_KEY,
        base_url=ZHIPU_GLM_BASE_URL,
        model=model,
        **kwargs
    )
    return client.query(prompt)


def query_qwen(prompt: str, model: str = "qwen-plus", **kwargs) -> str:
    """调用阿里云百炼模型"""
    from config.api_config import ALI_BAILIAN_API_KEY, ALI_BAILIAN_BASE_URL
    if not ALI_BAILIAN_API_KEY:
        raise ValueError("阿里云百炼 API Key 未配置，请在 .env 中设置 ALI_BAILIAN_API_KEY")
    client = OpenAICompatibleClient(
        api_key=ALI_BAILIAN_API_KEY,
        base_url=ALI_BAILIAN_BASE_URL,
        model=model,
        **kwargs
    )
    return client.query(prompt)


def query_openai_compatible(prompt: str, api_key: str, base_url: str,
                            model: str, **kwargs) -> str:
    """通用OpenAI兼容调用"""
    client = OpenAICompatibleClient(
        api_key=api_key,
        base_url=base_url,
        model=model,
        **kwargs
    )
    return client.query(prompt)


# ========== 兼容旧接口的适配器 ==========

def query_qwen_plus(prompt):
    """兼容旧接口：qwen_plus"""
    return query_qwen(prompt, model="qwen-plus")

def query_qwen_72b(prompt):
    """兼容旧接口：qwen_72b"""
    return query_qwen(prompt, model="qwen-72b-instruct")

def query_qwen_long(prompt):
    """兼容旧接口：qwen_long"""
    return query_qwen(prompt, model="qwen-long", max_tokens=10000)

def query_qwen_qwq(prompt):
    """兼容旧接口：qwen_qwq"""
    return query_qwen(prompt, model="qwq-32b", stream=True, max_tokens=8192)
