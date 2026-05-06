import sys
import logging
from pathlib import Path

# 设置项目路径
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from config.api_config import OPENAI_API_KEY

from openai import OpenAI

logger = logging.getLogger(__name__)


def query_openai_o1(prompt, tolerance=1):
    """
    调用 OpenAI o1 模型（旧式接口，推荐使用 agent.api_client.UnifiedAPIClient）

    参数:
        prompt (str): 提示文本
        tolerance (int): 最大重试次数
    返回:
        str: 模型回复文本
    """
    if not OPENAI_API_KEY:
        raise ValueError("OpenAI API Key 未配置，请设置环境变量 OPENAI_API_KEY")

    last_error = None
    for attempt in range(tolerance + 1):
        try:
            client = OpenAI(api_key=OPENAI_API_KEY)
            completion = client.chat.completions.create(
                model="o1",
                store=True,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return completion.choices[0].message.content
        except Exception as e:
            last_error = e
            if attempt < tolerance:
                logger.warning(f"[api.openai_o1] 第{attempt + 1}次调用失败: {e}")
            else:
                raise Exception(f"OpenAI o1 调用失败，已重试{tolerance}次: {last_error}")