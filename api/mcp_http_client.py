# -*- coding: utf-8 -*-
"""
智谱 MCP 独立客户端

通过 GLM Coding Plan API Key 直接调用 MCP 服务：
- web-search-prime: 网络搜索增强（StreamableHTTP）
- web-reader: 网页内容读取（StreamableHTTP）
- zread: GitHub 仓库文档/Issue 搜索（StreamableHTTP）
- zai_vision: 视觉理解（stdio @z_ai/mcp-server）

HTTP 服务协议：StreamableHTTP (JSON-RPC over HTTP + SSE)
视觉服务协议：stdio (JSON-RPC over subprocess stdin/stdout)
文档：https://open.bigmodel.cn/dev/api/mcp
"""

import json
import logging
import os
import time
import uuid
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)

# MCP 服务端点
MCP_ENDPOINTS = {
    "web-search-prime": "https://open.bigmodel.cn/api/mcp/web_search_prime/mcp",
    "web-reader": "https://open.bigmodel.cn/api/mcp/web_reader/mcp",
    "zread": "https://open.bigmodel.cn/api/mcp/zread/mcp",
}


def _get_api_key() -> str:
    """获取 GLM Coding Plan API Key"""
    from config.api_config import GLM_CODING_PLAN_API_KEY
    return GLM_CODING_PLAN_API_KEY


