# -*- coding: utf-8 -*-
"""
Pytest 公共配置和 fixtures
"""

import sys
import os
import pytest
from unittest.mock import MagicMock

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


@pytest.fixture
def mock_api_client():
    """创建一个 mock 的 UnifiedAPIClient"""
    client = MagicMock()
    client.call_reasoning.return_value = ""
    client.call_generation.return_value = ""
    client.call_light.return_value = ""
    client.parse_json_response.return_value = {}
    client.get_available_models.return_value = ["test_model"]
    return client


@pytest.fixture
def tmp_output_dir(tmp_path):
    """提供一个临时输出目录"""
    output = tmp_path / "output"
    output.mkdir()
    return str(output)
