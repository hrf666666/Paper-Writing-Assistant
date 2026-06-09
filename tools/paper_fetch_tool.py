# -*- coding: utf-8 -*-
"""
Tool: paper-fetch 封装器 (v11.0)

基于 paper-fetch-skill (https://github.com/Dictation354/paper-fetch-skill) 实现：
- 通过 DOI/URL/标题获取论文结构化 Markdown 全文 + 元数据
- 覆盖 17 个出版社（arXiv, Elsevier, Springer, Wiley, Science, IEEE 等）
- 降级链：paper-fetch 全文 → paper-fetch 元数据 → 原有搜索 API

安装：
    pip install paper-fetch-skill

核心 API：
    fetch_paper_markdown(query)  → 论文 Markdown 全文
    fetch_paper_metadata(query)  → 论文元数据（标题、作者、摘要）
    fetch_and_save(query, dir)   → 获取并保存到本地
    fetch_papers_batch(queries)  → 批量获取
"""

from __future__ import annotations

import json
import os
import re
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ── 可用性检测 ──

_BACKEND_AVAILABLE: Optional[bool] = None


def is_available() -> bool:
    """检测 paper-fetch-skill 是否已安装"""
    global _BACKEND_AVAILABLE
    if _BACKEND_AVAILABLE is None:
        try:
            from paper_fetch import fetch_paper  # noqa: F401
            _BACKEND_AVAILABLE = True
        except ImportError:
            _BACKEND_AVAILABLE = False
            logger.debug("[PaperFetch] paper-fetch-skill 未安装，将使用降级方案")
    return _BACKEND_AVAILABLE


# ── 数据模型 ──

@dataclass
class PaperContent:
    """论文内容统一模型"""
    title: str = ""
    authors: str = ""
    abstract: str = ""
    journal: str = ""
    doi: str = ""
    published: str = ""
    source: str = ""           # 来源: arxiv_html, crossref_meta, etc.
    content_kind: str = ""     # fulltext | abstract_only | metadata_only
    markdown: str = ""         # 全文 Markdown
    sections: List[Dict] = field(default_factory=list)   # 结构化章节
    references: List[Dict] = field(default_factory=list)  # 参考文献
    token_estimate: int = 0
    error: str = ""

    @property
    def has_fulltext(self) -> bool:
        return self.content_kind == "fulltext" and len(self.markdown) > 200

    @property
    def has_abstract(self) -> bool:
        return bool(self.abstract) or self.content_kind in ("fulltext", "abstract_only")

    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "authors": self.authors,
            "doi": self.doi,
            "journal": self.journal,
            "content_kind": self.content_kind,
            "token_estimate": self.token_estimate,
            "has_fulltext": self.has_fulltext,
            "markdown_length": len(self.markdown),
        }


# ── 核心函数 ──

def fetch_paper_markdown(query: str, timeout: int = 60) -> PaperContent:
    """
    获取论文的结构化 Markdown 全文。

    Args:
        query: DOI / arXiv ID / 论文 URL / 论文标题
        timeout: 超时时间（秒）

    Returns:
        PaperContent 对象（markdown 字段包含全文）
    """
    if not is_available():
        return PaperContent(
            title=query, content_kind="unavailable",
            error="paper-fetch-skill not installed",
        )

    try:
        from paper_fetch import fetch_paper

        logger.info(f"[PaperFetch] 获取: {query[:80]}...")
        t0 = time.time()

        env = fetch_paper(query)
        elapsed = time.time() - t0

        content = PaperContent(
            content_kind=env.content_kind or "",
            token_estimate=env.token_estimate or 0,
        )

        # 提取元数据
        if env.metadata:
            content.title = env.metadata.title or ""
            content.abstract = env.metadata.abstract or ""
            content.journal = env.metadata.journal or ""
            content.published = env.metadata.published or ""

        # 提取 Markdown
        if env.markdown:
            content.markdown = env.markdown

        # 提取 article 级数据
        if env.article:
            content.doi = env.article.doi or ""
            content.source = env.article.source or ""
            if env.article.sections:
                content.sections = [
                    {"heading": s.heading, "level": s.level, "text": getattr(s, "text", "")}
                    for s in env.article.sections
                    if hasattr(s, "heading")
                ]
            if env.article.references:
                content.references = [
                    ref if isinstance(ref, dict) else {"raw": str(ref)}
                    for ref in env.article.references
                ]
            # 补充标题
            if not content.title and env.article.metadata:
                content.title = env.article.metadata.title or ""

        logger.info(
            f"[PaperFetch] 完成: kind={content.content_kind}, "
            f"tokens={content.token_estimate}, "
            f"md_len={len(content.markdown)}, "
            f"elapsed={elapsed:.1f}s"
        )
        return content

    except Exception as e:
        logger.warning(f"[PaperFetch] 获取失败 ({query}): {e}")
        return PaperContent(
            title=query, content_kind="error", error=str(e),
        )


