# To install: pip install tavily-python
import logging
from tavily import TavilyClient
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from config.api_config import TAVILY_API_KEY

logger = logging.getLogger(__name__)

def query_zhihu(prompt, threshold=0.2333, tolerance = 3):
    retry_count = 0
    while retry_count <= tolerance:
        retry_count+=1
        try:
            client = TavilyClient(TAVILY_API_KEY)
            response = client.search(
                query=prompt,
                search_depth="advanced",
                max_results=10,
                time_range="year",
                include_answer="advanced",
                include_domains=["zhihu.com"]
            )
            return [r["url"] for r in response["results"] if r["score"]>threshold]
        except Exception as e:
            logger.debug(f"[tavily] 第{retry_count}次搜索失败: {e}")
    raise Exception(f"Tavily API失败，已重试{tolerance}次.")
        
if __name__ == "__main__":
    pass