import sys
import logging
import requests
from pathlib import Path
import time

# 设置项目路径
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from config.api_config import CLAUDE_API_KEY

logger = logging.getLogger(__name__)


def query_claude(prompt, tolerance=1):
    """
    调用Claude API获取响应（旧式接口，推荐使用 agent.api_client.UnifiedAPIClient）

    参数:
        prompt (str): 发送给Claude的提示文本
        tolerance (int): 最大重试次数
    返回:
        str: Claude的回复文本
    """
    if not CLAUDE_API_KEY:
        raise ValueError("Claude API Key 未配置，请设置环境变量 CLAUDE_API_KEY")

    headers = {
        "x-api-key": CLAUDE_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }

    data = {
        "model": "claude-3-7-sonnet-20250219",
        "max_tokens": 23333,
        "temperature": 1,
        "messages": [{"role": "user", "content": prompt}]
    }

    retry_count = 0
    last_error = None

    while retry_count <= tolerance:
        try:
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=data,
                timeout=300
            )

            response.raise_for_status()
            result = response.json()
            return result['content'][0]['text']

        except (requests.exceptions.RequestException, KeyError, IndexError) as e:
            last_error = e
            retry_count += 1
            if retry_count <= tolerance:
                logger.warning(f"[api.claude_37] 请求失败: {e}，第{retry_count}次重试...")
                time.sleep(30)
            else:
                raise Exception(f"请求Claude API失败，已重试{tolerance}次: {last_error}")