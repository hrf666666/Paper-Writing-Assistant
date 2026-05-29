import re
import logging

logger = logging.getLogger(__name__)


def extract_citations(content):
    """
    从文件中提取所有<citation>...</citation>标记的内容，并按原文出现顺序放入列表
    
    Args:
        content: 待处理文本
        
    Returns:
        包含所有引用内容的列表
    """
    try:
        citation_pattern = r'<citation>.*?</citation>'
        citations = re.findall(citation_pattern, content, re.DOTALL)
        return citations
    except Exception as e:
        logger.warning(f"[extract_citations] 处理文件时出错: {e}")
        return []


def generate_citation(paper_data):
    """
    Generate a citation string from paper data.
    Format: (作者1等人, 年份) or (作者1, 作者2, 年份) if fewer than 3 authors
    Returns empty string if no authors and no year.
    """
    if not paper_data:
        return ""
    
    authors = []
    if "authors" in paper_data and paper_data["authors"]:
        for author in paper_data["authors"]:
            if "name_zh" in author and author["name_zh"]:
                authors.append(author["name_zh"])
            elif "name" in author and author["name"]:
                authors.append(author["name"])
    
    year = ""
    if "year" in paper_data and paper_data["year"]:
        year = str(paper_data["year"]) + "年"
    
    if not authors and not year:
        return ""
    
    citation = ""
    if authors:
        if len(authors) >= 3:
            citation += f"{authors[0]}等人"
        else:
            citation += "，".join(authors)
    
    if authors and year:
        citation += "，"
    
    citation += year
    return citation


def generate_bibliography(json_list):
    """从JSON列表中生成标准格式的参考文献列表"""
    bibliography = []
    
    for index, item in enumerate(json_list, 1):
        paper_data = None
        if 'data' in item and item['data'] and len(item['data']) > 0:
            paper_data = item['data'][0]
        else:
            continue
        
        title = paper_data.get('title_zh', '') or paper_data.get('title', '')
        if not title:
            continue
            
        authors = []
        if 'authors' in paper_data and paper_data['authors']:
            for author in paper_data['authors']:
                author_name = author.get('name_zh', '') or author.get('name', '')
                if author_name:
                    authors.append(author_name)
        
        author_str = ""
        if len(authors) > 3:
            author_str = ", ".join(authors[:3]) + "等人"
        else:
            author_str = ", ".join(authors)
            
        year = paper_data.get('year', '')
        volume = paper_data.get('volume', '')
        issue = paper_data.get('issue', '')
        
        venue = ""
        if 'venue' in paper_data and paper_data['venue']:
            venue = paper_data['venue'].get('raw', '')
        
        pages = ""
        entry = f"{author_str}. {title}"
        pub_type = "[J]"
        
        if venue:
            entry += f"{pub_type} {venue}"
            if year:
                entry += f", {year}"
            if volume:
                entry += f", {volume}"
                if issue:
                    entry += f"({issue})"
            if pages:
                entry += f": {pages}"
            else:
                entry += "."
        elif year:
            entry += f". {year}."
        else:
            entry += "."
            
        bibliography.append((index, entry))
    
    return bibliography


def deduplicate_references(reference_list):
    """
    对参考文献列表进行去重，保持序号连续且升序
    
    参数:
        reference_list: 包含(序号, 文献内容)元组的列表
    
    返回:
        deduplicated_list: 去重后的参考文献列表
        mapping: 原序号到新序号的映射字典
    """
    contents = [ref[1] for ref in reference_list]
    
    unique_contents = []
    seen_contents = set()
    
    for content in contents:
        if content not in seen_contents:
            unique_contents.append(content)
            seen_contents.add(content)
    
    mapping = {}
    for old_index, content in reference_list:
        new_index = unique_contents.index(content) + 1
        mapping[old_index] = new_index
    
    deduplicated_list = [(i+1, content) for i, content in enumerate(unique_contents)]
    
    return deduplicated_list, mapping
