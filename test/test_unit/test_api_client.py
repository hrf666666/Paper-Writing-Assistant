# -*- coding: utf-8 -*-
"""
测试 api/openai_compatible.py - OpenAI/Anthropic 统一客户端
"""

import pytest
from unittest.mock import patch, MagicMock

from api.openai_compatible import (
    OpenAIClient,
    AnthropicClient,
    create_client,
)


class TestOpenAIClient:
    """测试 OpenAIClient — OpenAI 在 __init__ 内延迟导入，需 patch openai.OpenAI"""

    @patch("openai.OpenAI")
    def test_init(self, mock_openai_cls):
        client = OpenAIClient(
            api_key="test-key",
            base_url="https://api.example.com/v1",
            model="gpt-test",
        )
        assert client.model == "gpt-test"
        assert client.max_tokens == 8192
        assert client.temperature == 0.7
        assert client.stream is False
        mock_openai_cls.assert_called_once_with(
            api_key="test-key",
            base_url="https://api.example.com/v1",
            timeout=300,
        )

    @patch("openai.OpenAI")
    def test_init_custom_params(self, mock_openai_cls):
        client = OpenAIClient(
            api_key="k",
            base_url="url",
            model="m",
            max_tokens=4096,
            temperature=0.3,
            stream=True,
            timeout=120,
        )
        assert client.max_tokens == 4096
        assert client.temperature == 0.3
        assert client.stream is True
        assert client.timeout == 120

    @patch("openai.OpenAI")
    def test_is_reasoning_model(self, mock_openai_cls):
        client = OpenAIClient(api_key="k", base_url="u", model="qwq-32b")
        assert client._is_reasoning_model() is True

    @patch("openai.OpenAI")
    def test_is_reasoning_model_o1(self, mock_openai_cls):
        client = OpenAIClient(api_key="k", base_url="u", model="o1-preview")
        assert client._is_reasoning_model() is True

    @patch("openai.OpenAI")
    def test_is_reasoning_model_o3(self, mock_openai_cls):
        client = OpenAIClient(api_key="k", base_url="u", model="o3-mini")
        assert client._is_reasoning_model() is True

    @patch("openai.OpenAI")
    def test_is_reasoning_model_deepseek_r(self, mock_openai_cls):
        client = OpenAIClient(api_key="k", base_url="u", model="deepseek-r-v3")
        assert client._is_reasoning_model() is True

    @patch("openai.OpenAI")
    def test_is_not_reasoning_model(self, mock_openai_cls):
        client = OpenAIClient(api_key="k", base_url="u", model="glm-5.1")
        assert client._is_reasoning_model() is False

    @patch("openai.OpenAI")
    def test_is_not_reasoning_model_qwen(self, mock_openai_cls):
        client = OpenAIClient(api_key="k", base_url="u", model="qwen-plus")
        assert client._is_reasoning_model() is False

    @patch("openai.OpenAI")
    def test_query_sync(self, mock_openai_cls):
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = "Hello response"
        mock_openai_cls.return_value.chat.completions.create.return_value = mock_completion

        client = OpenAIClient(api_key="k", base_url="u", model="qwen-plus")
        result = client.query("Hello")
        assert result == "Hello response"

    @patch("openai.OpenAI")
    def test_query_sync_with_system_prompt(self, mock_openai_cls):
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = "System response"
        mock_openai_cls.return_value.chat.completions.create.return_value = mock_completion

        client = OpenAIClient(api_key="k", base_url="u", model="qwen-plus")
        result = client.query("Hello", system_prompt="You are helpful")
        assert result == "System response"

        call_args = mock_openai_cls.return_value.chat.completions.create.call_args
        messages = call_args[1]["messages"]
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are helpful"
        assert messages[1]["role"] == "user"

    @patch("openai.OpenAI")
    def test_query_empty_choices_returns_empty(self, mock_openai_cls):
        mock_completion = MagicMock()
        mock_completion.choices = []
        mock_openai_cls.return_value.chat.completions.create.return_value = mock_completion

        client = OpenAIClient(api_key="k", base_url="u", model="qwen-plus")
        result = client.query("Hello")
        assert result == ""

    @patch("openai.OpenAI")
    def test_repr(self, mock_openai_cls):
        client = OpenAIClient(api_key="k", base_url="u", model="test-model")
        assert repr(client) == "OpenAIClient(model=test-model)"


class TestAnthropicClient:
    """测试 AnthropicClient — anthropic 在 __init__ 内延迟导入"""

    @patch("anthropic.Anthropic")
    def test_init(self, mock_anthropic_cls):
        client = AnthropicClient(api_key="test-key", model="claude-test")
        assert client.model == "claude-test"
        assert client.max_tokens == 8192
        assert client.temperature == 1.0
        mock_anthropic_cls.assert_called_once_with(
            api_key="test-key", timeout=300
        )

    @patch("anthropic.Anthropic")
    def test_query(self, mock_anthropic_cls):
        mock_response = MagicMock()
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Claude response"
        mock_response.content = [text_block]
        mock_anthropic_cls.return_value.messages.create.return_value = mock_response

        client = AnthropicClient(api_key="k", model="claude-test")
        result = client.query("Hello")
        assert result == "Claude response"

    @patch("anthropic.Anthropic")
    def test_query_with_system_prompt(self, mock_anthropic_cls):
        mock_response = MagicMock()
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Response with system"
        mock_response.content = [text_block]
        mock_anthropic_cls.return_value.messages.create.return_value = mock_response

        client = AnthropicClient(api_key="k", model="claude-test")
        result = client.query("Hello", system_prompt="Be helpful")
        assert result == "Response with system"

        call_kwargs = mock_anthropic_cls.return_value.messages.create.call_args[1]
        assert call_kwargs["system"] == "Be helpful"

    @patch("anthropic.Anthropic")
    def test_repr(self, mock_anthropic_cls):
        client = AnthropicClient(api_key="k", model="claude-test")
        assert repr(client) == "AnthropicClient(model=claude-test)"


class TestCreateClient:
    """测试 create_client 工厂函数"""

    @patch("openai.OpenAI")
    def test_create_openai_client(self, mock_openai_cls):
        config = {
            "api_key": "test-key",
            "base_url": "https://api.example.com/v1",
            "model_id": "gpt-test",
            "max_tokens": 4096,
            "temperature": 0.5,
            "stream": True,
        }
        client = create_client(config)
        assert isinstance(client, OpenAIClient)
        assert client.model == "gpt-test"
        assert client.max_tokens == 4096
        assert client.temperature == 0.5
        assert client.stream is True

    @patch("anthropic.Anthropic")
    def test_create_anthropic_client(self, mock_anthropic_cls):
        config = {
            "api_key": "test-key",
            "model_id": "claude-test",
            "non_openai": True,
            "max_tokens": 4096,
            "temperature": 0.8,
        }
        client = create_client(config)
        assert isinstance(client, AnthropicClient)
        assert client.model == "claude-test"

    @patch("openai.OpenAI")
    def test_create_client_default_values(self, mock_openai_cls):
        config = {
            "api_key": "key",
            "base_url": "url",
            "model_id": "model",
        }
        client = create_client(config)
        assert isinstance(client, OpenAIClient)
        assert client.max_tokens == 8192
        assert client.temperature == 0.7
        assert client.stream is False
