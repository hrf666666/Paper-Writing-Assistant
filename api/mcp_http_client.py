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


def mcp_zread_search(repo_name: str, query: str,
                     language: str = "en") -> Optional[str]:
    """
    调用 zread 搜索 GitHub 仓库文档/Issue

    Args:
        repo_name: 仓库 owner/repo（如 "vitejs/vite"）
        query: 搜索关键词
        language: 语言 zh/en

    Returns:
        搜索结果文本
    """
    return get_mcp_client().call_tool(
        "zread", "search_doc",
        {
            "repo_name": repo_name,
            "query": query,
            "language": language,
        },
        timeout=30,
    )


# ==================== 视觉理解 MCP（stdio 传输） ====================

import base64
import subprocess
import threading
from pathlib import Path


class MCPVisionClient:
    """
    视觉理解 MCP 客户端（stdio 传输）

    通过 npx 启动 @z_ai/mcp-server 子进程，使用 JSON-RPC over stdio 通信。
    提供：图像分析、OCR 文字提取、数据可视化理解、技术图表理解等能力。

    依赖：
    - npx（Node.js）
    - @z_ai/mcp-server 包
    - GLM_CODING_PLAN_API_KEY（作为 Z_AI_API_KEY）
    """

    def __init__(self):
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.RLock()
        self._next_id = 0
        self._initialized = False

    def _ensure_running(self) -> bool:
        """确保子进程已启动并完成 MCP 初始化"""
        if self._proc is not None and self._proc.poll() is None and self._initialized:
            return True

        # 清理旧进程
        self._cleanup()

        glm_key = _get_api_key()
        if not glm_key:
            logger.warning("MCP Vision: GLM_CODING_PLAN_API_KEY 未配置")
            return False

        try:
            self._proc = subprocess.Popen(
                ["npx", "-y", "@z_ai/mcp-server"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**os.environ, "Z_AI_API_KEY": glm_key, "Z_AI_MODE": "ZHIPU"},
            )
        except FileNotFoundError:
            logger.warning("MCP Vision: npx 未找到，无法启动 zai-mcp-server")
            return False
        except Exception as e:
            logger.warning(f"MCP Vision: 启动失败: {e}")
            return False

        # MCP initialize 握手
        init_resp = self._send_raw({
            "jsonrpc": "2.0", "id": self._next_id, "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05", "capabilities": {},
                "clientInfo": {"name": "Paper-Writing-Assistant", "version": "9.0"},
            },
        })
        if not init_resp or "error" in init_resp:
            logger.warning(f"MCP Vision: 初始化失败: {init_resp}")
            self._cleanup()
            return False

        # notifications/initialized
        self._send_notification({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

        self._initialized = True
        logger.info("MCP Vision: zai-mcp-server 初始化成功")
        return True

    def _send_raw(self, payload: dict, timeout: float = 15) -> Optional[dict]:
        """通过 stdin 发送 JSON-RPC，从 stdout 读取响应"""
        rpc_id = payload.get("id")
        self._next_id += 1

        raw = json.dumps(payload) + "\n"
        try:
            self._proc.stdin.write(raw.encode())
            self._proc.stdin.flush()
        except BrokenPipeError:
            logger.warning("MCP Vision: 子进程已退出")
            self._cleanup()
            return None

        # 读取响应（可能需要多行）
        deadline = time.monotonic() + timeout
        buf = b""
        while time.monotonic() < deadline:
            line = self._proc.stdout.readline()
            if not line:
                break
            buf += line
            try:
                data = json.loads(buf.decode())
                if data.get("id") == rpc_id:
                    return data
                buf = b""  # 不是目标响应，继续读
            except json.JSONDecodeError:
                continue

        return None

    def _send_notification(self, payload: dict):
        """发送 JSON-RPC 通知（无 id，不需要响应）"""
        raw = json.dumps(payload) + "\n"
        try:
            self._proc.stdin.write(raw.encode())
            self._proc.stdin.flush()
        except Exception:
            pass

    def call_tool(self, tool_name: str, arguments: dict,
                  timeout: int = 60) -> Optional[str]:
        """
        调用视觉 MCP 工具

        Args:
            tool_name: 工具名（analyze_image, extract_text_from_screenshot 等）
            arguments: 工具参数（image_path 应为 base64 data URL）
            timeout: 超时秒数

        Returns:
            工具返回文本，失败返回 None
        """
        with self._lock:
            if not self._ensure_running():
                return None

            rpc_id = self._next_id
            result = self._send_raw({
                "jsonrpc": "2.0", "id": rpc_id, "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
            }, timeout=timeout)

        if not result:
            return None

        if "error" in result:
            err = result["error"]
            logger.warning(f"MCP Vision 工具错误 [{err.get('code')}]: {err.get('message')}")
            return None

        # 提取 content 中的文本
        res = result.get("result", {})
        content_blocks = res.get("content", [])
        if res.get("isError"):
            err_text = " ".join(b.get("text", "") for b in content_blocks if isinstance(b, dict))
            logger.warning(f"MCP Vision 工具错误: {err_text[:200]}")
            return None

        texts = []
        for block in content_blocks:
            if isinstance(block, dict) and block.get("type") == "text":
                texts.append(block.get("text", ""))
            elif isinstance(block, str):
                texts.append(block)

        raw_text = "\n".join(texts)
        return raw_text if raw_text.strip() else None

    def _cleanup(self):
        """清理子进程"""
        if self._proc is not None:
            try:
                if self._proc.poll() is None:
                    self._proc.kill()
                    self._proc.wait(timeout=5)
            except Exception:
                pass
            self._proc = None
        self._initialized = False

    def close(self):
        """关闭视觉 MCP 客户端"""
        self._cleanup()
        logger.info("MCP Vision: 客户端已关闭")

    def __del__(self):
        self._cleanup()


# ── 视觉 MCP 全局单例 ──

_vision_client: Optional[MCPVisionClient] = None


def get_vision_client() -> MCPVisionClient:
    """获取全局视觉 MCP 客户端"""
    global _vision_client
    if _vision_client is None:
        _vision_client = MCPVisionClient()
    return _vision_client


def _local_path_to_data_url(file_path: str) -> Optional[str]:
    """将本地图片转为 base64 data URL"""
    try:
        p = Path(file_path)
        if not p.exists():
            logger.warning(f"MCP Vision: 文件不存在: {file_path}")
            return None
        img_bytes = p.read_bytes()
        b64 = base64.b64encode(img_bytes).decode()
        mime_map = {
            ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".webp": "image/webp", ".gif": "image/gif",
        }
        mime = mime_map.get(p.suffix.lower(), "image/png")
        return f"data:{mime};base64,{b64}"
    except Exception as e:
        logger.warning(f"MCP Vision: 编码失败 {file_path}: {e}")
        return None


# ── 视觉工具便捷函数 ──

def mcp_analyze_image(image_path: str, prompt: str = "") -> Optional[str]:
    """
    通用图像分析

    Args:
        image_path: 本地图片路径
        prompt: 分析提示（为空则通用描述）

    Returns:
        分析结果文本
    """
    args = {"image_source": image_path}
    if prompt:
        args["prompt"] = prompt
    return get_vision_client().call_tool("analyze_image", args)


def mcp_extract_text(image_path: str, language_hint: str = "") -> Optional[str]:
    """
    从图片中提取文字（OCR）

    Args:
        image_path: 本地图片路径
        language_hint: 语言提示（如 "zh", "en"）

    Returns:
        提取的文字内容
    """
    args = {"image_source": image_path}
    if language_hint:
        args["prompt"] = f"Extract text, language hint: {language_hint}"
    return get_vision_client().call_tool("extract_text_from_screenshot", args)


def mcp_analyze_data_viz(image_path: str, focus: str = "") -> Optional[str]:
    """
    分析数据可视化图表

    Args:
        image_path: 本地图片路径
        focus: 关注点描述

    Returns:
        图表分析结果
    """
    args = {"image_source": image_path}
    if focus:
        args["prompt"] = focus
    return get_vision_client().call_tool("analyze_data_visualization", args)


def mcp_understand_diagram(image_path: str, prompt: str = "") -> Optional[str]:
    """
    理解技术图表/架构图

    Args:
        image_path: 本地图片路径
        prompt: 具体问题或描述要求

    Returns:
        图表理解结果
    """
    args = {"image_source": image_path}
    if prompt:
        args["prompt"] = prompt
    return get_vision_client().call_tool("understand_technical_diagram", args)


def mcp_diagnose_screenshot(image_path: str, context: str = "") -> Optional[str]:
    """
    诊断错误截图

    Args:
        image_path: 本地截图路径
        context: 上下文信息

    Returns:
        诊断结果
    """
    args = {"image_source": image_path}
    if context:
        args["context"] = context
    return get_vision_client().call_tool("diagnose_error_screenshot", args)
