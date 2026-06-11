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


def build_citation_instruction(min_cites: int = 5) -> str:
    """
    构建统一的引用指令片段。所有 chapter prompt 统一使用。

    citation_context 由 loop.py 的 _build_citation_context() 生成，
    包含 CITE KEY REFERENCE LIST。每个 prompt 末尾必须同时注入
    {citation_context} 和 build_citation_instruction()。
    """
    return (
        f"**引用要求**（关键）：\n"
        f"- 本节至少引用 {min_cites} 篇不同的参考文献\n"
        f"- 使用 \\cite{{key}} 格式。**CITE KEY REFERENCE LIST** 中列出了所有可用的 cite key\n"
        f"- **只能使用列表中给出的 key，禁止编造不存在的 cite key**\n"
        f"- 引用应自然融入句式，每处引用都要有明确的论述目的\n"
    )


def build_style_instruction(style_guide: dict, chapter_org: dict,
                           chapter_name: str = None,
                           is_related_work: bool = False) -> str:
    """
    统一的写作风格指导构建函数（替代 ch1/ch2/ch3/ch4 各自的 _build_style_instruction 副本）

    优先级：VenueAdapter (P1) → IEEE Trans profile (P2) → 学术写作指南 (P4) → style_guide → chapter_org
    """
    # P1: VenueAdapter（统一风格中心）
    if chapter_name:
        try:
            from agent.venue_adapter import VenueAdapter
            adapter = VenueAdapter()
            style_text = adapter.build_chapter_style_instruction(chapter_name)
            if style_text and len(style_text) > 100:
                return style_text
        except Exception as e:
            logger.debug(f"VenueAdapter 加载失败: {e}")

    instruction = "**写作风格指导**：\n"

    # P2: IEEE Trans 期刊风格配置
    try:
        from config.ieee_trans_style_profile import (
            get_ieee_trans_style_profile,
            get_section_requirements,
            get_red_flags,
        )
        profile = get_ieee_trans_style_profile()
        sec_name = chapter_name or "Introduction"
        sec_req = get_section_requirements(sec_name)

        instruction += f"\n**IEEE Transactions 期刊特定规则**（P2 优先级，必须遵守）：\n"
        if sec_req:
            for key, val in sec_req.items():
                if isinstance(val, list):
                    instruction += f"- {key}：\n"
                    for item in val:
                        instruction += f"  - {item}\n"
                else:
                    instruction += f"- {key}：{val}\n"

        try:
            red_flags = get_red_flags()
            if red_flags:
                instruction += f"\n### 禁止模式 (Red Flags)\n"
                for flag in red_flags[:5]:
                    instruction += f"- {flag}\n"
        except Exception:
            pass

        lang = profile.get('language_style_profile', {})
        if lang:
            instruction += f"\n### 语言风格\n"
            for k, v in lang.items():
                instruction += f"- {k}：{v}\n"
        instruction += "\n"
    except Exception as e:
        logger.debug(f"IEEE Trans 风格配置加载失败: {e}")

    # P3: 特殊章节要求
    if is_related_work:
        instruction += """
- Related Work 特殊要求：
  1. 每篇被讨论的工作用1-2段描述，先说方法核心思路再说结果/局限
  2. 工作之间的过渡句要体现递进或对比关系
  3. 每个小节的最后一段集中讨论该类方法的不足
  4. 不足的论述要具体
  5. 引用要自然融入句式
"""

    # P4: 学术写作风格指南
    try:
        style_guide_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "skills", "academic_writing_style", "style_guide.md"
        )
        if os.path.exists(style_guide_path):
            with open(style_guide_path, 'r', encoding='utf-8') as f:
                style_guide_content = f.read()
            instruction += f"\n**学术写作基础规范**（P4 优先级）：\n"
            instruction += style_guide_content[:1500]
            instruction += "\n"
    except Exception as e:
        logger.debug(f"风格指南加载失败: {e}")

    # P5: 参考论文提取的风格
    if style_guide and isinstance(style_guide, dict):
        sentence_patterns = style_guide.get("句式特征", {})
        if sentence_patterns:
            instruction += "- 常用句式模式：\n"
            for pattern_type, examples in sentence_patterns.items():
                if isinstance(examples, (list, dict)):
                    instruction += f"  {pattern_type}: {examples}\n"
        vocabulary = style_guide.get("用词特征", [])
        if vocabulary:
            instruction += f"- 学术用词：{vocabulary[:20]}\n"
        citation_style = style_guide.get("引用风格", {})
        if citation_style:
            instruction += f"- 引用风格：{citation_style}\n"

    if chapter_org and isinstance(chapter_org, dict):
        structure = chapter_org.get("章节结构", [])
        if structure:
            instruction += f"- 参考组织结构：{structure}\n"
        patterns = chapter_org.get("关键句式模板", {})
        if patterns:
            instruction += f"- 关键句式模板：\n"
            for k, v in patterns.items():
                instruction += f"  {k}: {v}\n"

    instruction += """
- 重要要求：
  1. 文风必须学术化，禁止口语化表达
  2. 每句话都要有明确的论述目的，避免空洞的过渡句
  3. 论述要有逻辑层次：从宏观到微观，从问题到方案
  4. 引用要自然融入句式，不能生硬堆砌
  5. **严格避免 AI 风格词汇**（如 revolutionize, groundbreaking, unprecedented 等）
  6. **括号内容不超过 20 词**，超长内容应拆分为独立句子
  7. **句子长度控制在 20-30 词**，避免超过 40 词的长句
"""

    return instruction
