# -*- coding: utf-8 -*-
"""
Tool 基类 - 解耦 tools → agent 反向依赖

问题：tools/ 直接 `from agent.api_client import get_api_client` 违反分层架构。
方案：通过依赖注入，由调用方（loop.py）设置 api_client，tools 不再 import agent。

使用方式：
1. 调用方启动时：`setup_tool_api(api_client_instance)`
2. Tool 文件中：`from tools.base_tool import get_tool_api`
3. 获取客户端：`api = get_tool_api()`
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# 模块级 API 客户端引用（由调用方通过 setup_tool_api 设置）
_api_client: Optional[object] = None


def setup_tool_api(api_client):
    """
    设置 Tool 层使用的 API 客户端

    由调用方（如 loop.py）在启动时调用：
        from tools.base_tool import setup_tool_api
        setup_tool_api(self.api_client)

    Args:
        api_client: UnifiedAPIClient 实例
    """
    global _api_client
    _api_client = api_client
    logger.debug("[BaseTool] API 客户端已设置")


def get_tool_api():
    """
    获取 Tool 层的 API 客户端

    如果未设置，自动回退到 agent.api_client 的全局单例。
    这个回退保证向后兼容（旧代码仍可直接调用 tools）。

    Returns:
        UnifiedAPIClient 实例
    """
    global _api_client
    if _api_client is None:
        # 回退：延迟导入 agent 层（仅在未显式设置时）
        from agent.api_client import get_api_client
        _api_client = get_api_client()
        logger.debug("[BaseTool] API 客户端自动初始化（回退模式）")
    return _api_client


class BaseTool:
    """
    Tool 基类

    提供统一的 API 客户端访问、日志记录和文件保存能力。
    tools/ 下的工具类可继承此基类，不再直接依赖 agent 层。

    使用方式：
        class MyTool(BaseTool):
            def run(self, data):
                result = self.call_generation("prompt...")
                return self.parse_json(result)

        # 调用方：
        tool = MyTool()
        tool.run(data)
    """

    def __init__(self, api_client=None):
        self._api = api_client
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @property
    def api(self):
        """延迟获取 API 客户端"""
        if self._api is None:
            self._api = get_tool_api()
        return self._api

    def call_generation(self, prompt: str, **kwargs) -> str:
        """调用生成模型"""
        return self.api.call_generation(prompt, **kwargs)

    def call_reasoning(self, prompt: str, **kwargs) -> str:
        """调用推理模型"""
        return self.api.call_reasoning(prompt, **kwargs)

    def call_light(self, prompt: str, **kwargs) -> str:
        """调用轻量模型"""
        return self.api.call_light(prompt, **kwargs)

    def parse_json(self, response: str, default=None):
        """安全解析 JSON"""
        return self.api.parse_json_response(response, default=default)
