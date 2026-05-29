# -*- coding: utf-8 -*-
"""
全局大纲规划器 - Phase 0.5

核心策略：
1. 基于 ref_pdf 的章节组织 + 项目数据分析，生成全局大纲
2. 为每章定义 Content Checklist（必须覆盖的内容项）
3. 定义篇幅预算（字数/段落分配）
4. 用户确认环节：大纲确认后再开始写作

解决问题：
- 各章独立生成导致 Introduction 提到的 Section VI/VII 不存在
- Methodology content_completeness 仅 35/100
- 内容组织缺少全局视角
"""

import json
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# 各章节的内容清单模板
CONTENT_CHECKLISTS = {
    "Introduction": [
        "研究背景与问题重要性（宏观→微观）",
        "现有方法的系统性局限分析（按类别）",
        "本文方法的核心思路概述",
        "3-4条具体贡献（每条含：提出了什么、解决了什么、带来了什么提升）",
        "论文组织结构概述（各章节概述）",
    ],
    "Related Work": [
        "按技术路线分类的系统性综述",
        "每类方法的核心思想和代表工作",
        "每类方法的关键不足（引出本文的必要性）",
        "与本文方法的差异化说明",
        "章节小结（总结现有工作不足，引出本文方法）",
    ],
    "Methodology": [
        "总体架构概述（含输入→模块→特征→处理→输出的完整数据流）",
        "各模块详细描述（设计动机、输入输出维度、数学公式推导、与前后模块的衔接）",
        "损失函数完整定义（总损失、各分量、权重设置、物理含义）",
        "训练策略细节（优化器、学习率、训练epoch、数据增强）",
        "推理流程说明",
        "计算复杂度分析（可选）",
        "架构图（TikZ）与正文的一致性",
    ],
    "Experiments": [
        "实验设置（硬件、软件、超参数）",
        "数据集描述（规模、属性、预处理方式）",
        "评价指标定义",
        "与 SOTA 的定量对比（表格 + 分析）",
        "消融实验（逐模块验证有效性）",
        "定性分析（可视化对比）",
        "效率分析（运行时间、参数量）",
    ],
    "Conclusion": [
        "核心贡献总结",
        "关键实验结论",
        "局限性讨论",
        "未来工作方向（具体技术路线）",
    ],
}

# 各章节篇幅预算（词数）
LENGTH_BUDGETS = {
    "Introduction": {"min": 800, "max": 1500, "target": 1200},
    "Related Work": {"min": 800, "max": 1500, "target": 1200},
    "Methodology": {"min": 1500, "max": 3000, "target": 2500},
    "Experiments": {"min": 1000, "max": 2500, "target": 1800},
    "Conclusion": {"min": 400, "max": 800, "target": 600},
}


