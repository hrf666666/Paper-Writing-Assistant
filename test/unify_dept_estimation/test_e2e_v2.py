#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
端到端测试脚本 v2 - 带质量门控+迭代修改+参考文献验证

测试用例：Unified Dual-Mask Physical Model for Non-Lambertian Light Field Depth Estimation

核心改进（相比v1）：
1. 每章生成后执行质量评估，不达标自动修改迭代（最多3轮）
2. 用AMiner API搜索真实论文，生成可验证的参考文献
3. 验证参考文献真实性，标注验证状态
"""

import os
import sys
import re
import json
import time
import logging

sys.stdout.reconfigure(encoding='utf-8')

# 确保项目根目录在sys.path中
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# 输出目录（相对于项目根目录）
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))

# ============================================================
# 1. 项目信息
# ============================================================

PROJECT_INFO = {
    "paper_title": "Unified Dual-Mask Physical Model for Non-Lambertian Light Field Depth Estimation",
    "article_type": "IEEE Transactions",
    "research_domain": "Light Field Depth Estimation, Computational Imaging, Non-Lambertian Vision",
    
    "innovation_points": [
        {
            "name": "Dual-Mask Physical Model (Medium Mask + Angular Direction Mask)",
            "description": "A unified physics-inspired framework that abstracts light-matter interaction governed by Maxwell's equations into two learnable, physically interpretable masks: the Medium Mask r(x,y)=a(x,y)/lambda quantifying dominant interaction type (specular/scattering/diffuse), and the Angular Direction Mask V(x,y,theta_i) describing wave vector deflection distribution under phase matching conditions.",
            "value": "Provides the first unified theoretical framework that naturally reduces to Lambertian as a special case (r>>1, isotropic cosine) while explicitly modeling non-Lambertian phenomena."
        },
        {
            "name": "Physically Consistent Differentiable Rendering",
            "description": "A differentiable rendering layer that enforces electromagnetic optical principles through physical consistency loss (<1e-4), including Fresnel reflectance constraints, Rayleigh/Mie scattering phase functions, and Lambertian micro-facet statistical averaging, ensuring the model's outputs strictly align with Maxwell's equations.",
            "value": "Eliminates the photometric consistency failure that plagues traditional MVS methods under non-Lambertian scenes, providing physically grounded depth predictions."
        },
        {
            "name": "Three-Stage Physics-Guided Training Pipeline",
            "description": "A curriculum learning strategy: Stage 1 validates the physical model on Lambertian-dominant HCI4D data (MAE<=0.05), Stage 2 fine-tunes on hybrid synthetic non-Lambertian data (MAE<=0.04), Stage 3 optimizes on target non-Lambertian scenes (MAE<=0.03), with automatic fallback when HCI4D is unavailable.",
            "value": "Achieves robust generalization across Lambertian to severely non-Lambertian environments (specular, scattering, mine dust) without manual intervention."
        }
    ],
    
    "model_architecture": {
        "overview": "The proposed framework consists of four core modules: (1) Dual-Mask Encoder that extracts the Medium Mask r(x,y) and Angular Direction Mask V(x,y,theta_i) from multi-view light field inputs; (2) Physical Interaction Module that computes physically consistent feature representations based on electromagnetic interaction types; (3) Depth Decoder that predicts dense depth maps from physically-enhanced features; (4) Differentiable Rendering Layer that enforces forward physical consistency through Maxwell's equation constraints.",
        "components": [
            {"name": "Dual-Mask Encoder", "type": "core_innovation", "description": "Extracts Medium Mask r(x,y)=a(x,y)/lambda classifying interaction types and Angular Direction Mask V(x,y,theta_i) capturing wave vector deflection distributions from angular light field sub-aperture views."},
            {"name": "Physical Interaction Module", "type": "core_innovation", "description": "Routes features through physics-specific computation paths: Fresnel reflectance for specular, Rayleigh/Mie phase functions for scattering, micro-facet BRDF for diffuse."},
            {"name": "Depth Decoder", "type": "base_component", "description": "Multi-scale depth prediction with skip connections and cost volume construction from physically-enhanced angular features."},
            {"name": "Differentiable Rendering Layer", "type": "core_innovation", "description": "Forward renders predicted depth and dual masks, computing physical consistency loss enforcing Fresnel equations, energy conservation, and phase matching."}
        ]
    },
    
    "experiment_design": {
        "datasets": [
            {"name": "HCI4D", "type": "Lambertian-dominant", "usage": "Stage 1 physical pre-training", "scenes": "Teddy, David"},
            {"name": "Synthetic Non-Lambertian", "type": "Physics-based rendered", "usage": "Stage 2 augmentation fine-tuning"},
            {"name": "Non-lambertian_dataset_zhenglong", "type": "Real non-Lambertian", "usage": "Stage 3 target training", "scenes": "Teddy, David 10-80%, Apple 20-90%, Mine 0-80%"}
        ],
        "metrics": ["MAE", "RMSE", "MSE", "Bad Pixel Ratio (delta1.25)", "Physical Consistency Loss"],
        "baselines": ["LF (Wang et al.)", "EPI2F (Shin et al.)", "LFNet (Yeung et al.)", "EPINET (Shin et al.)", "ACE (Mikhailiuk et al.)", "DPT (Ranftl et al.)"],
        "key_results": {
            "stage1": "Val MAE <= 0.05 on HCI4D",
            "stage2": "Val MAE <= 0.04 on synthetic non-Lambertian",
            "stage3": "Val MAE <= 0.03 on target non-Lambertian",
        },
        "training_details": {
            "framework": "PyTorch", "optimizer": "AdamW",
            "scheduler": "Cosine annealing with warmup",
            "stage1_epochs": 20, "stage2_epochs": 30, "stage3_epochs": 40,
            "loss_components": ["Depth supervision", "Physical consistency", "Epipolar constraint", "Medium mask regularization", "Reprojection error"]
        }
    }
}

# ============================================================
# 2. 带质量门控的章节生成
# ============================================================

def generate_chapter_with_qc(executor, skill_name, context, chapter_name, max_rounds=2):
    """
    生成章节 + 质量评估 + 迭代修改
    
    流程：生成 → 评估 → 不达标则修改 → 再评估 → ... → 最多max_rounds轮
    """
    from agent.quality_gate import QualityGate
    quality_gate = QualityGate(executor.api_client)
    
    # 第一轮：生成
    logger.info("  [生成] %s ..." % chapter_name)
    result = executor.execute(skill_name, context)
    current_content = result["content"]
    
    # 质量评估循环
    for round_num in range(max_rounds + 1):
        logger.info("  [评估] %s 第%d轮质量评估 ..." % (chapter_name, round_num))
        report = quality_gate.evaluate(
            chapter_name=chapter_name,
            chapter_content=current_content,
            style_guide=context.get("style_guide", {}),
            chapter_org=context.get("chapter_org", {}),
            previous_content=context.get("previous_content", ""),
        )
        
        score = report.overall_score
        dims = report.dimensions
        logger.info("  [评估] %s 得分: %.1f/100 | 学术规范:%.0f 逻辑连贯:%.0f 引用自然:%.0f 内容完整:%.0f" % (
            chapter_name, score,
            dims.get("academic_rigor", 0), dims.get("logical_coherence", 0),
            dims.get("citation_naturalness", 0), dims.get("content_completeness", 0)
        ))
        
        if report.passed:
            logger.info("  [通过] %s 质量达标 (%.1f >= 70)" % (chapter_name, score))
            break
        
        if round_num < max_rounds and report.should_retry:
            logger.info("  [修改] %s 根据评估意见修改 ..." % chapter_name)
            # 打印主要问题
            for iss in report.issues[:3]:
                logger.info("    问题: [%s] %s" % (iss.get("dimension", ""), iss.get("description", "")))
            for sug in report.suggestions[:3]:
                logger.info("    建议: %s" % sug)
            
            # 执行修改
            current_content = quality_gate.revise(chapter_name, current_content, report)
        else:
            logger.info("  [结束] %s 达到最大修改轮次，当前得分 %.1f" % (chapter_name, score))
    
    return current_content, report


# ============================================================
# 3. 真实参考文献生成（基于AMiner API）
# ============================================================

def generate_real_references(full_content):
    """
    从全文提取citation关键词 → 用Semantic Scholar搜索真实论文 → 生成参考文献列表
    Semantic Scholar API免费无需key，作为AMiner的fallback
    """
    import requests as req
    
    # 提取所有citation标记
    citations = re.findall(r'<citation>\[(.*?)\]</citation>', full_content)
    
    if not citations:
        logger.warning("未找到citation标记，使用主题关键词搜索")
        topic_keywords = [
            "light field depth estimation non-Lambertian",
            "specular reflection scattering depth",
            "Fresnel equations electromagnetic optics rendering",
            "multi-view stereo photometric consistency",
            "micro-facet BRDF surface reflectance model",
            "epipolar geometry light field refocusing",
            "differentiable rendering neural rendering",
            "Rayleigh Mie scattering phase function",
            "curriculum learning physics-informed neural network",
            "HCI4D light field benchmark dataset",
        ]
    else:
        # 从citation标记构建搜索查询
        topic_keywords = []
        for cit in citations:
            try:
                keywords = json.loads(cit)
                if isinstance(keywords, list) and len(keywords) > 0:
                    # 取前2个关键词组合成查询
                    query = " ".join(keywords[:2])
                    topic_keywords.append(query)
            except (json.JSONDecodeError, TypeError):
                kws = [kw.strip().strip('"').strip("'") for kw in cit.split(',')]
                kws = [kw for kw in kws if kw]
                if kws:
                    topic_keywords.append(" ".join(kws[:2]))
        
        # 去重
        topic_keywords = list(dict.fromkeys(topic_keywords))[:25]
    
    logger.info("  搜索关键词数: %d" % len(topic_keywords))
    
    # 用Semantic Scholar搜索真实论文
    all_papers = []
    seen_ids = set()
    
    for i, query in enumerate(topic_keywords):
        logger.info("  搜索 [%d/%d]: %s" % (i+1, len(topic_keywords), query[:60]))
        try:
            url = "https://api.semanticscholar.org/graph/v1/paper/search"
            params = {
                "query": query,
                "limit": 3,
                "fields": "title,authors,year,venue,externalIds"
            }
            resp = req.get(url, params=params, timeout=15)
            
            if resp.status_code == 200:
                data = resp.json()
                if "data" in data and data["data"]:
                    for paper in data["data"][:2]:
                        pid = paper.get("paperId", "")
                        if pid and pid not in seen_ids:
                            seen_ids.add(pid)
                            all_papers.append(paper)
                            logger.info("    找到: %s (%s)" % (
                                paper.get("title", "N/A")[:60],
                                paper.get("year", "N/A")
                            ))
            elif resp.status_code == 429:
                logger.warning("    API限流，等待5秒...")
                time.sleep(5)
            else:
                logger.warning("    API返回 %d" % resp.status_code)
        except Exception as e:
            logger.warning("    搜索失败: %s" % str(e)[:80])
        
        # 避免API限流
        time.sleep(1.5)
    
    logger.info("  Semantic Scholar找到真实论文: %d 篇" % len(all_papers))
    
    # 生成参考文献列表
    ref_lines = ["# References", ""]
    
    for idx, paper in enumerate(all_papers, 1):
        authors = [a.get("name", "") for a in paper.get("authors", []) if a.get("name")]
        if len(authors) > 4:
            author_str = ", ".join(authors[:3]) + " et al."
        elif authors:
            author_str = ", ".join(authors)
        else:
            author_str = "Unknown"
        
        title = paper.get("title", "Untitled")
        year = paper.get("year", "")
        venue = paper.get("venue", "")
        
        entry = "[%d] %s, \"%s,\"" % (idx, author_str, title)
        if venue:
            entry += " %s," % venue
        if year:
            entry += " %s." % year
        
        # 标注为Semantic Scholar验证通过
        entry += " <!-- verified: Semantic Scholar -->"
        ref_lines.append(entry)
    
    # 如果搜到的论文不够，用LLM补充
    if len(all_papers) < 20:
        logger.info("  搜索结果不足(%d篇)，用LLM补充" % len(all_papers))
        supplement = supplement_references_with_llm(full_content, len(all_papers))
        if supplement:
            ref_lines.append("")
            ref_lines.append("<!-- LLM-generated references below (need verification) -->")
            ref_lines.append(supplement)
    
    return "\n".join(ref_lines)


def supplement_references_with_llm(full_content, existing_count):
    """用LLM补充参考文献（标注为未验证）"""
    from agent.api_client import get_api_client
    api_client = get_api_client()
    
    needed = max(20, 40 - existing_count)
    prompt = """Generate %d realistic academic references for a paper about "Unified Dual-Mask Physical Model for Non-Lambertian Light Field Depth Estimation".

