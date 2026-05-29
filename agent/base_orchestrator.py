# -*- coding: utf-8 -*-
"""
LLM 调用基类 - 消除 skill_orchestrators 中的重复模式

所有 skill_orchestrators 共享以下模式：
1. 延迟初始化 API 客户端
2. 调用 call_generation / call_reasoning / call_light
3. JSON 解析（带重试）
4. 保存输出到 workspace/output/

本基类将这些模式统一封装，子类只需关注 prompt 构建和业务逻辑。
"""

import json
import logging
import os
from typing import Any, Optional, Union

logger = logging.getLogger(__name__)

# 默认输出目录
DEFAULT_OUTPUT_DIR = "workspace/output"


class BaseOrchestrator:
    """
    LLM 调用基类

    使用方式：
        class MyOrchestrator(BaseOrchestrator):
            def run(self, project_data, ref_data):
                result = self.call_generation("prompt...")
                data = self.parse_json(result)
                self.save_output("my_file.json", data)
    """

    def __init__(self, output_dir: str = None):
        self._api = None
        self._output_dir = output_dir or DEFAULT_OUTPUT_DIR
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @property
    def api(self):
        """延迟获取 API 客户端单例"""
        if self._api is None:
            from agent.api_client import get_api_client
            self._api = get_api_client()
        return self._api

    @property
    def output_dir(self) -> str:
        return self._output_dir

    # ---- LLM 调用封装 ----

    def call_generation(self, prompt: str, **kwargs) -> str:
        """调用生成模型"""
        return self.api.call_generation(prompt, **kwargs)

    def call_reasoning(self, prompt: str, **kwargs) -> str:
        """调用推理模型"""
        return self.api.call_reasoning(prompt, **kwargs)

    def call_light(self, prompt: str, **kwargs) -> str:
        """调用轻量模型"""
        return self.api.call_light(prompt, **kwargs)

    def call_evaluation(self, prompt: str, **kwargs) -> str:
        """调用评价模型（与执行模型跨 provider）"""
        return self.api.call_evaluation(prompt, **kwargs)

    # ---- JSON 解析 ----

    def parse_json(self, response: str, default: Any = None) -> Any:
        """
        安全解析 LLM 返回中的 JSON 内容

        支持以下格式：
        - 纯 JSON 字符串
        - ```json ... ``` 包裹的 markdown
        - 带 ``` ... ``` 包裹的 JSON
        """
        return self.api.parse_json_response(response, default=default)

    def parse_json_with_retry(self, prompt: str, call_method: str = "call_reasoning",
                              max_attempts: int = 2, default: Any = None,
                              expected_type: type = None, **call_kwargs) -> Any:
        """
        带重试的 JSON 解析：调用 LLM → 解析 JSON → 失败则重试

        Args:
            prompt: LLM prompt
            call_method: 调用方法名 ("call_generation", "call_reasoning", "call_light")
            max_attempts: 最大尝试次数
            default: 解析失败时的默认返回值
            expected_type: 期望的 JSON 类型 (list, dict 等)
            **call_kwargs: 传递给调用方法的额外参数

        Returns:
            解析后的 JSON 对象，或 default
        """
        caller = getattr(self, call_method)
        for attempt in range(1, max_attempts + 1):
            try:
                response = caller(prompt, **call_kwargs)
                result = self.parse_json(response)
                if result is not None:
                    if expected_type is not None and not isinstance(result, expected_type):
                        self._logger.warning(
                            f"JSON 类型不匹配 (期望 {expected_type.__name__}, "
                            f"得到 {type(result).__name__}), 尝试 {attempt}/{max_attempts}"
                        )
                        continue
                    return result
                self._logger.warning(f"JSON 解析返回 None, 尝试 {attempt}/{max_attempts}")
            except (json.JSONDecodeError, ValueError) as e:
                self._logger.warning(f"JSON 解析失败 (尝试 {attempt}/{max_attempts}): {e}")
            except Exception as e:
                self._logger.error(f"LLM 调用失败 (尝试 {attempt}/{max_attempts}): {e}")
                break  # API 错误不重试 JSON 解析
        return default

    # ---- 文件 I/O ----

    def save_output(self, filename: str, content: Union[str, dict, list],
                    subdir: str = None, encoding: str = "utf-8") -> str:
        """
        保存输出文件到 workspace/output/

        Args:
            filename: 文件名
            content: 文件内容（str 直接写入，dict/list 自动 json 序列化）
            subdir: 子目录（可选）
            encoding: 文件编码

        Returns:
            保存的文件绝对路径
        """
        target_dir = os.path.join(self._output_dir, subdir) if subdir else self._output_dir
        os.makedirs(target_dir, exist_ok=True)
        filepath = os.path.join(target_dir, filename)

        try:
            with open(filepath, "w", encoding=encoding) as f:
                if isinstance(content, (dict, list)):
                    json.dump(content, f, ensure_ascii=False, indent=2)
                else:
                    f.write(content)
            self._logger.debug(f"已保存: {filepath}")
            return filepath
        except Exception as e:
            self._logger.error(f"保存文件失败 {filepath}: {e}")
            raise

    def load_output(self, filename: str, subdir: str = None,
                    encoding: str = "utf-8") -> Any:
        """
        从 workspace/output/ 加载文件

        对于 .json 文件自动解析，其他文件返回字符串
        """
        target_dir = os.path.join(self._output_dir, subdir) if subdir else self._output_dir
        filepath = os.path.join(target_dir, filename)

        try:
            with open(filepath, "r", encoding=encoding) as f:
                if filename.endswith(".json"):
                    return json.load(f)
                return f.read()
        except FileNotFoundError:
            self._logger.debug(f"文件不存在: {filepath}")
            return None
        except Exception as e:
            self._logger.error(f"加载文件失败 {filepath}: {e}")
            return None
