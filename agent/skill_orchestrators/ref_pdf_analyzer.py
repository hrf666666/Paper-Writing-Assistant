# -*- coding: utf-8 -*-
"""
Skill: 参考论文分析器 (v11.0)

v11.0: 集成 paper-fetch Markdown 优先
- 优先从 ref_md/ 目录加载 paper-fetch 获取的 Markdown 全文
- 降级到 ref_pdf/ 目录的 PDF 解析（PyMuPDF/pdfplumber/PyPDF2）
- 支持通过 paper-fetch 在线获取（DOI/标题 → Markdown 全文）
"""

import os
import json
import re
from pathlib import Path
from tqdm import tqdm

from config.project_config import REF_PDF_PATH, OUTPUT_DIR
from agent.base_orchestrator import BaseOrchestrator

import logging
logger = logging.getLogger(__name__)

# 基类实例：统一 LLM 调用、JSON 解析、文件保存
_orch = BaseOrchestrator(output_dir=OUTPUT_DIR)


def extract_text_from_pdf(pdf_path):
    """从PDF文件中提取文本内容"""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text
    except ImportError:
        logger.warning("[ref_pdf_analyzer] PyMuPDF未安装，尝试使用pdfplumber...")
        try:
            import pdfplumber
            text = ""
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            return text
        except ImportError:
            logger.warning("[ref_pdf_analyzer] pdfplumber也未安装，尝试使用PyPDF2...")
            try:
                from PyPDF2 import PdfReader
                reader = PdfReader(pdf_path)
                text = ""
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                return text
            except ImportError:
                logger.warning("[ref_pdf_analyzer] 无可用的PDF解析库，请安装PyMuPDF: pip install PyMuPDF")
                return ""


def _get_ref_md_path() -> str:
    """获取 ref_md/ 目录路径（与 ref_pdf/ 同级）"""
    ref_pdf = Path(REF_PDF_PATH)
    return str(ref_pdf.parent / "ref_md")


def load_ref_papers(ref_pdf_path, prefer_markdown=True):
    """
    加载参考论文，优先 Markdown，降级 PDF。

    v11.0 策略：
    1. 检查 ref_md/ 目录下的 .md 文件（paper-fetch 获取的）
    2. 降级到 ref_pdf/ 目录下的 .pdf 文件（PDF 解析）

    Args:
        ref_pdf_path: PDF 目录路径
        prefer_markdown: 是否优先加载 Markdown

    Returns:
        [{"filename": str, "text": str, "size": int, "source": str, ...}, ...]
    """
    papers = []

    # ── 1. 优先加载 Markdown ──
    if prefer_markdown:
        md_dir = _get_ref_md_path()
        md_path = Path(md_dir)
        if md_path.exists():
            md_files = list(md_path.glob("*.md"))
            if md_files:
                logger.info(f"[ref_pdf_analyzer] 发现 {len(md_files)} 篇 Markdown 参考论文")
                for md_file in tqdm(md_files, desc="读取 Markdown"):
                    try:
                        text = md_file.read_text(encoding="utf-8")
                        if not text.strip():
                            continue
                        paper = {
                            "filename": md_file.name,
                            "text": text,
                            "size": len(text),
                            "source": "paper_fetch_markdown",
                        }
                        # 尝试加载 .meta.json
                        meta_file = md_file.with_suffix(".meta.json")
                        if meta_file.exists():
                            try:
                                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                                paper["title"] = meta.get("title", "")
                                paper["doi"] = meta.get("doi", "")
                                paper["journal"] = meta.get("journal", "")
                            except Exception as e:
                                logger.debug(f"操作失败: {e}")
                        papers.append(paper)
                    except Exception as e:
                        logger.warning(f"[ref_pdf_analyzer] 读取 {md_file.name} 失败: {e}")

                if papers:
                    logger.info(
                        f"[ref_pdf_analyzer] 加载 {len(papers)} 篇 Markdown 论文 "
                        f"(总计 {sum(p['size'] for p in papers)} 字符)"
                    )
                    return papers

    # ── 2. 降级加载 PDF ──
    ref_path = Path(ref_pdf_path)
    if not ref_path.exists():
        logger.warning(f"[ref_pdf_analyzer] 参考PDF目录不存在: {ref_pdf_path}")
        return []

    pdf_files = list(ref_path.glob("*.pdf"))
    logger.info(f"[ref_pdf_analyzer] 发现 {len(pdf_files)} 篇参考PDF")

    for pdf_file in tqdm(pdf_files, desc="读取参考PDF"):
        text = extract_text_from_pdf(str(pdf_file))
        if text.strip():
            papers.append({
                "filename": pdf_file.name,
                "text": text,
                "size": len(text),
                "source": "pdf_extraction",
            })

    return papers