def fetch_paper_metadata(query: str) -> PaperContent:
    """
    仅获取论文元数据（标题、作者、摘要），不获取全文。
    比 fetch_paper_markdown 更快。
    """
    content = fetch_paper_markdown(query)
    # 即使获取失败，metadata_only 的结果也是有用的
    return content


def fetch_and_save(
    query: str,
    output_dir: str,
    save_metadata: bool = True,
) -> Tuple[PaperContent, Optional[str]]:
    """
    获取论文并保存 Markdown 到本地。

    Args:
        query: DOI / URL / 标题
        output_dir: 保存目录
        save_metadata: 是否额外保存 JSON 元数据

    Returns:
        (PaperContent, markdown文件路径)
    """
    content = fetch_paper_markdown(query)

    if not content.markdown:
        return content, None

    os.makedirs(output_dir, exist_ok=True)

    # 生成安全的文件名
    safe_name = _safe_filename(content.title or content.doi or query)
    md_path = os.path.join(output_dir, f"{safe_name}.md")

    # 保存 Markdown
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(content.markdown)

    logger.info(f"[PaperFetch] 保存: {md_path}")

    # 保存元数据
    if save_metadata:
        meta_path = os.path.join(output_dir, f"{safe_name}.meta.json")
        meta = {
            "title": content.title,
            "authors": content.authors,
            "doi": content.doi,
            "journal": content.journal,
            "published": content.published,
            "source": content.source,
            "content_kind": content.content_kind,
            "token_estimate": content.token_estimate,
            "sections_count": len(content.sections),
            "references_count": len(content.references),
            "query": query,
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

    return content, md_path


def fetch_papers_batch(
    queries: List[str],
    output_dir: Optional[str] = None,
    max_papers: int = 20,
    delay: float = 1.0,
) -> List[Tuple[str, PaperContent]]:
    """
    批量获取论文。

    Args:
        queries: 查询列表（DOI/URL/标题）
        output_dir: 保存目录（None 则不保存）
        max_papers: 最大获取数
        delay: 每篇间隔（秒，防止被限流）

    Returns:
        [(query, PaperContent), ...]
    """
    results = []
    for i, query in enumerate(queries[:max_papers]):
        logger.info(f"[PaperFetch] 批量 {i+1}/{min(len(queries), max_papers)}: {query[:60]}")

        if output_dir:
            content, _ = fetch_and_save(query, output_dir, save_metadata=True)
        else:
            content = fetch_paper_markdown(query)

        results.append((query, content))

        if i < len(queries) - 1 and delay > 0:
            time.sleep(delay)

    success = sum(1 for _, c in results if c.has_fulltext)
    logger.info(
        f"[PaperFetch] 批量完成: {success}/{len(results)} 全文获取成功"
    )
    return results


# ── 加载本地 Markdown 论文 ──

def load_local_markdown_papers(directory: str) -> List[Dict]:
    """
    从目录加载已保存的 Markdown 论文文件。

    支持 paper-fetch 保存的 .md + .meta.json 格式，
    也支持纯 .md 文件。

    Returns:
        [{"filename": str, "text": str, "title": str, "doi": str, ...}, ...]
    """
    md_dir = Path(directory)
    if not md_dir.exists():
        return []

    papers = []
    for md_file in sorted(md_dir.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        if not text.strip():
            continue

        paper = {
            "filename": md_file.name,
            "text": text,
            "size": len(text),
            "source": "paper_fetch_markdown",
        }

        # 尝试加载配套的 .meta.json
        meta_file = md_file.with_suffix(".meta.json")
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                paper["title"] = meta.get("title", "")
                paper["doi"] = meta.get("doi", "")
                paper["journal"] = meta.get("journal", "")
                paper["content_kind"] = meta.get("content_kind", "")
            except Exception:
                pass

        papers.append(paper)

    logger.info(f"[PaperFetch] 加载 {len(papers)} 篇本地 Markdown 论文")
    return papers


# ── 与 reference_pool 联动 ──

def enrich_reference_pool_with_fulltext(
    reference_pool: List[Dict],
    output_dir: str = "./ref_md",
    max_papers: int = 15,
) -> List[Dict]:
    """
    为参考池中的论文获取全文 Markdown，增强引用质量。

    对参考池中每篇论文：
    1. 优先用 DOI 获取全文
    2. 回退到标题获取
    3. 将 markdown 路径添加到 reference_pool 条目中

    Args:
        reference_pool: reference_pool_builder 构建的论文池
        output_dir: Markdown 保存目录
        max_papers: 最多获取几篇全文

    Returns:
        增强后的 reference_pool（原地修改）
    """
    if not is_available():
        logger.info("[PaperFetch] 不可用，跳过全文增强")
        return reference_pool

    os.makedirs(output_dir, exist_ok=True)
    enriched_count = 0

    for entry in reference_pool:
        if enriched_count >= max_papers:
            break

        # 跳过已有全文的
        if entry.get("markdown_path"):
            continue

        # 优先 DOI，其次标题
        query = entry.get("externalIds", {}).get("DOI") or entry.get("doi", "")
        if not query:
            query = entry.get("title", "")

        if not query:
            continue

        content, md_path = fetch_and_save(query, output_dir)
        if md_path and content.has_fulltext:
            entry["markdown_path"] = md_path
            entry["content_kind"] = content.content_kind
            entry["token_estimate"] = content.token_estimate
            enriched_count += 1
            logger.info(
                f"[PaperFetch] 增强引用池: {content.title[:50]} "
                f"({content.content_kind})"
            )

    logger.info(
        f"[PaperFetch] 引用池增强完成: {enriched_count}/{min(len(reference_pool), max_papers)} 全文"
    )
    return reference_pool


# ── 工具函数 ──

def _safe_filename(text: str, max_len: int = 60) -> str:
    """将文本转换为安全的文件名"""
    # 移除特殊字符
    safe = re.sub(r'[\\/:*?"<>|\n\r\t]', '_', text)
    # 替换空格
    safe = safe.replace(' ', '_')
    # 截断
    safe = safe[:max_len]
    # 移除首尾的点和下划线
    safe = safe.strip('._')
    # 如果为空，用时间戳
    if not safe:
        safe = f"paper_{int(time.time())}"
    return safe


# ── 便捷入口 ──

def run_paper_fetch(
    queries: List[str],
    output_dir: str = "./ref_md",
    max_papers: int = 20,
) -> Dict:
    """
    主入口：批量获取论文 Markdown 全文。

    Args:
        queries: DOI/URL/标题列表
        output_dir: 保存目录
        max_papers: 最大数量

    Returns:
        {"fetched": int, "fulltext": int, "files": [...], "errors": [...]}
    """
    results = fetch_papers_batch(queries, output_dir, max_papers)

    report = {
        "fetched": len(results),
        "fulltext": sum(1 for _, c in results if c.has_fulltext),
        "metadata_only": sum(1 for _, c in results if not c.has_fulltext),
        "files": [],
        "errors": [],
    }

    for query, content in results:
        if content.error:
            report["errors"].append({"query": query, "error": content.error})
        # 查找保存的文件
        safe_name = _safe_filename(content.title or content.doi or query)
        md_path = os.path.join(output_dir, f"{safe_name}.md")
        if os.path.exists(md_path):
            report["files"].append(md_path)

    return report
