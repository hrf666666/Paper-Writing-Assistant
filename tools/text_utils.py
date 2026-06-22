# -*- coding: utf-8 -*-
"""
公共工具函数 — 消除跨模块重复代码

v14 清理：删除 4 个死函数（strip_markdown_code_block /
parse_json_response / normalize_authors / authors_to_str），
仅保留 generate_bib_key（3 处活跃引用）。
- JSON 解析统一走 agent.api_client.parse_json_response
"""

import re
from typing import Any


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
