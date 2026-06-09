# -*- coding: utf-8 -*-
"""
Skill: 第五章 - Conclusion / 总结
仿照参考文章PDF的总结写法
"""

import os
import json
import glob

from config.project_config import (
    PAPER_TITLE, OUTPUT_DIR, get_article_type_info
)
from agent.base_orchestrator import BaseOrchestrator

import logging
logger = logging.getLogger(__name__)

# 基类实例：统一 LLM 调用
_orch = BaseOrchestrator(output_dir=OUTPUT_DIR)


def _load_previous_summary():
    """从输出目录读取前序章节摘要"""
    summary = ""
    for chapter_num in range(1, 5):
        pattern = f"{OUTPUT_DIR}/chapter{chapter_num}/chapter{chapter_num}_*.md"
        files = glob.glob(pattern)
        for f in files:
            try:
                with open(f, 'r', encoding='utf-8') as fh:
                    content = fh.read()
                summary += content[:500] + "\n...\n"
            except Exception as e:
                logger.debug(f"操作失败: {e}")
    return summary


def generate_conclusion(project_data, ref_data, previous_chapters_summary,
                        skip_limitations=False, citation_context=""):
    """生成第五章 Conclusion"""
    
    innovation_points = project_data.get("innovation_points", [])
    experiment_design = project_data.get("experiment_design", {})
    
    style_guide = ref_data.get("style_guide", {})
    chapter_org = ref_data.get("chapter_organizations", {}).get("Conclusion", {})
    article_info = get_article_type_info()
    
    innovation_summary = "\n".join([
        f"贡献{i+1}: {ip.get('创新点名称', 'N/A')} - {ip.get('创新点价值', 'N/A')}"
        for i, ip in enumerate(innovation_points)
    ])
    
    key_results = experiment_design.get("关键结果", {})
    
    # 构建参考论文中结论的写法指导
    ref_conclusion_instruction = ""
    if chapter_org and isinstance(chapter_org, dict):
        structure = chapter_org.get("章节结构", [])
        patterns = chapter_org.get("关键句式模板", {})
        if structure:
            ref_conclusion_instruction += f"参考组织结构：{structure}\n"
        if patterns:
            ref_conclusion_instruction += "参考句式模板：\n"
            for k, v in patterns.items():
                ref_conclusion_instruction += f"  {k}: {v}\n"
    
    # v9.3: 加载 IEEE Trans 期刊风格配置
    ieee_trans_instruction = ""
    try:
        # v10.1: 优先使用 StyleManager
        try:
            from agent.venue_adapter import VenueAdapter
            adapter = VenueAdapter()
            style_text = adapter.build_chapter_style_instruction("Conclusion")
            if style_text and len(style_text) > 100:
                ieee_trans_instruction = f"\n{style_text}\n"
            else:
                raise ValueError("StyleManager returned insufficient content")
        except Exception as e:
            logger.debug(f"风格规则加载失败: {e}")
            # 降级：原有 IEEE Trans 规则加载
            from config.ieee_trans_style_profile import get_section_requirements
            concl_req = get_section_requirements("Conclusion")
            ieee_trans_instruction = f"\n**IEEE Transactions 期刊特定规则**（必须遵守）：\n"
            ieee_trans_instruction += f"- 长度：{concl_req.get('length', 'N/A')}\n"
            ieee_trans_instruction += f"- 必须包含：{', '.join(concl_req.get('must_include', []))}\n"
            ieee_trans_instruction += f"- 禁止模式：{', '.join(concl_req.get('anti_patterns', []))}\n"
    except Exception as e:
        logger.debug(f"[IEEE Trans 风格配置] 加载失败: {e}")
    
    prompt = f"""
你是一名{article_info['name']}级别的学术论文写作专家。请为论文"{PAPER_TITLE}"撰写第5章"Conclusion"。

**核心任务**：总结全文，凝练贡献，展望未来。

**项目贡献**：
{innovation_summary}

**关键实验结果**：
{json.dumps(key_results, ensure_ascii=False, indent=2)[:2000]}

**前序章节摘要**：
{previous_chapters_summary[:2000]}

{ref_conclusion_instruction}

{ieee_trans_instruction}

**具体要求**：
1. **总结段落**（1段）：回顾本文的核心问题和提出的方法，简述关键思路
2. **贡献列表**（3条）：对应3个创新点，每条说明做了什么、解决了什么、效果如何
3. **局限性与未来工作**：{"**绝对禁止写此段** — 局限性、未来工作和讨论已在独立的 Discussion/Limitations 章节中详细展开。结论中只能写一段简短的展望性总结（2-3句），绝对不要重复讨论局限性、future work、不足之处。" if skip_limitations else "诚实地指出当前方法的局限性，并给出2-3个有价值的未来方向"}

**写作风格**：
- 结论应简洁有力，不引入新的信息
- 贡献的描述要比Introduction更具体（因为读者已经读完全文）
- 局限性要诚实但不过分贬低，未来工作要自然承接局限性
- 仿照参考论文的结论写法

请使用学术英语撰写。请直接输出LaTeX代码。不要输出 \section 标题。只输出LaTeX正文代码：
"""
    
    logger.info("[chapter5] 生成第五章 Conclusion...")
    section_5 = _orch.call_generation(prompt)
    
    full_chapter = f"\\section{{Conclusion}}\n\n{section_5}\n"
    
    return full_chapter


def run_chapter5(project_data, ref_data, previous_chapters=None, skip_limitations=False,
                  citation_context=""):
    """主入口：生成第五章"""
    os.makedirs(f"{OUTPUT_DIR}/chapter5", exist_ok=True)
    
    # 优先使用传入的前序章节摘要
    if previous_chapters:
        previous_chapters_summary = ""
        for ch_num in sorted(previous_chapters.keys(), key=lambda x: str(x)):
            previous_chapters_summary += f"Chapter {ch_num}:\n{previous_chapters[ch_num][:1500]}\n...\n"
    else:
        # 从输出目录读取前序章节摘要
        try:
            previous_chapters_summary = _load_previous_summary()
        except Exception as e:
            logger.error(f"[chapter5] 读取前序章节摘要失败: {e}")
            previous_chapters_summary = ""
    
    logger.info("[chapter5] 开始生成第五章 Conclusion...")
    try:
        chapter_content = generate_conclusion(project_data, ref_data, previous_chapters_summary,
                                               skip_limitations=skip_limitations,
                                               citation_context=citation_context)
    except Exception as e:
        logger.error(f"[chapter5] 第五章生成失败: {e}")
        chapter_content = "\\section{Conclusion}\n\n(生成失败，请重新运行)\n"
    
    try:
        _orch.save_output("chapter5_conclusion.md", chapter_content, subdir="chapter5")
    except Exception as e:
        logger.error(f"[chapter5] 保存失败: {e}")
    
    logger.info("[chapter5] 第五章生成完成！")
    return chapter_content


if __name__ == "__main__":
    project_data = {}
    ref_data = {}
    for fname in ["innovation_points.json", "experiment_design.json"]:
        fpath = f"{OUTPUT_DIR}/{fname}"
        if os.path.exists(fpath):
            with open(fpath, 'r', encoding='utf-8') as f:
                project_data[fname.replace(".json", "")] = json.load(f)
    result = run_chapter5(project_data, ref_data)
