# -*- coding: utf-8 -*-
"""
测试 utils/json_utils.py - JSON 提取工具
"""

import json
import pytest
from utils.json_utils import extract_json_from_string


class TestExtractJsonFromString:
    """测试从字符串中提取 JSON"""

    def test_extract_from_json_code_block(self):
        """从 ```json ... ``` 代码块中提取"""
        text = '```json\n{"key": "value", "num": 42}\n```'
        result = extract_json_from_string(text)
        assert result == {"key": "value", "num": 42}

    def test_extract_from_json_code_block_with_list(self):
        """从代码块中提取 JSON 数组"""
        text = '```json\n[1, 2, 3]\n```'
        result = extract_json_from_string(text)
        assert result == [1, 2, 3]

    def test_extract_plain_json_dict(self):
        """无代码块包裹时直接解析 JSON 字典"""
        text = '{"name": "test", "score": 95.5}'
        result = extract_json_from_string(text)
        assert result == {"name": "test", "score": 95.5}

    def test_extract_plain_json_list(self):
        """无代码块包裹时直接解析 JSON 数组"""
        text = '[{"id": 1}, {"id": 2}]'
        result = extract_json_from_string(text)
        assert result == [{"id": 1}, {"id": 2}]

    def test_extract_nested_json(self):
        """提取嵌套 JSON"""
        text = '```json\n{"outer": {"inner": [1, 2]}}\n```'
        result = extract_json_from_string(text)
        assert result == {"outer": {"inner": [1, 2]}}

    def test_json_code_block_with_extra_text(self):
        """代码块前后有额外文本"""
        text = 'Here is the result:\n```json\n{"status": "ok"}\n```\nEnd.'
        result = extract_json_from_string(text)
        assert result == {"status": "ok"}

    def test_invalid_json_raises_error(self):
        """无效 JSON 抛出 JSONDecodeError"""
        with pytest.raises(json.JSONDecodeError):
            extract_json_from_string("not json at all")

    def test_invalid_json_in_code_block_raises_error(self):
        """代码块内无效 JSON 抛出 JSONDecodeError"""
        with pytest.raises(json.JSONDecodeError):
            extract_json_from_string('```json\n{broken json}\n```')

    def test_empty_code_block_raises_error(self):
        """空代码块抛出 JSONDecodeError"""
        with pytest.raises(json.JSONDecodeError):
            extract_json_from_string('```json\n```')

    def test_empty_string_raises_error(self):
        """空字符串抛出 JSONDecodeError"""
        with pytest.raises(json.JSONDecodeError):
            extract_json_from_string("")

    def test_code_block_with_whitespace(self):
        """代码块内有额外空白"""
        text = '```json\n  \n{"a": 1}\n  \n```'
        result = extract_json_from_string(text)
        assert result == {"a": 1}

    def test_none_input_raises_error(self):
        """None 输入抛出 TypeError"""
        with pytest.raises((TypeError, AttributeError)):
            extract_json_from_string(None)

    def test_first_json_block_extracted_when_multiple(self):
        """多个代码块时只提取第一个"""
        text = '```json\n{"first": true}\n```\n```json\n{"second": true}\n```'
        result = extract_json_from_string(text)
        assert result == {"first": True}