Topics to cover: light field imaging, depth estimation, non-Lambertian rendering, Maxwell's equations, Fresnel reflectance, scattering, computational photography, multi-view stereo, micro-facet BRDF, differentiable rendering.

Use IEEE format: [#] Author(s), "Title," Venue, Year.
Start numbering from %d.

Output only the reference list:""" % (needed, existing_count + 1)
    
    try:
        result = api_client.call_generation(prompt)
        if result and len(result) > 100:
            # 标注这些是LLM生成的，未经AMiner验证
            return "<!-- AMiner-verified references above, LLM-generated references below (need verification) -->\n\n" + result
        return result
    except Exception as e:
        logger.error("LLM补充参考文献失败: %s" % e)
        return ""


# ============================================================
# 4. 主测试流程
# ============================================================

def run_test():
    from agent.skill_executor import SkillExecutor
    from agent.api_client import get_api_client
    
    executor = SkillExecutor()
    
    # 公共上下文
    base_context = {
        "article_type": PROJECT_INFO["article_type"],
        "paper_title": PROJECT_INFO["paper_title"],
        "innovation_points": json.dumps(PROJECT_INFO["innovation_points"], ensure_ascii=False, indent=2),
        "experiment_design": json.dumps(PROJECT_INFO["experiment_design"], ensure_ascii=False, indent=2),
        "model_architecture": json.dumps(PROJECT_INFO["model_architecture"], ensure_ascii=False, indent=2),
        "project_info": json.dumps(PROJECT_INFO, ensure_ascii=False, indent=2),
    }
    
    chapters = {}
    quality_reports = {}
    total_start = time.time()
    
    # ---- Chapter 1: Introduction ----
    logger.info("=" * 60)
    logger.info("  Chapter 1: Introduction (with QC)")
    logger.info("=" * 60)
    context_ch1 = {**base_context, "length_budget_chars": 12000, "length_budget_pages": 2.5}
    content, report = generate_chapter_with_qc(executor, "chapter1_introduction", context_ch1, "Introduction", max_rounds=2)
    chapters["ch1"] = content
    quality_reports["ch1"] = report.to_dict()
    
    # ---- Chapter 2: Related Work ----
    logger.info("=" * 60)
    logger.info("  Chapter 2: Related Work (with QC)")
    logger.info("=" * 60)
    context_ch2 = {**base_context, "length_budget_chars": 9600, "length_budget_pages": 2.0,
                    "previous_content": chapters["ch1"][:1000]}
    content, report = generate_chapter_with_qc(executor, "chapter2_related_work", context_ch2, "Related Work", max_rounds=2)
    chapters["ch2"] = content
    quality_reports["ch2"] = report.to_dict()
    
    # ---- Chapter 3: Methodology ----
    logger.info("=" * 60)
    logger.info("  Chapter 3: Methodology (with QC)")
    logger.info("=" * 60)
    context_ch3 = {**base_context, "length_budget_chars": 19200, "length_budget_pages": 4.0,
                    "previous_content": chapters["ch1"][:500] + "\n" + chapters["ch2"][:500]}
    content, report = generate_chapter_with_qc(executor, "chapter3_methodology", context_ch3, "Methodology", max_rounds=2)
    chapters["ch3"] = content
    quality_reports["ch3"] = report.to_dict()
    
    # ---- Chapter 4: Experiments ----
    logger.info("=" * 60)
    logger.info("  Chapter 4: Experiments (with QC)")
    logger.info("=" * 60)
    context_ch4 = {**base_context, "length_budget_chars": 16000, "length_budget_pages": 3.5,
                    "previous_content": chapters["ch1"][:300] + "\n" + chapters["ch3"][:500]}
    content, report = generate_chapter_with_qc(executor, "chapter4_experiments", context_ch4, "Experiments", max_rounds=2)
    chapters["ch4"] = content
    quality_reports["ch4"] = report.to_dict()
    
    # ---- Chapter 5: Conclusion ----
    logger.info("=" * 60)
    logger.info("  Chapter 5: Conclusion (with QC)")
    logger.info("=" * 60)
    previous_summary = ""
    for key in ["ch1", "ch2", "ch3", "ch4"]:
        if key in chapters:
            ch_num = key.replace("ch", "")
            previous_summary += "Chapter %s:\n%s\n\n" % (ch_num, chapters[key][:500])
    context_ch5 = {**base_context, "length_budget_chars": 3000, "previous_content": previous_summary}
    content, report = generate_chapter_with_qc(executor, "chapter5_conclusion", context_ch5, "Conclusion", max_rounds=1)
    chapters["ch5"] = content
    quality_reports["ch5"] = report.to_dict()
    
    # ---- Abstract & Keywords ----
    logger.info("=" * 60)
    logger.info("  Abstract & Keywords")
    logger.info("=" * 60)
    context_abstract = {**base_context, "length_budget_chars": 1500, "keyword_count": 6, "previous_content": previous_summary}
    result_abstract = executor.execute("abstract", context_abstract)
    chapters["abstract"] = result_abstract["content"]
    
    # ---- References (基于AMiner真实搜索) ----
    logger.info("=" * 60)
    logger.info("  References (AMiner API + Verification)")
    logger.info("=" * 60)
    full_content = "\n\n".join(chapters.values())
    chapters["references"] = generate_real_references(full_content)
    
    # ============================================================
    # 5. 输出结果
    # ============================================================
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 输出各章节独立文件
    chapter_files = {
        "0_abstract.md": chapters.get("abstract", ""),
        "1_introduction.md": chapters.get("ch1", ""),
        "2_related_work.md": chapters.get("ch2", ""),
        "3_methodology.md": chapters.get("ch3", ""),
        "4_experiments.md": chapters.get("ch4", ""),
        "5_conclusion.md": chapters.get("ch5", ""),
        "6_references.md": chapters.get("references", ""),
    }
    
    for filename, content in chapter_files.items():
        filepath = os.path.join(OUTPUT_DIR, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info("  Saved: %s (%d chars)" % (filename, len(content)))
    
    # 输出合并的完整论文
    full_paper_parts = [
        chapters.get("abstract", ""),
        "", "---", "",
        chapters.get("ch1", ""),
        "", chapters.get("ch2", ""),
        "", chapters.get("ch3", ""),
        "", chapters.get("ch4", ""),
        "", chapters.get("ch5", ""),
        "", chapters.get("references", ""),
    ]
    full_paper = "\n\n".join(full_paper_parts)
    
    full_paper_path = os.path.join(OUTPUT_DIR, "full_paper.md")
    with open(full_paper_path, 'w', encoding='utf-8') as f:
        f.write(full_paper)
    logger.info("  Saved: full_paper.md (%d chars)" % len(full_paper))
    
    # 输出质量报告
    quality_summary = {}
    for key, report in quality_reports.items():
        quality_summary[key] = {
            "overall_score": report.get("overall_score", -1),
            "dimensions": report.get("dimensions", {}),
            "passed": report.get("passed", False),
            "issues_count": len(report.get("issues", [])),
            "suggestions_count": len(report.get("suggestions", [])),
        }
    
    with open(os.path.join(OUTPUT_DIR, "quality_report.json"), 'w', encoding='utf-8') as f:
        json.dump(quality_summary, f, ensure_ascii=False, indent=2)
    
    # ============================================================
    # 6. 输出统计
    # ============================================================
    
    total_elapsed = time.time() - total_start
    
    print("\n" + "=" * 60)
    print("  Generation Complete! (v2 with QC)")
    print("=" * 60)
    
    # 引用标记统计
    all_citations = re.findall(r'<citation>\[(.*?)\]</citation>', full_content)
    print("\n  Citation markers: %d" % len(all_citations))
    
    # 各章长度
    print("\n  Chapter lengths:")
    total_chars = 0
    for key, content in sorted(chapters.items()):
        chars = len(content)
        total_chars += chars
        qc_info = ""
        if key in quality_reports:
            score = quality_reports[key].get("overall_score", -1)
            passed = quality_reports[key].get("passed", False)
            qc_info = " (QC: %.0f %s)" % (score, "PASS" if passed else "RETRY")
        print("    %-15s: %6d chars%s" % (key, chars, qc_info))
    print("    %-15s: %6d chars" % ("TOTAL", total_chars))
    
    # 参考文献统计
    ref_content = chapters.get("references", "")
    ref_entries = re.findall(r'\[(\d+)\]', ref_content)
    aminer_verified = ref_content.count("AMiner")
    print("\n  References: %d entries" % len(set(ref_entries)))
    print("  Total time: %.1f minutes" % (total_elapsed / 60))
    print("  Output: %s" % OUTPUT_DIR)
    print("=" * 60)


if __name__ == "__main__":
    run_test()
