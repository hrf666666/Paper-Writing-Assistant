# -*- coding: utf-8 -*-
"""
审计模块 - 反幻觉验证引擎

v5.0 核心新增：彻底解决大模型幻觉和虚假思考问题

三大审计能力：
1. 逐步验证（Step Audit）：检查每个Phase的输出是否真实完成了预期工作
2. 参考文献反向检索（Reference Reverse Verification）：通过Semantic Scholar反向验证引文真实存在
3. 内容真实性校验（Content Factuality Check）：验证论文中的具体声明是否有依据

设计原则：
- 零信任：不盲目信任LLM输出，所有关键声明都需要外部验证
- 可追溯：每条审计结果都有明确的数据来源
- 不阻塞：审计失败标记为warning，不阻断主流程，但汇总到最终报告
"""

import os
import re
import json
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

from agent.api_client import get_api_client, UnifiedAPIClient
from config.project_config import PAPER_TITLE, OUTPUT_DIR

logger = logging.getLogger(__name__)


@dataclass
class AuditIssue:
    """审计发现的问题"""
    severity: str          # "critical" | "warning" | "info"
    category: str          # "reference" | "factuality" | "step_completion" | "consistency"
    description: str       # 问题描述
    location: str          # 问题位置（章节、引用编号等）
    evidence: str          # 证据或依据
    suggestion: str        # 修正建议


@dataclass
class AuditReport:
    """审计报告"""
    phase_name: str
    timestamp: float = 0.0
    issues: List[AuditIssue] = field(default_factory=list)
    passed: bool = True
    summary: str = ""

    def add_issue(self, severity: str, category: str, description: str,
                  location: str = "", evidence: str = "", suggestion: str = ""):
        issue = AuditIssue(
            severity=severity, category=category,
            description=description, location=location,
            evidence=evidence, suggestion=suggestion,
        )
        self.issues.append(issue)
        if severity == "critical":
            self.passed = False

    def to_dict(self) -> dict:
        return {
            "phase_name": self.phase_name,
            "timestamp": self.timestamp,
            "passed": self.passed,
            "summary": self.summary,
            "issue_count": len(self.issues),
            "critical_count": sum(1 for i in self.issues if i.severity == "critical"),
            "warning_count": sum(1 for i in self.issues if i.severity == "warning"),
            "issues": [
                {
                    "severity": i.severity,
                    "category": i.category,
                    "description": i.description,
                    "location": i.location,
                    "evidence": i.evidence,
                    "suggestion": i.suggestion,
                }
                for i in self.issues
            ],
        }