def analyze_writing_style(papers, target_chapter=None):
    """分析参考论文的写作风格"""
    
    # 合并论文内容（截断防止超长）
    combined = ""
    for p in papers[:5]:  # 最多取5篇
        combined += f"\n--- Paper: {p['filename']} ---\n{p['text'][:6000]}\n"
    
    chapter_hint = f"重点关注'{target_chapter}'部分的写作风格。" if target_chapter else ""
    
    prompt = f"""
    你是一名学术论文写作风格分析专家。请分析以下参考论文的写作风格特征，{chapter_hint}
    
    请从以下维度进行分析：
    1. **句式特征**：常用的句式结构（如"首先...然后...最终..."、问题导向句式、对比句式等），每类句式给出2-3个原文例句
    2. **段落组织**：段落开头常用的引入方式、段内论证逻辑、段落结尾常用的收束方式
    3. **用词特征**：学术表达常用词汇和短语（避免口语化表达），特别是过渡词、强调词、限定词
    4. **论证模式**：提出问题→分析原因→给出方案的模式，或先总后分的模式等
    5. **引用风格**：引用的嵌入方式（句首引用/句中引用/句末引用），引用与论述的衔接方式
    
    <reference_papers>
    {combined[:16000]}
    </reference_papers>
    
    请以json格式给出，包含"句式特征"(dict)、"段落组织"(dict)、"用词特征"(list)、"论证模式"(list)、"引用风格"(dict)。
    回复以```json开头，以```结尾，无需添加任何解释说明。
    """
    
    return _orch.parse_json_with_retry(
        prompt, call_method="call_reasoning",
        default={"句式特征": {}, "段落组织": {}, "用词特征": [], "论证模式": [], "引用风格": {}}
    )