class MCPHttpClient:
    """
    智谱 MCP StreamableHTTP 独立客户端

    工作流程：
    1. initialize → 获取 Mcp-Session-Id
    2. notifications/initialized → 确认初始化
    3. tools/call → 调用工具（带 Mcp-Session-Id）
    """

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key
        self._session = requests.Session()
        self._session_ids: Dict[str, str] = {}  # server_name -> session_id

    @property
    def api_key(self) -> str:
        if self._api_key is None:
            self._api_key = _get_api_key()
        return self._api_key

    def _make_headers(self, server_name: Optional[str] = None) -> dict:
        """构造请求头，如果已初始化则带上 Mcp-Session-Id"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": self.api_key,
        }
        if server_name and server_name in self._session_ids:
            headers["Mcp-Session-Id"] = self._session_ids[server_name]
        return headers

    def _send_jsonrpc(self, server_name: str, method: str,
                      params: Optional[dict] = None,
                      timeout: int = 30) -> Any:
        """
        发送 JSON-RPC 请求到 MCP 服务

        Args:
            server_name: MCP 服务名（web-search-prime, web-reader, zread）
            method: JSON-RPC 方法名
            params: 方法参数
            timeout: 请求超时（秒）

        Returns:
            JSON-RPC 响应的 result 字段
        """
        if server_name not in MCP_ENDPOINTS:
            raise ValueError(
                f"未知的 MCP 服务: {server_name}，可选: {list(MCP_ENDPOINTS.keys())}"
            )

        url = MCP_ENDPOINTS[server_name]
        request_id = str(uuid.uuid4())

        payload: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }
        if params:
            payload["params"] = params

        try:
            resp = self._session.post(
                url,
                headers=self._make_headers(server_name),
                json=payload,
                timeout=timeout,
            )
            resp.raise_for_status()

            # 处理 SSE (text/event-stream) 或普通 JSON 响应
            content_type = resp.headers.get("Content-Type", "")
            if "text/event-stream" in content_type:
                return self._parse_sse_response(resp.text, request_id)
            else:
                data = resp.json()
                if "error" in data:
                    error = data["error"]
                    raise Exception(
                        f"MCP 错误 [{error.get('code')}]: {error.get('message')}"
                    )
                return data.get("result")

        except requests.exceptions.Timeout:
            logger.warning(f"MCP {server_name} 请求超时 ({timeout}s)")
            return None
        except requests.exceptions.RequestException as e:
            logger.warning(f"MCP {server_name} 请求失败: {e}")
            return None

    def _parse_sse_response(self, text: str, request_id: str) -> Any:
        """解析 SSE 格式的响应"""
        result = None
        for line in text.split("\n"):
            line = line.strip()
            if not line.startswith("data:"):
                continue
            data_str = line[5:].strip()
            if not data_str:
                continue
            try:
                data = json.loads(data_str)
                # 匹配对应 request_id 的响应
                if data.get("id") == request_id:
                    if "error" in data:
                        error = data["error"]
                        raise Exception(
                            f"MCP 错误 [{error.get('code')}]: {error.get('message')}"
                        )
                    result = data.get("result")
            except json.JSONDecodeError:
                continue
        return result

    def _initialize(self, server_name: str) -> bool:
        """
        初始化 MCP 会话（发送 initialize + initialized 通知）
        保存 Mcp-Session-Id 用于后续请求
        """
        if server_name in self._session_ids:
            return True

        url = MCP_ENDPOINTS[server_name]

        # Step 1: initialize 请求
        try:
            resp = self._session.post(
                url,
                headers=self._make_headers(),  # 此时无 session_id
                json={
                    "jsonrpc": "2.0",
                    "id": str(uuid.uuid4()),
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {},
                        "clientInfo": {
                            "name": "Paper-Writing-Assistant",
                            "version": "6.0",
                        },
                    },
                },
                timeout=10,
            )
            resp.raise_for_status()
        except Exception as e:
            logger.warning(f"MCP {server_name} 初始化请求失败: {e}")
            return False

        # 提取 Mcp-Session-Id
        session_id = resp.headers.get("Mcp-Session-Id")
        if not session_id:
            logger.warning(f"MCP {server_name} 响应中无 Mcp-Session-Id")
            return False

        self._session_ids[server_name] = session_id
        logger.debug(f"MCP {server_name} 获取 session: {session_id[:8]}...")

        # Step 2: initialized 通知
        try:
            self._session.post(
                url,
                headers=self._make_headers(server_name),
                json={
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                },
                timeout=10,
            )
        except Exception:
            pass  # 通知不需要响应

        logger.info(f"MCP {server_name} 初始化成功")
        return True

    def call_tool(self, server_name: str, tool_name: str,
                  arguments: dict, timeout: int = 30) -> Optional[str]:
        """
        调用 MCP 工具

        Args:
            server_name: MCP 服务名
            tool_name: 工具名
            arguments: 工具参数
            timeout: 超时秒数

        Returns:
            工具返回的文本内容，失败返回 None
        """
        if not self.api_key:
            logger.debug("GLM_CODING_PLAN_API_KEY 未配置，MCP 不可用")
            return None

        # 确保会话已初始化
        if not self._initialize(server_name):
            return None

        result = self._send_jsonrpc(
            server_name,
            method="tools/call",
            params={
                "name": tool_name,
                "arguments": arguments,
            },
            timeout=timeout,
        )

        if result is None:
            return None

        # 提取 content 中的文本
        return self._extract_tool_content(result)

    def _extract_tool_content(self, result: Any) -> Optional[str]:
        """从 tools/call 结果中提取文本内容"""
        if isinstance(result, dict):
            content = result.get("content", [])
            if isinstance(content, list):
                texts = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        texts.append(item.get("text", ""))
                if texts:
                    return "\n".join(texts)
            # 兜底
            return json.dumps(result, ensure_ascii=False)
        if isinstance(result, str):
            return result
        return None

    def close(self):
        """关闭 HTTP 会话"""
        self._session.close()
        self._session_ids.clear()


# ========== 全局单例（延迟初始化） ==========

_client: Optional[MCPHttpClient] = None


def get_mcp_client() -> MCPHttpClient:
    """获取全局 MCP HTTP 客户端"""
    global _client
    if _client is None:
        _client = MCPHttpClient()
    return _client


# ========== 便捷封装函数 ==========

def mcp_web_search(search_query: str,
                   search_domain_filter: str = "",
                   search_recency_filter: str = "noLimit",
                   content_size: str = "medium",
                   location: str = "cn") -> Optional[str]:
    """
    调用 web-search-prime 进行网络搜索

    Args:
        search_query: 搜索内容（建议不超过70字符）
        search_domain_filter: 限定搜索域名（如 arxiv.org）
        search_recency_filter: 时间范围 oneDay/oneWeek/oneMonth/oneYear/noLimit
        content_size: 摘要大小 medium(400-600字)/high(2500字)
        location: 地区 cn/us

    Returns:
        搜索结果文本（JSON）
    """
    args = {
        "search_query": search_query,
        "content_size": content_size,
        "location": location,
    }
    if search_domain_filter:
        args["search_domain_filter"] = search_domain_filter
    if search_recency_filter != "noLimit":
        args["search_recency_filter"] = search_recency_filter

    return get_mcp_client().call_tool(
        "web-search-prime", "web_search_prime", args, timeout=30
    )


def mcp_web_reader(url: str,
                   return_format: str = "markdown",
                   timeout_seconds: int = 30,
                   retain_images: bool = False) -> Optional[str]:
    """
    调用 web-reader 读取网页内容

    Args:
        url: 目标网页 URL
        return_format: 返回格式 markdown/text
        timeout_seconds: 读取超时秒数
        retain_images: 是否保留图片

    Returns:
        网页内容（Markdown 或纯文本）
    """
    return get_mcp_client().call_tool(
        "web-reader", "webReader",
        {
            "url": url,
            "return_format": return_format,
            "timeout": timeout_seconds,
            "retain_images": retain_images,
        },
        timeout=timeout_seconds + 10,
    )