class Auditor:
    """
    反幻觉审计引擎

    在每个关键步骤后执行审计，确保：
    1. 参考文献真实存在（不是编造的）
    2. 论文声明有据可查（不是幻觉）
    3. 每个Phase确实完成了预期工作
    """

    def __init__(self, api_client: UnifiedAPIClient = None):
        self.api_client = api_client or get_api_client()
        self._reports: List[AuditReport] = []
        self._verified_refs: Dict[str, Dict] = {}  # 缓存已验证的参考文献

    def audit_chapter(self, phase_name: str, chapter_name: str,
                      chapter_content: str, project_data: Dict = None,
                      ref_data: Dict = None) -> AuditReport:
        """
        对章节内容进行全面审计

        Args:
            phase_name: 阶段名 (如 "phase1")
            chapter_name: 章节名 (如 "Introduction")
            chapter_content: 章节内容
            project_data: 项目分析数据（用于交叉验证）
            ref_data: 参考PDF数据

        Returns:
            AuditReport: 审计报告
        """
        report = AuditReport(phase_name=phase_name, timestamp=time.time())

        # 1. 步骤完成度检查
        self._audit_step_completion(report, chapter_name, chapter_content, project_data)

        # 2. 参考文献反向检索
        self._audit_references(report, chapter_content)

        # 3. 内容真实性校验
        self._audit_factuality(report, chapter_name, chapter_content, project_data)

        # 4. 内部一致性检查
        self._audit_consistency(report, chapter_name, chapter_content, project_data)

        # 汇总
        critical = sum(1 for i in report.issues if i.severity == "critical")
        warnings = sum(1 for i in report.issues if i.severity == "warning")
        report.summary = (
            f"审计完成: {len(report.issues)} 个问题 "
            f"({critical} 严重, {warnings} 警告)"
        )

        logger.info(f"[审计] {chapter_name}: {report.summary}")
        self._reports.append(report)
        return report

    def audit_abstract(self, abstract_content: str,
                       chapters: Dict[int, str], project_data: Dict = None) -> AuditReport:
        """
        审计摘要：检查摘要中的声明是否与正文一致

        Args:
            abstract_content: 摘要内容
            chapters: 各章内容
            project_data: 项目数据
        """
        report = AuditReport(phase_name="phase5_5", timestamp=time.time())

        # 检查摘要中的关键声明是否在正文中有支撑
        self._audit_abstract_vs_chapters(report, abstract_content, chapters, project_data)

        # 参考文献审计
        self._audit_references(report, abstract_content)

        critical = sum(1 for i in report.issues if i.severity == "critical")
        warnings = sum(1 for i in report.issues if i.severity == "warning")
        report.summary = (
            f"摘要审计完成: {len(report.issues)} 个问题 "
            f"({critical} 严重, {warnings} 警告)"
        )

        logger.info(f"[审计] Abstract: {report.summary}")
        self._reports.append(report)
        return report

    def audit_ablation(self, ablation_design: Dict,
                       project_data: Dict = None) -> AuditReport:
        """
        审计消融实验设计：检查是否与代码结构和ref_pdf一致
        """
        report = AuditReport(phase_name="phase_ablation", timestamp=time.time())

        experiments = ablation_design.get("ablation_experiments", [])
        if not experiments:
            report.add_issue(
                "warning", "step_completion",
                "消融实验设计为空", "",
                "未找到消融实验设计方案",
                "请确保消融实验设计已完成"
            )
        else:
            # 检查每个消融实验是否有明确的目标模块和修改方式
            model_arch = (project_data or {}).get("model_architecture", {})
            module_names = set()
            for mod in model_arch.get("模块详情", []):
                module_names.add(mod.get("模块名", "").lower())

            for exp in experiments:
                target = exp.get("target_module", "")
                if target and module_names and target.lower() not in module_names:
                    report.add_issue(
                        "warning", "factuality",
                        f"消融实验目标模块 '{target}' 不在已识别的模型模块中",
                        exp.get("experiment_name", ""),
                        f"已识别模块: {', '.join(module_names)}",
                        "请确认目标模块名称与代码中一致"
                    )

        critical = sum(1 for i in report.issues if i.severity == "critical")
        warnings = sum(1 for i in report.issues if i.severity == "warning")
        report.summary = f"消融实验审计完成: {len(report.issues)} 个问题 ({critical} 严重, {warnings} 警告)"

        logger.info(f"[审计] Ablation: {report.summary}")
        self._reports.append(report)
        return report

    def audit_with_autofix(self, phase_name: str, chapter_name: str,
                           chapter_content: str, project_data: Dict = None,
                           ref_data: Dict = None, api_client=None,
                           max_fix_rounds: int = 1) -> Tuple[str, AuditReport]:
        """
        审计 + 自动修正循环

        如果发现 critical issue，尝试自动修正并重新审计。
        修正策略：根据 issue 的 category 选择不同的修正 prompt。

        Args:
            phase_name: 阶段名
            chapter_name: 章节名
            chapter_content: 章节内容
            project_data: 项目数据
            ref_data: 参考PDF数据
            api_client: API 客户端（用于生成修正内容）
            max_fix_rounds: 最大修正轮次

        Returns:
            (修正后的内容, 最终审计报告)
        """
        current_content = chapter_content
        report = None

        for round_num in range(max_fix_rounds + 1):
            report = self.audit_chapter(
                phase_name, chapter_name, current_content,
                project_data, ref_data
            )

            # 检查是否还有 critical issues
            critical_issues = [i for i in report.issues if i.severity == "critical"]
            if not critical_issues or round_num >= max_fix_rounds:
                break

            if not api_client:
                logger.warning("[auditor] 发现 critical issues 但无 api_client，无法自动修正")
                break

            # 尝试自动修正
            logger.info(f"[auditor] {chapter_name} 发现 {len(critical_issues)} 个严重问题，尝试第{round_num+1}轮自动修正")

            fix_prompt = self._build_autofix_prompt(
                chapter_name, current_content, critical_issues, project_data
            )

            try:
                fixed_content = api_client.call_generation(fix_prompt)
                if fixed_content and len(fixed_content) > len(current_content) * 0.5:
                    current_content = fixed_content
                    logger.info(f"[auditor] {chapter_name} 第{round_num+1}轮修正完成")
                else:
                    logger.warning(f"[auditor] {chapter_name} 修正内容过短，可能修正失败")
                    break
            except Exception as e:
                logger.error(f"[auditor] 自动修正失败: {e}")
                break

        return current_content, report

    def _build_autofix_prompt(self, chapter_name: str, content: str,
                              critical_issues: List[AuditIssue],
                              project_data: Dict = None) -> str:
        """构建自动修正 prompt"""
        issues_text = "\n".join(
            f"- [{i.category}] {i.description}\n  位置: {i.location}\n  建议: {i.suggestion}"
            for i in critical_issues
        )

        prompt = f"""你是一名学术论文修改专家。以下章节 "{chapter_name}" 经审计发现严重问题，请逐一修正。

**发现的严重问题**:
{issues_text}

**待修正内容**:
<chapter_content>
{content[:8000]}
</chapter_content>

**修正要求**:
1. 逐一解决上述每个严重问题
2. 保持原文的整体结构和论述逻辑
3. 如果数值无法确认真实性，替换为占位符 'X.XX'
4. 如果引用无法验证，删除该引用或替换为更通用的表述
5. 保持学术化表述

请直接给出修正后的完整章节内容（Markdown格式），无需解释："""

        return prompt

    # ========== 步骤完成度审计 ==========

    def _audit_step_completion(self, report: AuditReport, chapter_name: str,
                               content: str, project_data: Dict = None):
        """检查章节是否真正完成了预期工作"""
        # 定义每个章节必须包含的关键元素
        required_elements = {
            "Introduction": {
                "min_length": 1500,
                "must_contain": ["contribution", "propose", "method"],
                "must_have_sections": 2,
            },
            "Related Work": {
                "min_length": 2000,
                "must_contain": ["citation"],
                "must_have_sections": 2,
            },
            "Methodology": {
                "min_length": 3000,
                "must_contain": ["proposed", "framework", "module"],
                "must_have_sections": 3,
            },
            "Experiments": {
                "min_length": 2000,
                "must_contain": ["dataset", "result", "comparison"],
                "must_have_sections": 2,
            },
            "Conclusion": {
                "min_length": 800,
                "must_contain": ["conclusion", "future"],
                "must_have_sections": 1,
            },
        }

        requirements = required_elements.get(chapter_name, {})
        if not requirements:
            return

        # 长度检查
        min_len = requirements.get("min_length", 0)
        if len(content) < min_len:
            report.add_issue(
                "warning", "step_completion",
                f"章节内容过短（{len(content)}字 < 最低{min_len}字），可能未充分展开",
                chapter_name,
                f"实际长度: {len(content)}, 最低要求: {min_len}",
                "补充更多内容细节"
            )

        # 关键词检查
        content_lower = content.lower()
        for kw in requirements.get("must_contain", []):
            if kw.lower() not in content_lower:
                report.add_issue(
                    "warning", "step_completion",
                    f"章节缺少关键内容元素: '{kw}'",
                    chapter_name,
                    f"在章节中未找到 '{kw}' 相关内容",
                    f"确保章节包含与 '{kw}' 相关的论述"
                )

        # 段落/子章节数检查
        sections = re.findall(r'^#{1,3}\s+\S+', content, re.MULTILINE)
        min_sections = requirements.get("must_have_sections", 0)
        if len(sections) < min_sections:
            report.add_issue(
                "info", "step_completion",
                f"章节子节数量偏少（{len(sections)} < 建议的{min_sections}），结构可能不够完整",
                chapter_name,
                f"当前子节: {[s.strip() for s in sections]}",
                "考虑增加子节以更好组织内容"
            )

        # 创新点覆盖检查（针对Introduction和Methodology）
        if project_data and chapter_name in ("Introduction", "Methodology"):
            innovation_points = project_data.get("innovation_points", [])
            for ip in innovation_points:
                ip_name = ip.get("创新点名称", "")
                if ip_name and ip_name.lower() not in content_lower:
                    report.add_issue(
                        "warning", "step_completion",
                        f"创新点 '{ip_name}' 未在章节中被提及",
                        chapter_name,
                        f"项目分析中识别了 {len(innovation_points)} 个创新点，此章节未覆盖 '{ip_name}'",
                        f"在章节中补充对 '{ip_name}' 的描述"
                    )

    # ========== 参考文献反向检索审计 ==========

    def _audit_references(self, report: AuditReport, content: str):
        """
        反向检索审计：验证论文中的参考文献是否真实存在

        两种引用格式：
        1. <citation>[["kw1", "kw2"], ["kw3"]]</citation> - 嵌套关键词格式
        2. [n] Author. Title. Venue, Year. - 数字编号格式
        """
        # 1. 提取<citation>标记
        citation_pattern = r'<citation>(.*?)</citation>'
        citations = re.findall(citation_pattern, content, re.DOTALL)

        # 2. 提取数字引用 [n]
        numeric_refs = re.findall(r'\[(\d+)\]', content)

        # 3. 提取参考文献列表
        ref_entries = self._extract_bibliography(content)

        # 审计 citation 标记
        for i, tag in enumerate(citations):
            self._verify_citation_tag(report, tag, i + 1, len(citations))

        # 审计参考文献条目
        for entry in ref_entries:
            self._verify_bibliography_entry(report, entry)

    def _extract_bibliography(self, content: str) -> List[Dict]:
        """从内容中提取参考文献条目"""
        entries = []
        # 尝试匹配参考文献区域
        ref_section = ""
        markers = ["# References", "# Bibliography", "## References", "## Bibliography"]
        for marker in markers:
            idx = content.find(marker)
            if idx != -1:
                ref_section = content[idx:]
                break

        if not ref_section:
            return entries

        # 匹配 [n] Author. Title. 格式
        entry_pattern = r'\[(\d+)\]\s*(.*?)(?=\n\[\d+\]|\Z)'
        matches = re.findall(entry_pattern, ref_section, re.DOTALL)
        for num, text in matches:
            entries.append({"index": int(num), "content": text.strip()})

        return entries

    def _verify_citation_tag(self, report: AuditReport, tag: str,
                             idx: int, total: int):
        """验证<citation>标记中的搜索关键词是否能检索到真实论文"""
        # 解析关键词
        try:
            import ast
            keywords = ast.literal_eval(tag.strip())
            if not isinstance(keywords, list):
                keywords = [[tag.strip()]]
        except (ValueError, SyntaxError):
            keywords = [[tag.strip()]]

        # 优先使用MCP增强验证
        try:
            from api.paper_search import verify_citation_with_mcp
            query_str = " ".join(keywords[0]) if keywords else tag
            verification = verify_citation_with_mcp(query_str)

            if verification["verified"]:
                self._verified_refs[tag] = {
                    "verified": True,
                    "confidence": verification["confidence"],
                    "found_urls": verification.get("found_urls", []),
                    "method": verification.get("method", "mcp"),
                }
            else:
                report.add_issue(
                    "critical", "reference",
                    f"引用#{idx}无法检索到任何论文，可能是编造的引用",
                    f"<citation>{tag}</citation>",
                    f"搜索关键词: {keywords}, MCP+Semantic Scholar均无结果",
                    "请替换为真实可检索的参考文献"
                )
        except ImportError:
            # 回退到Semantic Scholar
            try:
                from api.paper_search import search_papers_semantic
                query_str = " ".join(keywords[0]) if keywords else tag
                results = search_papers_semantic(query_str, limit=3)

                if not results:
                    report.add_issue(
                        "critical", "reference",
                        f"引用#{idx}无法检索到任何论文，可能是编造的引用",
                        f"<citation>{tag}</citation>",
                        f"搜索关键词: {keywords}, 无任何结果",
                        "请替换为真实可检索的参考文献"
                    )
                else:
                    self._verified_refs[tag] = {
                        "verified": True,
                        "found_papers": len(results),
                        "top_result": {
                            "title": results[0].get("title", ""),
                            "year": results[0].get("year", ""),
                            "authors": [a.get("name", "") for a in results[0].get("authors", [])][:3],
                        },
                        "method": "semantic_scholar",
                    }
            except Exception as e:
                report.add_issue(
                    "info", "reference",
                    f"引用#{idx}检索时发生异常",
                    f"<citation>{tag}</citation>",
                    str(e)[:200],
                    "请人工确认此引用的真实性"
                )
        except Exception as e:
            report.add_issue(
                "info", "reference",
                f"引用#{idx}检索时发生异常",
                f"<citation>{tag}</citation>",
                str(e)[:200],
                "请人工确认此引用的真实性"
            )

    def _verify_bibliography_entry(self, report: AuditReport, entry: Dict):
        """验证参考文献条目是否真实存在"""
        content = entry.get("content", "")
        index = entry.get("index", 0)

        if not content or len(content) < 20:
            report.add_issue(
                "warning", "reference",
                f"参考文献[{index}]内容过短，可能不完整",
                f"[{index}]",
                f"内容: {content[:100]}",
                "请补充完整的参考文献信息"
            )
            return

        # 提取标题（通常是引号中的内容或第一个句号前的内容）
        title_match = re.search(r'"(.+?)"', content)
        title = title_match.group(1) if title_match else content.split(".")[0]

        # 优先使用MCP增强验证
        try:
            from api.paper_search import deep_verify_reference
            verification = deep_verify_reference(content)

            if not verification["verified"]:
                issues_str = "; ".join(verification.get("issues", []))
                report.add_issue(
                    "critical", "reference",
                    f"参考文献[{index}]无法检索到匹配论文，可能是编造的",
                    f"[{index}] {content[:80]}",
                    f"验证结果: {issues_str}",
                    "请替换为真实可检索的参考文献"
                )
            else:
                # 检查置信度
                confidence = verification.get("confidence", 0)
                if confidence < 0.7:
                    report.add_issue(
                        "warning", "reference",
                        f"参考文献[{index}]检索置信度较低",
                        f"[{index}] {content[:80]}",
                        f"置信度: {confidence:.2f}",
                        "请核实该引用的准确性"
                    )
        except ImportError:
            # 回退到Semantic Scholar
            try:
                from api.paper_search import search_papers_semantic
                results = search_papers_semantic(title, limit=3)

                if not results:
                    report.add_issue(
                        "critical", "reference",
                        f"参考文献[{index}]无法检索到匹配论文，可能是编造的",
                        f"[{index}] {content[:80]}",
                        f"搜索标题: {title}, 无匹配结果",
                        "请替换为真实可检索的参考文献"
                    )
                else:
                    # 检查标题相似度
                    best_match = results[0]
                    best_title = best_match.get("title", "")
                    if not self._titles_similar(best_title, content):
                        report.add_issue(
                            "warning", "reference",
                            f"参考文献[{index}]的最优匹配标题不一致，可能引用了错误论文",
                            f"[{index}] {content[:80]}",
                            f"搜索到的最相关论文: {best_title}",
                            "请核实引用是否指向了正确的论文"
                        )
            except Exception as e:
                # 搜索失败不标记为critical，因为可能是API问题
                logger.debug(f"参考文献[{index}]搜索验证失败: {e}")

    def _titles_similar(self, title1: str, title2: str) -> bool:
        """检查两个标题是否相似"""
        if not title1 or not title2:
            return False
        words1 = set(title1.lower().split())
        words2 = set(title2.lower().split())
        if not words1:
            return False
        overlap = len(words1 & words2) / len(words1)
        return overlap > 0.4

    # ========== 内容真实性校验 ==========

    def _audit_factuality(self, report: AuditReport, chapter_name: str,
                          content: str, project_data: Dict = None):
        """
        内容真实性校验

        检查论文中的具体声明是否与项目数据一致：
        - 数据集声明：是否使用了项目中实际使用的数据集
        - 指标声明：提到的指标是否与实验设计一致
        - 模型声明：描述的模型结构是否与代码分析结果一致
        - 方法声明：描述的方法是否与创新点一致
        """
        if not project_data:
            return

        # 检查数据集声明
        exp_design = project_data.get("experiment_design", {})
        datasets = exp_design.get("数据集", [])
        if datasets and chapter_name in ("Experiments", "Methodology"):
            for ds in datasets:
                ds_name = ds.get("名称", "") if isinstance(ds, dict) else str(ds)
                if ds_name and ds_name.lower() not in content.lower():
                    report.add_issue(
                        "warning", "factuality",
                        f"数据集 '{ds_name}' 在项目代码中被使用但未在章节中提及",
                        chapter_name,
                        f"项目分析发现数据集: {ds_name}",
                        f"在实验章节中补充对 {ds_name} 的描述"
                    )

        # 检查模型结构一致性
        model_arch = project_data.get("model_architecture", {})
        modules = model_arch.get("模块详情", [])
        if modules and chapter_name == "Methodology":
            for mod in modules:
                mod_name = mod.get("模块名", "")
                if mod_name and mod_name.lower() not in content.lower():
                    report.add_issue(
                        "warning", "factuality",
                        f"模型模块 '{mod_name}' 在代码分析中被识别但未在方法论中描述",
                        chapter_name,
                        f"代码分析发现模块: {mod_name}",
                        f"在方法论中补充对 {mod_name} 的详细描述"
                    )

        # 检查指标声明一致性
        metrics = exp_design.get("评估指标", [])
        if metrics and chapter_name == "Experiments":
            for metric in metrics:
                metric_name = metric if isinstance(metric, str) else metric.get("名称", "")
                if metric_name and metric_name.lower() not in content.lower():
                    report.add_issue(
                        "info", "factuality",
                        f"评估指标 '{metric_name}' 在项目分析中被识别但未在实验章节中提及",
                        chapter_name,
                        f"项目分析发现指标: {metric_name}",
                        f"在实验章节中补充对 {metric_name} 的评估结果"
                    )

        # 检查虚假数值声明（如"我们的方法达到了XX%"等过于具体的声明）
        self._check_specific_claims(report, chapter_name, content, project_data)

    def _check_specific_claims(self, report: AuditReport, chapter_name: str,
                               content: str, project_data: Dict = None):
        """
        检查过于具体的数值声明是否可能是幻觉

        检查维度：
        1. "achieve/obtain XX%" 类声明是否有项目数据支撑
        2. Markdown 表格中的数值是否来自真实实验
        3. "Ours" 行的数据是否与 PROJECT_BRIEF 中的目标完全一致（可能是编造）
        """
        # 检查 1: 句子级数值声明
        claim_pattern = r'(?:achieve|obtain|reach|attain|score|perform)[^.]*?(\d+\.?\d*)\s*%'
        claims = re.findall(claim_pattern, content, re.IGNORECASE)

        if claims and chapter_name == "Experiments":
            key_results = (project_data or {}).get("experiment_design", {}).get("关键结果", {})
            if not key_results:
                for match_val in claims[:3]:
                    report.add_issue(
                        "critical", "factuality",
                        f"检测到具体数值声明（{match_val}%），但项目数据中无对应实验结果",
                        chapter_name,
                        "项目代码分析未发现实验结果数据，但论文中包含具体指标数值",
                        "请确保数值来自真实实验，而非LLM编造。如果实验尚未运行，请使用占位符如'X.XX'"
                    )
                return

        # 检查 2: 表格数值幻觉检测
        if chapter_name == "Experiments":
            # 提取 Markdown 表格中的数值
            table_rows = re.findall(r'\|(.+)\|', content)
            our_values = []
            for row in table_rows:
                cells = [c.strip() for c in row.split('|')]
                if any('ours' in c.lower() for c in cells):
                    # 提取 "Ours" 行中的数值
                    nums = re.findall(r'(\d+\.\d+)', row)
                    our_values.extend(nums)

            if our_values:
                key_results = (project_data or {}).get("experiment_design", {}).get("关键结果", {})
                if not key_results:
                    report.add_issue(
                        "critical", "factuality",
                        f"Experiments 表格中 'Ours' 行包含 {len(our_values)} 个数值（如 {our_values[:3]}），"
                        f"但项目数据中无任何实验结果",
                        "Experiments tables",
                        f"检测到数值: {our_values[:5]}",
                        "如果实验未运行，所有表格数值应使用占位符 'X.XX'"
                    )
                else:
                    # 检查数值是否与 PROJECT_BRIEF 中的"目标"完全一致（说明是从 brief 抄来的）
                    brief_str = json.dumps(key_results, ensure_ascii=False)
                    copied_count = sum(1 for v in our_values if v in brief_str)
                    if copied_count == len(our_values) and len(our_values) > 2:
                        report.add_issue(
                            "warning", "factuality",
                            "Experiments 中 'Ours' 的所有数值与 PROJECT_BRIEF 中的目标值完全一致，"
                            "可能并非来自真实实验运行",
                            "Experiments tables",
                            f"所有 {len(our_values)} 个数值均在 BRIEF 中找到",
                            "建议实际运行实验获取真实数据，或使用占位符"
                        )

    # ========== 内部一致性检查 ==========

    def _audit_consistency(self, report: AuditReport, chapter_name: str,
                           content: str, project_data: Dict = None):
        """
        内部一致性检查

        - 引用标记和参考文献列表是否对应
        - 前后文数据/方法描述是否一致
        - 术语使用是否一致
        """
        # 检查 citation 标记格式一致性
        citation_tags = re.findall(r'<citation>(.*?)</citation>', content, re.DOTALL)
        for tag in citation_tags:
            try:
                import ast
                parsed = ast.literal_eval(tag.strip())
                if not isinstance(parsed, list):
                    report.add_issue(
                        "warning", "consistency",
                        f"<citation>标记格式不正确，应为嵌套列表格式: {tag[:50]}",
                        "",
                        f"标记内容: {tag[:80]}",
                        "修正为 [['keyword1', 'keyword2'], ['keyword3']] 格式"
                    )
            except (ValueError, SyntaxError):
                report.add_issue(
                    "warning", "consistency",
                    f"<citation>标记无法解析: {tag[:50]}",
                    "",
                    f"标记内容: {tag[:80]}",
                    "修正为标准嵌套列表格式"
                )

        # 检查数字引用的连续性
        numeric_refs = [int(n) for n in re.findall(r'\[(\d+)\]', content)]
        if numeric_refs:
            ref_section = ""
            markers = ["# References", "## References"]
            for marker in markers:
                idx = content.find(marker)
                if idx != -1:
                    ref_section = content[idx:]
                    break

            if ref_section:
                defined_refs = [int(n) for n in re.findall(r'\[(\d+)\]', ref_section)]
                # 正文中引用了但参考文献列表中没有
                missing = set(numeric_refs) - set(defined_refs)
                if missing:
                    report.add_issue(
                        "warning", "consistency",
                        f"正文中引用了 [{', '.join(map(str, sorted(missing)))}] 但参考文献列表中未定义",
                        chapter_name,
                        f"引用但未定义: {sorted(missing)}",
                        "在参考文献列表中补充缺失的条目"
                    )

    # ========== 摘要 vs 正文一致性审计 ==========

    def _audit_abstract_vs_chapters(self, report: AuditReport,
                                     abstract: str, chapters: Dict[int, str],
                                     project_data: Dict = None):
        """检查摘要中的声明是否与正文内容一致"""
        # 使用LLM进行交叉验证
        chapter_summary = ""
        for num in sorted(chapters.keys()):
            content = chapters[num][:500]
            chapter_summary += f"Chapter {num}:\n{content}...\n\n"

        prompt = f"""你是一名学术论文审计专家。请检查以下论文摘要中的声明是否与正文内容一致。

**摘要**：
{abstract[:2000]}

**正文摘要**：
{chapter_summary[:3000]}

请检查：
1. 摘要中提到的数据集、方法、指标是否在正文中也有描述
2. 摘要中的关键数值声明是否与正文一致
3. 摘要中是否有正文未提及的内容

以json格式给出审计结果：
{{
  "consistent_claims": ["一致的声明1", "一致的声明2"],
  "inconsistent_claims": [
    {{"claim": "摘要中的声明", "issue": "问题描述"}}
  ],
  "unsupported_claims": [
    {{"claim": "摘要中无支撑的声明", "suggestion": "建议"}}
  ]
}}

回复以```json开头，以```结尾。"""

        try:
            response = self.api_client.call_reasoning(prompt)
            result = self.api_client.parse_json_response(response, default={})

            if isinstance(result, dict):
                for ic in result.get("inconsistent_claims", []):
                    report.add_issue(
                        "critical", "consistency",
                        f"摘要与正文不一致: {ic.get('claim', '')}",
                        "Abstract",
                        ic.get("issue", ""),
                        "修正摘要或正文使之一致"
                    )
                for uc in result.get("unsupported_claims", []):
                    report.add_issue(
                        "warning", "factuality",
                        f"摘要中有无正文支撑的声明: {uc.get('claim', '')}",
                        "Abstract",
                        "摘要中提到但正文中未详细论述",
                        uc.get("suggestion", "在正文中补充支撑内容")
                    )
        except Exception as e:
            logger.debug(f"摘要-正文一致性审计LLM调用失败: {e}")

    # ========== 全局审计报告 ==========

    def get_all_reports(self) -> List[Dict]:
        """获取所有审计报告"""
        return [r.to_dict() for r in self._reports]

    def get_summary_report(self) -> Dict:
        """获取审计汇总报告"""
        all_issues = []
        for r in self._reports:
            all_issues.extend(r.issues)

        return {
            "total_phases_audited": len(self._reports),
            "total_issues": len(all_issues),
            "critical_issues": sum(1 for i in all_issues if i.severity == "critical"),
            "warning_issues": sum(1 for i in all_issues if i.severity == "warning"),
            "info_issues": sum(1 for i in all_issues if i.severity == "info"),
            "overall_passed": all(r.passed for r in self._reports),
            "phase_results": {
                r.phase_name: {"passed": r.passed, "issue_count": len(r.issues)}
                for r in self._reports
            },
            "verified_references": len(self._verified_refs),
            "all_critical": [
                {
                    "phase": r.phase_name,
                    "category": i.category,
                    "description": i.description,
                    "location": i.location,
                    "suggestion": i.suggestion,
                }
                for r in self._reports for i in r.issues if i.severity == "critical"
            ],
        }

    def save_reports(self, output_dir: str = None):
        """保存审计报告到文件（原子写入，防止多进程并发损坏）"""
        import tempfile

        output_dir = output_dir or OUTPUT_DIR
        os.makedirs(output_dir, exist_ok=True)

        reports = {
            "audit_detail.json": self.get_all_reports(),
            "audit_summary.json": self.get_summary_report(),
        }

        for filename, data in reports.items():
            filepath = os.path.join(output_dir, filename)
            try:
                # 使用临时文件 + 原子重命名，避免并发写入损坏
                fd, tmp_path = tempfile.mkstemp(
                    suffix=".tmp", prefix=filename.replace('.', '_'), dir=output_dir
                )
                try:
                    with os.fdopen(fd, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    os.replace(tmp_path, filepath)
                except Exception:
                    os.unlink(tmp_path)
                    raise
            except Exception as e:
                logger.error(f"保存审计报告 {filename} 失败: {e}")

        print(f"[auditor] 审计报告已保存至 {output_dir}/audit_*.json")