def analyze_chapter_organization(papers, chapter_name):
    """分析参考论文中特定章节的内容组织方法"""
    
    # 从论文中提取目标章节的内容
    chapter_contents = []
    for p in papers[:8]:
        text = p["text"]
        # 尝试匹配章节标题
        patterns = [
            rf"(?i)(?:^|\n)\d*\.?\s*{re.escape(chapter_name)}.*?(?=\n\d+\.|\Z)",
            rf"(?i)(?:^|\n){re.escape(chapter_name)}.*?(?=\n[A-Z][a-z]+.*\n|\Z)",
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            if matches:
                chapter_contents.append({
                    "paper": p["filename"],
                    "content": matches[0][:4000],
                })
                break
    
    if not chapter_contents:
        # 如果没找到精确匹配，用全文的一部分
        combined = "\n".join([p["text"][:3000] for p in papers[:3]])
    else:
        combined = "\n".join([f"--- {c['paper']} ---\n{c['content']}" for c in chapter_contents])
    
    prompt = f"""
    你是一名学术论文内容组织分析专家。
    请分析以下参考论文中"{chapter_name}"章节的内容组织方法，提炼出：
    
    1. **章节结构**：该章节通常包含哪些子节，每个子节的核心任务
    2. **内容逻辑**：各子节之间的逻辑关系和过渡方式
    3. **论证手法**：如何证明某个观点（举例、对比、引用、数据支撑等）
    4. **关键句式模板**：每个子节的核心句式和表述模板（给出原文示例）
    5. **内容比例**：各子节大致的篇幅占比
    
    <chapter_contents>
    {combined[:16000]}
    </chapter_contents>
    
    请以json格式给出，包含"章节结构"(list)、"内容逻辑"(str)、"论证手法"(list)、"关键句式模板"(dict)、"内容比例"(dict)。
    回复以```json开头，以```结尾，无需添加任何解释说明。
    """
    
    return _orch.parse_json_with_retry(
        prompt, call_method="call_reasoning",
        default={"章节结构": [], "内容逻辑": "", "论证手法": [], "关键句式模板": {}, "内容比例": {}}
    )


def extract_datasets_and_baselines(papers, domain_keywords):
    """从参考论文中提取数据集和baseline信息"""
    
    combined = "\n".join([p["text"][:4000] for p in papers[:5]])
    
    prompt = f"""
    你是一名学术研究领域的文献分析专家。
    请从以下参考论文中，提取与"{domain_keywords}"相关的：
    
    1. **常用数据集**：数据集名称、规模、特点、来源论文
    2. **常用baseline方法**：方法名称、发表年份、核心思路、关键性能指标
    3. **常用评估指标**：指标名称、定义、典型值范围
    
    <reference_papers>
    {combined[:16000]}
    </reference_papers>
    
    请以json格式给出，包含"数据集"(list, 每个元素含"名称"、"描述"、"来源")、"baseline方法"(list, 每个元素含"名称"、"年份","核心思路","性能")、"评估指标"(list)。
    回复以```json开头，以```结尾，无需添加任何解释说明。
    """
    
    return _orch.parse_json_with_retry(
        prompt, call_method="call_reasoning",
        default={"数据集": [], "baseline方法": [], "评估指标": []}
    )


def extract_figure_style(papers):
    """分析参考论文中架构图的设计风格"""
    
    combined = "\n".join([p["text"][:3000] for p in papers[:5]])
    
    prompt = f"""
    你是一名学术论文图表设计专家。
    请从以下参考论文中分析架构图（Framework/Architecture Figure）的设计风格：
    
    1. **整体布局**：自左向右流式、自上而下流式、编码器-解码器对称式等
    2. **模块表示**：圆角矩形、直角矩形、圆柱体（数据）、平行四边形等
    3. **连接方式**：实线箭头、虚线箭头、双向箭头等表示的数据流/控制流
    4. **颜色使用**：是否使用颜色区分模块类型，常用配色方案
    5. **标注方式**：模块内标注维度、操作名称、损失函数位置等
    
    <reference_papers>
    {combined[:12000]}
    </reference_papers>
    
    请以json格式给出TikZ绘图指导，包含"布局方式"、"模块样式"(dict)、"连接样式"(dict)、"配色方案"(list)、"标注规范"(dict)。
    回复以```json开头，以```结尾，无需添加任何解释说明。
    """
    
    return _orch.parse_json_with_retry(
        prompt, call_method="call_light",
        default={"布局方式": "left_to_right", "模块样式": {}, "连接样式": {}, "配色方案": [], "标注规范": {}}
    )


def run_ref_pdf_analyzer(target_chapters=None, ref_dois=None):
    """
    主入口：运行参考论文分析器

    v11.0: 支持 paper-fetch 在线获取
    - 如果 ref_md/ 目录已有 Markdown，直接使用
    - 如果 ref_dois 提供了 DOI 列表，先通过 paper-fetch 获取全文
    - 最后降级到 ref_pdf/ 的 PDF 解析

    Args:
        target_chapters: 目标章节列表
        ref_dois: 额外的 DOI 列表（通过 paper-fetch 获取全文）
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if target_chapters is None:
        target_chapters = ["Introduction", "Related Work", "Methodology", "Experiments", "Conclusion"]

    # Step 0: 如果提供了 DOI 列表，通过 paper-fetch 获取 Markdown
    if ref_dois:
        _fetch_dois_to_markdown(ref_dois)

    # Step 1: 加载论文（Markdown 优先，PDF 降级）
    logger.info("[ref_pdf_analyzer] 步骤1: 加载参考论文...")
    try:
        papers = load_ref_papers(REF_PDF_PATH, prefer_markdown=True)
    except Exception as e:
        logger.error(f"[ref_pdf_analyzer] 步骤1 加载失败: {e}")
        papers = []

    if not papers:
        logger.warning("[ref_pdf_analyzer] 未找到参考论文，将使用默认写作风格")
        return _get_default_style_guide()

    md_count = sum(1 for p in papers if p.get("source") == "paper_fetch_markdown")
    pdf_count = len(papers) - md_count
    logger.info(
        f"[ref_pdf_analyzer] 成功加载 {len(papers)} 篇参考论文 "
        f"(Markdown: {md_count}, PDF: {pdf_count})"
    )
    
    logger.info("[ref_pdf_analyzer] 步骤2: 分析整体写作风格...")
    try:
        style_guide = analyze_writing_style(papers)
        _orch.save_output("writing_style_guide.json", style_guide)
    except Exception as e:
        logger.error(f"[ref_pdf_analyzer] 步骤2 分析失败: {e}")
        style_guide = {}
    
    logger.info("[ref_pdf_analyzer] 步骤3: 分析各章节内容组织...")
    chapter_organizations = {}
    for chapter in target_chapters:
        logger.info(f"  分析 '{chapter}' 章节...")
        try:
            org = analyze_chapter_organization(papers, chapter)
            chapter_organizations[chapter] = org
        except Exception as e:
            logger.error(f"[ref_pdf_analyzer] 章节 '{chapter}' 分析失败: {e}")
            chapter_organizations[chapter] = {}
    
    try:
        _orch.save_output("chapter_organizations.json", chapter_organizations)
    except Exception as e:
        logger.error(f"[ref_pdf_analyzer] 保存章节组织失败: {e}")
    
    logger.info("[ref_pdf_analyzer] 步骤4: 提取数据集和baseline信息...")
    try:
        from config.project_config import PAPER_TITLE
        domain_info = extract_datasets_and_baselines(papers, PAPER_TITLE)
        _orch.save_output("domain_info_from_refs.json", domain_info)
    except Exception as e:
        logger.error(f"[ref_pdf_analyzer] 步骤4 提取失败: {e}")
        domain_info = {"数据集": [], "baseline方法": [], "评估指标": []}
    
    logger.info("[ref_pdf_analyzer] 步骤5: 分析架构图设计风格...")
    try:
        figure_style = extract_figure_style(papers)
        _orch.save_output("figure_style_guide.json", figure_style)
    except Exception as e:
        logger.error(f"[ref_pdf_analyzer] 步骤5 分析失败: {e}")
        figure_style = {}
    
    logger.info("[ref_pdf_analyzer] 分析完成！")
    
    return {
        "style_guide": style_guide,
        "chapter_organizations": chapter_organizations,
        "domain_info": domain_info,
        "figure_style": figure_style,
        "papers": papers,
    }


def _get_default_style_guide():
    """返回默认写作风格（当无参考PDF时使用）"""
    return {
        "style_guide": {
            "句式特征": {
                "引入问题": "It is widely recognized that... / Recent studies have shown that...",
                "提出方法": "To address this issue, we propose... / In this work, we introduce...",
                "描述结果": "Experimental results demonstrate that... / As shown in Table...",
            },
            "段落组织": {
                "开头": "先给出本段核心观点或问题",
                "中间": "用证据/对比/分析支撑核心观点",
                "结尾": "总结或过渡到下一个观点",
            },
            "用词特征": ["furthermore", "moreover", "consequently", "specifically", "notably", "in contrast"],
            "论证模式": ["问题-分析-方案", "先总后分", "对比论证"],
            "引用风格": {"嵌入方式": "句中引用为主", "衔接": "作者+年份自然融入句式"},
        },
        "chapter_organizations": {},
        "domain_info": {"数据集": [], "baseline方法": [], "评估指标": []},
        "figure_style": {"布局方式": "left_to_right", "模块样式": {}, "连接样式": {}, "配色方案": [], "标注规范": {}},
        "papers": [],
    }


if __name__ == "__main__":
    results = run_ref_pdf_analyzer()
    logger.info(f"写作风格分析完成，包含 {len(results['papers'])} 篇参考论文的分析结果")


def _fetch_dois_to_markdown(dois: list, max_papers: int = 15):
    """
    通过 paper-fetch 批量获取 DOI 列表对应的 Markdown 全文。

    Args:
        dois: DOI 列表
        max_papers: 最大获取数
    """
    try:
        from tools.paper_fetch_tool import is_available, fetch_and_save
    except ImportError:
        logger.info("[ref_pdf_analyzer] paper_fetch_tool 不可用，跳过在线获取")
        return

    if not is_available():
        logger.info("[ref_pdf_analyzer] paper-fetch 不可用，跳过在线获取")
        return

    md_dir = _get_ref_md_path()
    fetched = 0
    for doi in dois[:max_papers]:
        content, md_path = fetch_and_save(doi, md_dir)
        if md_path:
            fetched += 1
            kind = "全文" if content.has_fulltext else "元数据"
            logger.info(f"[ref_pdf_analyzer] paper-fetch {kind}: {content.title[:50]}")
        if fetched >= max_papers:
            break

    logger.info(f"[ref_pdf_analyzer] paper-fetch 获取完成: {fetched}/{min(len(dois), max_papers)}")
