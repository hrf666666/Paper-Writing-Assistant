import http.client
import json
import logging

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from config.api_config import SERPER_API_KEY

logger = logging.getLogger(__name__)

def query_singleWebsite(url, includeMarkdown=True, tolerance=3):
    """通过 Serper Scraping API 获取指定URL的内容"""
    retry_count = 0
    last_error = None

    while retry_count <= tolerance:
        conn = None
        try:
            conn = http.client.HTTPSConnection("scrape.serper.dev")
            payload = json.dumps({
                "url": url,
                "includeMarkdown": includeMarkdown
            })
            headers = {
                'X-API-KEY': SERPER_API_KEY,
                'Content-Type': 'application/json'
            }
            conn.request("POST", "/", payload, headers)
            res = conn.getresponse()
            data = res.read()
            json_data = json.loads(data)
            return json_data
        except Exception as e:
            last_error = e
            logger.warning(f"[serper_normal] 第{retry_count + 1}次请求失败: {e}")
        finally:
            if conn:
                conn.close()
            retry_count += 1

    raise Exception(f"serper API失败，已重试{tolerance}次. 最后错误: {last_error}")

if __name__ == "__main__":
    pass