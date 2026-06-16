# -*- coding: utf-8 -*-
"""
公共 JSON 解析工具

从 chapter1_utils 提取到公共层，供 agent 和 skill 层共同使用。
"""

import re
import json


def extract_json_from_string(text):
    """
    从文本中提取JSON内容

    Args:
        text: 包含JSON的字符串，可能被```json和```包围

    Returns:
        dict or list: 解析后的JSON对象

    Raises:
        json.JSONDecodeError: 如果无法解析JSON
    """
    pattern = r'```json\s*([\s\S]*?)\s*```'
    match = re.search(pattern, text)

    if match:
        json_str = match.group(1)
        return json.loads(json_str)
    else:
        return json.loads(text)
