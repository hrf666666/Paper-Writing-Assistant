# -*- coding: utf-8 -*-
"""
公共工具函数 — 消除跨模块重复代码

v12.2: 从 12 处重复中抽取的公共逻辑
"""

import re
import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def strip_markdown_code_block(text: str) -> str:
    """
    清理 LLM 返回中的 Markdown 代码块包裹（```json ... ``` 或 ``` ... ```）。
    在项目中被 12+ 处重复实现，统一抽取。
    """
    if not text:
        return ""
    text = text.strip()
    # 去掉 ```json 或 ``` 开头和 ``` 结尾
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].strip() in ("```json", "```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()


def parse_json_response(response: str, default=None) -> Any:
    """
    清理并解析 LLM 返回的 JSON。
    自动处理 markdown 包裹和常见格式问题。
    """
    if not response:
        return default
    cleaned = strip_markdown_code_block(response)
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        return default


def normalize_authors(authors) -> List[Dict]:
    """
    统一作者格式为 [{"name": "Full Name"}, ...]
    处理各种输入格式：
    - ["name1", "name2"]
    - [{"name": "name1"}, {"name": "name2"}]
    - "name1, name2"
    """
    if not authors:
        return []
    if isinstance(authors, str):
        return [{"name": a.strip()} for a in authors.split(",") if a.strip()]
    result = []
    for a in authors:
        if isinstance(a, dict):
            name = a.get("name", "")
            if name:
                result.append({"name": name})
        elif isinstance(a, str) and a.strip():
            result.append({"name": a.strip()})
    return result


def authors_to_str(authors, max_authors: int = 3) -> str:
    """
    作者列表 → 显示字符串 "Smith, Jones et al."
    """
    names = []
    for a in (authors or []):
        if isinstance(a, dict):
            names.append(a.get("name", ""))
        elif isinstance(a, str):
            names.append(a)
    names = [n for n in names if n]
    if not names:
        return ""
    result = ", ".join(names[:max_authors])
    if len(names) > max_authors:
        result += " et al."
    return result


def generate_bib_key(authors: list, year: Any, title: str, num: int = 0) -> str:
    """
    生成确定性 BibTeX cite key: surname + year。
    同一篇论文无论在哪个模块调用，始终生成相同的 key。
    `num` 参数已废弃（保留仅为 API 兼容），不再参与 key 生成。
    冲突消解由调用方统一处理（_build_cite_key_list 中的 _cite_key_map）。
    """
    surname = ""
    if authors:
        first = authors[0]
        name = first.get("name", "") if isinstance(first, dict) else str(first)
        surname = name.split()[-1].lower() if name else ""
        surname = re.sub(r'[^a-z]', '', surname)

    if not surname or len(surname) < 2:
        words = re.findall(r'[a-zA-Z]+', title)
        stopwords = {'the', 'a', 'an', 'of', 'for', 'and', 'in', 'on', 'to',
                     'from', 'with', 'by', 'using', 'based'}
        meaningful = [w.lower() for w in words
                      if w.lower() not in stopwords and len(w) > 2]
        surname = (meaningful[0][:6] + meaningful[1][:4]) if len(meaningful) >= 2 \
            else meaningful[0][:10] if meaningful else "ref"

    yr = str(year) if year else ""
    key = f"{surname}{yr}"
    return key[:20]