class StructurePlanner:
    """
    全局大纲规划器

    工作流程：
    1. 分析 ref_pdf 的章节组织结构
    2. 结合项目数据，为每章生成详细子节大纲
    3. 定义 Content Checklist 和篇幅预算
    4. 生成 outline.json
    """

    def __init__(self, api_client=None):
        self.api_client = api_client

    def plan(self, project_data: Dict, ref_data: Dict) -> Dict:
        """
        生成全局大纲

        Returns:
            {
                "outline": {
                    "Introduction": {
                        "subsections": [...],
                        "key_arguments": [...],
                        "content_checklist": [...],
                        "length_budget": {...},
                    },
                    ...
                },
                "global_constraints": {
                    "total_word_target": ...,
                    "figure_budget": ...,
                    "table_budget": ...,
                }
            }
        """
        outline = {}

        chapter_names = ["Introduction", "Related Work", "Methodology",
                        "Experiments", "Conclusion"]

        for chapter_name in chapter_names:
            chapter_outline = self._plan_chapter(
                chapter_name, project_data, ref_data
            )
            outline[chapter_name] = chapter_outline

        total_words = sum(
            info["length_budget"]["target"]
            for info in outline.values()
        )

        global_constraints = {
            "total_word_target": total_words,
            "figure_budget": 5,
            "table_budget": 4,
            "prohibited_terms": self._get_prohibited_terms(),
            "format": "Markdown（禁止混用 LaTeX 块级元素）",
        }

        result = {
            "outline": outline,
            "global_constraints": global_constraints,
        }

        logger.info(f"[StructurePlanner] 大纲规划完成，目标总词数: {total_words}")
        return result

    def _plan_chapter(self, chapter_name: str,
                      project_data: Dict, ref_data: Dict) -> Dict:
        """为单个章节生成详细大纲"""
        ref_chapter_org = ref_data.get("chapter_organizations", {}).get(chapter_name, {})
        ref_structure = ref_chapter_org.get("章节结构", []) if isinstance(ref_chapter_org, dict) else []

        subsections = self._derive_subsections(
            chapter_name, project_data, ref_structure
        )

        checklist = CONTENT_CHECKLISTS.get(chapter_name, [])
        budget = LENGTH_BUDGETS.get(chapter_name, {"min": 500, "max": 2000, "target": 1000})
        key_arguments = self._derive_key_arguments(chapter_name, project_data)
        expected_citations = self._derive_expected_citations(chapter_name, project_data)

        return {
            "subsections": subsections,
            "key_arguments": key_arguments,
            "content_checklist": checklist,
            "length_budget": budget,
            "expected_citations": expected_citations,
            "ref_structure": ref_structure[:3] if ref_structure else [],
        }

    def _derive_subsections(self, chapter_name: str,
                            project_data: Dict, ref_structure: List) -> List[Dict]:
        """推导章节的子节结构"""
        if chapter_name == "Introduction":
            return [
                {"title": "1.1 Background and Motivation", "description": "研究背景与问题重要性"},
                {"title": "1.2 Limitations of Existing Methods", "description": "现有方法的局限性"},
                {"title": "1.3 Proposed Method and Contributions", "description": "本文方法与贡献"},
            ]
        elif chapter_name == "Related Work":
            return [
                {"title": "2.1 Category A Methods", "description": "按技术路线分类综述"},
                {"title": "2.2 Category B Methods", "description": "按技术路线分类综述"},
                {"title": "2.3 Summary", "description": "总结现有工作不足"},
            ]
        elif chapter_name == "Methodology":
            subsections = [
                {"title": "3.1 Overall Architecture", "description": "总体架构概述"},
            ]
            modules = project_data.get("model_architecture", {}).get("模块详情", [])
            innovation = project_data.get("innovation_points", [])
            source = modules if modules else innovation
            for i, item in enumerate(source):
                name = item.get("模块名", item.get("创新点名称", f"Component {i+1}"))
                desc = item.get("核心操作", item.get("创新点价值", ""))
                subsections.append({
                    "title": f"3.{i+2} {name}",
                    "description": desc,
                })
            subsections.append({
                "title": f"3.{len(source)+2} Training Objective",
                "description": "损失函数与训练策略",
            })
            return subsections
        elif chapter_name == "Experiments":
            return [
                {"title": "4.1 Experimental Setup", "description": "数据集、评价指标、实现细节"},
                {"title": "4.2 Comparison with State-of-the-art", "description": "SOTA 定量对比"},
                {"title": "4.3 Ablation Study", "description": "消融实验"},
                {"title": "4.4 Qualitative Analysis", "description": "定性分析与可视化"},
            ]
        elif chapter_name == "Conclusion":
            return [
                {"title": "5.1 Summary of Contributions", "description": "核心贡献总结"},
                {"title": "5.2 Limitations and Future Work", "description": "局限性与未来方向"},
            ]
        return []

    def _derive_key_arguments(self, chapter_name: str, project_data: Dict) -> List[str]:
        """推导章节的关键论点"""
        arguments = []
        innovation = project_data.get("innovation_points", [])

        if chapter_name == "Introduction":
            for ip in innovation[:3]:
                arguments.append(f"Contribution: {ip.get('创新点名称', 'N/A')} - {ip.get('创新点价值', 'N/A')}")
        elif chapter_name == "Methodology":
            for ip in innovation:
                works = "; ".join(ip.get('创新点工作内容', []))
                arguments.append(f"Module motivation and design: {works}")
        elif chapter_name == "Experiments":
            exp = project_data.get("experiment_design", {})
            datasets = exp.get("数据集", [])
            if datasets:
                ds_names = [ds if isinstance(ds, str) else ds.get("名称", "") for ds in datasets]
                arguments.append(f"Datasets: {', '.join(ds_names)}")
        return arguments

    def _derive_expected_citations(self, chapter_name: str, project_data: Dict) -> List[str]:
        """推导预期的引用位置描述"""
        citation_map = {
            "Introduction": [
                "背景描述段（领域总体引用）",
                "现有方法分析段（各方法类别引用）",
                "贡献段（本文相关技术引用）",
            ],
            "Related Work": [
                "每类方法的代表工作（2-3 篇/类）",
                "与本文方法对比的引用",
            ],
            "Methodology": [
                "各模块相关的技术引用",
                "公式来源引用",
            ],
            "Experiments": [
                "数据集引用",
                "baselines 引用",
                "评价指标引用",
            ],
        }
        return citation_map.get(chapter_name, [])

    def _get_prohibited_terms(self) -> List[str]:
        """获取禁用术语列表"""
        try:
            from config.project_config import get_article_type_info
            return get_article_type_info().get("prohibited_terms", [])
        except Exception:
            return []

    def save(self, outline_data: Dict, output_dir: str):
        """保存大纲到磁盘"""
        import os
        filepath = os.path.join(output_dir, "outline.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(outline_data, f, ensure_ascii=False, indent=2)
        logger.info(f"[StructurePlanner] 大纲已保存到 {filepath}")

    def load(self, output_dir: str) -> Optional[Dict]:
        """从磁盘加载大纲"""
        import os
        filepath = os.path.join(output_dir, "outline.json")
        if not os.path.exists(filepath):
            return None
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

    def format_outline_for_display(self, outline_data: Dict) -> str:
        """格式化大纲用于用户确认"""
        lines = ["=" * 60, "  论文大纲规划", "=" * 60, ""]

        for chapter_name, chapter_info in outline_data.get("outline", {}).items():
            budget = chapter_info.get("length_budget", {})
            target = budget.get("target", "?")
            lines.append(f"## {chapter_name} (目标 {target} 词)")

            for sub in chapter_info.get("subsections", []):
                title = sub.get("title", "")
                desc = sub.get("description", "")
                lines.append(f"  {title}: {desc}")

            lines.append("")

            checklist = chapter_info.get("content_checklist", [])
            if checklist:
                lines.append("  Content Checklist:")
                for i, item in enumerate(checklist, 1):
                    lines.append(f"    {i}. {item}")
                lines.append("")

        lines.append("-" * 60)
        constraints = outline_data.get("global_constraints", {})
        lines.append(f"总词数目标: {constraints.get('total_word_target', '?')}")
        lines.append(f"图表预算: {constraints.get('figure_budget', '?')} 图, {constraints.get('table_budget', '?')} 表")

        return "\n".join(lines)


def run_structure_planner(project_data: Dict, ref_data: Dict,
                          api_client=None) -> Dict:
    """
    主入口：生成全局大纲
    """
    from config.project_config import OUTPUT_DIR

    planner = StructurePlanner(api_client)
    outline = planner.plan(project_data, ref_data)
    planner.save(outline, OUTPUT_DIR)

    display = planner.format_outline_for_display(outline)
    print(display)
    print("\n[StructurePlanner] 请检查大纲，如需修改请编辑 output/outline.json")
    print("[StructurePlanner] 确认无误后将继续生成...")

    return outline
