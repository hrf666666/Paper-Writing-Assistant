# -*- coding: utf-8 -*-
"""
Tool: PDF 编译验证器 v3.0

Phase 8.5: PDF 编译验证器
- 实际编译验证（调用 pdf_compiler）
- 解析 LaTeX 编译日志（warnings/errors）
- PDF 视觉结构检查（页数、空白页、文本覆盖率）
- 关键元素渲染验证（引用、表格、图片、公式）
- 规则驱动的结构修复（括号平衡、环境嵌套、数学模式边界）
- LLM 分批辅助修复（仅处理规则无法修复的复杂问题）
- 验证失败时触发修复循环（最多 3 次）

v3.0 改进：
1. 规则驱动修复：括号平衡分析、环境嵌套验证、数学模式边界检查
2. 编译日志去重：消除级联错误（一个根因产生多个报错）
3. LLM 分批修复：每批 10 个问题，仅发送错误上下文
4. 结构化验证：检查返回内容是否为有效 LaTeX（而非长度比较）
"""

import os
import re
import json
import logging
from typing import Dict, List, Optional, Tuple
from collections import Counter

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# 错误分类与去重规则（v3.0 规则驱动）
# ═══════════════════════════════════════════════════════════════

# 级联错误模式：以下错误类型通常是另一个根因的连锁反应，不独立计
CASCADE_SECONDARY = {
    "Missing \\cr inserted.": "cr_error",
    "Misplaced \\cr.": "cr_error",
    "Missing } inserted.": "brace_error",
    "Missing { inserted.": "brace_error",
    "Missing $ inserted.": "dollar_error",
    "Extra }, or forgotten $.": "dollar_error",
    "Improper \\spacefactor.": "spacefactor_error",
    "You can't use `\\spacefactor' in math mode.": "spacefactor_error",
    "You can't use `\\spacefactor' in display math mode.": "spacefactor_error",
    "LaTeX Error: Command \\bfseries invalid in math mode.": "spacefactor_error",
    "You can't use `\\eqno' in math mode.": "eqno_error",
}

# 每个根因组最多保留的错误数
CASCADE_GROUP_LIMITS = {
    "cr_error": 3,
    "brace_error": 3,
    "dollar_error": 3,
    "spacefactor_error": 2,
    "eqno_error": 2,
}


class PDFValidator:
    """PDF 编译验证器 v3.0"""

    def __init__(self, output_dir: str, api_client=None):
        self.output_dir = output_dir
        self.latex_dir = os.path.join(output_dir, "latex")
        self.api_client = api_client
        self.max_retries = 3

    def run_validation(self, max_retries: int = 3) -> Dict:
        """
        主验证循环：约束预检 → 编译 → 验证 → 修复 → 重新编译
        """
        self.max_retries = max_retries
        report = {
            "passed": False,
            "compile_log_issues": [],
            "pdf_structure": {},
            "element_validation": {},
            "auto_fix_attempts": {"total_issues": 0, "fixed": 0, "remaining": 0},
            "constraint_audit": {},
            "retry_count": 0,
        }

        # ── Phase 8.5-pre: 约束预检（编译前检查结构合规） ──
        tex_path = os.path.join(self.latex_dir, "main.tex")
        if os.path.exists(tex_path):
            try:
                with open(tex_path, "r", encoding="utf-8") as f:
                    tex_content = f.read()

                from tools.latex_constraint_checker import run_constraint_check
                constraint_result = run_constraint_check(
                    tex_content, template_type="ieee_trans", auto_fix=True
                )
                report["constraint_audit"] = {
                    "critical": constraint_result["critical_count"],
                    "warnings": constraint_result["warning_count"],
                    "passed": constraint_result["all_passed"],
                    "violations": constraint_result["violations"],
                }

                if not constraint_result["all_passed"]:
                    # 写回修复后的内容
                    with open(tex_path, "w", encoding="utf-8") as f:
                        f.write(constraint_result["fixed_content"])
                    logger.info(
                        f"[Phase 8.5-pre] 约束预检修复: "
                        f"{constraint_result['critical_count']} critical, "
                        f"{constraint_result['warning_count']} warnings"
                    )
                else:
                    logger.info("[Phase 8.5-pre] 约束预检通过")
            except Exception as e:
                logger.warning(f"[Phase 8.5-pre] 约束预检失败（不阻塞）: {e}")

        for retry in range(max_retries + 1):
            logger.info(f"[Phase 8.5] 验证循环 {retry + 1}/{max_retries + 1}")

            # 1. 编译 PDF
            compile_result = self._compile_pdf()
            if not compile_result.get("success"):
                report["compile_log_issues"].append({
                    "type": "compilation_failed",
                    "severity": "critical",
                    "message": compile_result.get("error", "Unknown error"),
                    "suggestion": "编译失败，需检查 .tex 语法",
                })
                break

            # 2. 解析编译日志（带去重）
            log_issues = self._parse_compile_log()
            report["compile_log_issues"] = log_issues

            # 3. 验证 PDF 结构
            pdf_path = compile_result.get("pdf_path", "")
            pdf_structure = self._validate_pdf_structure(pdf_path)
            report["pdf_structure"] = pdf_structure

            # 4. 验证关键元素
            tex_path = os.path.join(self.latex_dir, "main.tex")
            bib_path = os.path.join(self.latex_dir, "references.bib")
            element_validation = self._validate_elements(tex_path, bib_path, pdf_path)
            report["element_validation"] = element_validation

            # 5. 评估是否通过
            critical_issues = [
                issue for issue in log_issues
                if issue.get("severity") == "critical"
            ]
            if not critical_issues and pdf_structure.get("valid", False):
                report["passed"] = True
                logger.info("[Phase 8.5] 验证通过")
                break

            # 6. 尝试自动修复
            if retry < max_retries:
                fix_report = self._auto_fix(log_issues, tex_path, bib_path)
                report["auto_fix_attempts"]["total_issues"] += fix_report.get("total_issues", 0)
                report["auto_fix_attempts"]["fixed"] += fix_report.get("fixed", 0)
                report["retry_count"] = retry + 1

                if fix_report.get("fixed", 0) == 0:
                    logger.warning("[Phase 8.5] 无问题可修复，停止重试")
                    break
            else:
                logger.warning(f"[Phase 8.5] 达到最大重试次数 {max_retries}")
                break

        report["auto_fix_attempts"]["remaining"] = (
            report["auto_fix_attempts"]["total_issues"] -
            report["auto_fix_attempts"]["fixed"]
        )

        # 保存验证报告
        report_path = os.path.join(self.output_dir, "pdf_validation_report.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        return report

    def _compile_pdf(self) -> Dict:
        """调用 pdf_compiler 编译 PDF"""
        try:
            from tools.pdf_compiler import run_pdf_compiler
            return run_pdf_compiler(self.output_dir)
        except Exception as e:
            logger.error(f"[Phase 8.5] 编译异常: {e}")
            return {"success": False, "error": str(e)}

    # ═══════════════════════════════════════════════════════════
    # 编译日志解析（v3.0：带级联去重）
    # ═══════════════════════════════════════════════════════════

    def _parse_compile_log(self) -> List[Dict]:
        """
        解析 LaTeX 编译日志，提取 warnings/errors 并去重级联错误。
        """
        log_path = os.path.join(self.latex_dir, "main.log")
        if not os.path.exists(log_path):
            logger.warning("[Phase 8.5] 编译日志不存在")
            return []

        try:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                log_content = f.read()
        except Exception as e:
            logger.error(f"[Phase 8.5] 读取编译日志失败: {e}")
            return []

        raw_issues = []

        # 1. Overfull \hbox
        for width, line in re.findall(
            r'Overfull \\hbox \(([^)]+)\) in (?:paragraph at|lines) (\d+)', log_content
        ):
            raw_issues.append({
                "type": "overfull_hbox", "severity": "warning",
                "line": int(line),
                "message": f"Overfull \\hbox ({width}) at line {line}",
                "suggestion": "添加 \\resizebox 或调整列宽",
            })

        # 2. Overfull \vbox
        for height, line in re.findall(
            r'Overfull \\vbox \(([^)]+)\) detected at line (\d+)', log_content
        ):
            raw_issues.append({
                "type": "overfull_vbox", "severity": "warning",
                "line": int(line),
                "message": f"Overfull \\vbox ({height}) at line {line}",
                "suggestion": "调整页面边距或使用 \\pagebreak",
            })

        # 3. Reference undefined
        for ref in re.findall(r"LaTeX Warning: Reference `([^']+)' undefined", log_content):
            raw_issues.append({
                "type": "undefined_reference", "severity": "critical",
                "message": f"Reference '{ref}' undefined",
                "suggestion": f"检查 \\label{{{ref}}} 是否存在",
            })

        # 4. Citation undefined
        all_undefined_cites = list(set(
            re.findall(r"LaTeX Warning: Citation `([^']+)' undefined", log_content) +
            re.findall(r"I didn't find a database entry for \"([^\"]+)\"", log_content)
        ))
        for cite in all_undefined_cites:
            raw_issues.append({
                "type": "undefined_citation", "severity": "critical",
                "message": f"Citation '{cite}' undefined",
                "suggestion": f".bib 中缺少条目 '{cite}'",
            })

        # 5. File not found
        all_missing_files = list(set(
            re.findall(r"LaTeX Warning: File `([^']+)' not found", log_content) +
            re.findall(r"! Package graphicx Error: File `([^']+)' not found", log_content)
        ))
        for filepath in all_missing_files:
            raw_issues.append({
                "type": "file_not_found", "severity": "critical",
                "message": f"File '{filepath}' not found",
                "suggestion": f"检查路径或替换为占位符",
            })

        # 6. LaTeX Errors — 按行号收集，用于去重
        error_lines = re.finditer(r'^! (.+?)(?:\n|$)', log_content, re.MULTILINE)
        for m in error_lines:
            error_msg = m.group(1).strip()
            if any(kw in error_msg.lower() for kw in [
                "overfull", "underfull", "reference", "citation", "file"
            ]):
                continue
            raw_issues.append({
                "type": "latex_error", "severity": "critical",
                "message": f"LaTeX Error: {error_msg}",
                "suggestion": "需检查 .tex 语法",
            })

        # 7. Package warnings
        for package, warning in re.findall(
            r'Package (\w+) Warning: (.+?)(?:\n|\. )', log_content
        ):
            raw_issues.append({
                "type": "package_warning", "severity": "warning",
                "message": f"Package {package} Warning: {warning}",
                "suggestion": f"检查 {package} 包配置",
            })

        # 8. 编译状态
        compile_success = "Output written" in log_content
        error_count = log_content.count("! ")
        if not compile_success or error_count > 0:
            raw_issues.append({
                "type": "compilation_status",
                "severity": "critical" if error_count > 0 else "warning",
                "message": f"编译 {'失败' if error_count > 0 else '有警告'}: {error_count} errors",
                "suggestion": "检查编译日志中的错误信息",
            })

        # ── 去重级联错误 ──
        deduped = self._deduplicate_cascade_errors(raw_issues)
        logger.info(f"[Phase 8.5] 解析编译日志: {len(raw_issues)} → {len(deduped)} 个问题 (去重后)")
        return deduped

    def _deduplicate_cascade_errors(self, issues: List[Dict]) -> List[Dict]:
        """
        规则驱动的级联错误去重。

        原理：LaTeX 中一个根因错误（如未闭合的 math mode）
        会产生大量连锁报错（Missing $, Extra }, \spacefactor 等）。
        这些属于同一根因组，只保留代表样本。
        """
        group_counts = Counter()
        result = []
        non_cascade = []

        for issue in issues:
            msg = issue.get("message", "")
            cascade_group = None
            for pattern, group in CASCADE_SECONDARY.items():
                if pattern in msg:
                    cascade_group = group
                    break

            if cascade_group:
                group_counts[cascade_group] += 1
                limit = CASCADE_GROUP_LIMITS.get(cascade_group, 3)
                if group_counts[cascade_group] <= limit:
                    # 标注为级联错误，但保留前几个样本
                    issue["_cascade_group"] = cascade_group
                    issue["_cascade_total"] = None  # 后面填充
                    non_cascade.append(issue)
                # 超出限额的直接丢弃
            else:
                non_cascade.append(issue)

        # 回填级联总数
        for issue in non_cascade:
            if "_cascade_group" in issue:
                issue["_cascade_total"] = group_counts[issue["_cascade_group"]]
                # 添加备注
                issue["message"] += f" (级联错误，共 {issue['_cascade_total']} 个同类)"

        return non_cascade

    # ═══════════════════════════════════════════════════════════
    # PDF 结构验证
    # ═══════════════════════════════════════════════════════════

    def _validate_pdf_structure(self, pdf_path: str) -> Dict:
        """验证 PDF 视觉结构"""
        result = {"valid": False, "pages": 0, "blank_pages": [], "text_coverage": 0.0}

        if not os.path.exists(pdf_path):
            logger.warning("[Phase 8.5] PDF 文件不存在")
            return result

        try:
            import fitz  # PyMuPDF
            doc = fitz.open(pdf_path)
            result["pages"] = len(doc)

            if len(doc) < 5:
                result["pages_too_few"] = True
                logger.warning(f"[Phase 8.5] PDF 页数过少: {len(doc)} 页")
            elif len(doc) > 30:
                result["pages_too_many"] = True

            blank_pages = []
            total_text_area = 0
            total_page_area = 0
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_area = page.rect.width * page.rect.height
                total_page_area += page_area
                text = page.get_text()
                text_area = len(text.strip()) * 10
                if text_area < page_area * 0.05:
                    blank_pages.append(page_num + 1)
                total_text_area += text_area

            result["blank_pages"] = blank_pages
            result["text_coverage"] = total_text_area / total_page_area if total_page_area > 0 else 0.0
            doc.close()

            result["valid"] = (
                5 <= result["pages"] <= 30
                and not blank_pages
                and result["text_coverage"] > 0.3
            )
            logger.info(
                f"[Phase 8.5] PDF 结构: {result['pages']} 页, "
                f"空白页: {blank_pages}, 覆盖率: {result['text_coverage']:.2%}"
            )
        except ImportError:
            logger.warning("[Phase 8.5] PyMuPDF 未安装，使用基础检查")
            result = self._basic_pdf_check(pdf_path)
        except Exception as e:
            logger.error(f"[Phase 8.5] PDF 结构验证失败: {e}")
            result = self._basic_pdf_check(pdf_path)

        return result

    def _basic_pdf_check(self, pdf_path: str) -> Dict:
        """基础 PDF 检查（不依赖 PyMuPDF）"""
        result = {"valid": False, "pages": 0, "blank_pages": [], "text_coverage": 0.0}
        try:
            with open(pdf_path, "rb") as f:
                content = f.read()
            page_count = content.count(b"/Type /Page") - content.count(b"/Type /Pages")
            result["pages"] = max(page_count, 1)
            file_size = os.path.getsize(pdf_path)
            result["file_size_kb"] = round(file_size / 1024, 1)
            result["valid"] = file_size > 100 * 1024 and result["pages"] >= 5
        except Exception as e:
            logger.error(f"[Phase 8.5] 基础 PDF 检查失败: {e}")
        return result

    # ═══════════════════════════════════════════════════════════
    # 元素验证
    # ═══════════════════════════════════════════════════════════

    def _validate_elements(self, tex_path: str, bib_path: str, pdf_path: str) -> Dict:
        """验证关键元素渲染完整性"""
        result = {
            "citations_match": True,
            "missing_citations": [],
            "tables_rendered": 0,
            "tables_truncated": 0,
            "figures_rendered": 0,
            "figures_missing": 0,
            "formulas_count": 0,
            "formula_numbering_ok": True,
        }

        if not os.path.exists(tex_path):
            return result

        try:
            with open(tex_path, "r", encoding="utf-8") as f:
                tex_content = f.read()

            # 引用匹配
            cites_in_tex = set()
            for match in re.finditer(r'\\cite[^\{]*\{([^}]+)\}', tex_content):
                cites_in_tex.update(k.strip() for k in match.group(1).split(","))

            result["citations_in_tex"] = len(cites_in_tex)

            if os.path.exists(bib_path):
                with open(bib_path, "r", encoding="utf-8") as f:
                    bib_content = f.read()
                bib_entries = set(
                    m.group(1) for m in re.finditer(r'@\w+\{([^,\s]+)', bib_content)
                )
                result["citations_in_bib"] = len(bib_entries)
                missing = cites_in_tex - bib_entries
                if missing:
                    result["citations_match"] = False
                    result["missing_citations"] = list(missing)
                    logger.warning(f"[Phase 8.5] 引用缺失: {len(missing)} 个")

            # 表格
            result["tables_rendered"] = len(re.findall(r'\\begin\{table', tex_content))
            result["tables_truncated"] = len(re.findall(
                r'TABLE_CAPTION|\\caption\{\[TODO\]\}', tex_content
            ))

            # 图片
            result["figures_rendered"] = len(re.findall(r'\\begin\{figure', tex_content))
            figure_paths = re.findall(r'\\includegraphics[^\{]*\{([^}]+)\}', tex_content)
            missing_figs = 0
            for fig_path in figure_paths:
                if not os.path.exists(os.path.join(self.output_dir, fig_path)):
                    if not os.path.exists(os.path.join(self.latex_dir, fig_path)):
                        missing_figs += 1
            result["figures_missing"] = missing_figs

            # 公式
            eq_count = len(re.findall(r'\\begin\{equation\}', tex_content))
            align_count = len(re.findall(r'\\begin\{align\}', tex_content))
            result["formulas_count"] = eq_count + align_count
            result["formula_labels"] = len(re.findall(r'\\label\{([^}]+)\}', tex_content))

        except Exception as e:
            logger.error(f"[Phase 8.5] 元素验证失败: {e}")

        logger.info(
            f"[Phase 8.5] 元素验证: "
            f"引用 {result.get('citations_in_tex', 0)}/{result.get('citations_in_bib', 0)}, "
            f"表格 {result['tables_rendered']}, "
            f"图片 {result['figures_rendered']}, "
            f"公式 {result['formulas_count']}"
        )
        return result

    # ═══════════════════════════════════════════════════════════
    # 规则驱动的结构分析（v3.0 核心）
    # ═══════════════════════════════════════════════════════════

    def _analyze_tex_structure(self, tex_content: str) -> Dict:
        """
        分析 .tex 文件的结构完整性。

        通过规则检查：
        1. 括号平衡（{ } 配对）
        2. 数学模式边界（$ 配对，equation/align 配对）
        3. 环境嵌套（\begin/\end 配对）
        4. tabular 行尾（\\ 配对）

        Returns:
            {
                "brace_balance": {"line": int, "depth": int},  # 不平衡的括号
                "math_mode_issues": [...],  # 数学模式边界问题
                "env_nesting_issues": [...],  # 环境嵌套问题
                "table_issues": [...],  # 表格结构问题
                "total_issues": int,
            }
        """
        analysis = {
            "brace_balance": [],
            "math_mode_issues": [],
            "env_nesting_issues": [],
            "table_issues": [],
            "total_issues": 0,
        }

        lines = tex_content.split('\n')

        # ── 1. 逐行括号平衡分析 ──
        brace_depth = 0
        for i, line in enumerate(lines, 1):
            # 跳过注释行
            stripped = line.split('%')[0] if '%' in line else line
            for ch in stripped:
                if ch == '{':
                    brace_depth += 1
                elif ch == '}':
                    brace_depth -= 1
                # 括号深度不应为负（除非在特殊环境中）
                if brace_depth < 0:
                    analysis["brace_balance"].append({
                        "line": i, "depth": brace_depth,
                        "hint": "多余的 } 在此行",
                    })
                    brace_depth = 0  # 重置以继续分析

        if brace_depth > 0:
            analysis["brace_balance"].append({
                "line": len(lines), "depth": brace_depth,
                "hint": f"文件末尾缺少 {brace_depth} 个 }}",
            })

        # ── 2. 环境嵌套分析 ──
        env_stack = []
        begin_pattern = re.compile(r'\\begin\{([^}]+)\}')
        end_pattern = re.compile(r'\\end\{([^}]+)\}')

        for i, line in enumerate(lines, 1):
            for m in begin_pattern.finditer(line):
                env_name = m.group(1)
                env_stack.append((env_name, i))

            for m in end_pattern.finditer(line):
                env_name = m.group(1)
                if env_stack and env_stack[-1][0] == env_name:
                    env_stack.pop()
                elif env_stack:
                    # 嵌套不匹配
                    analysis["env_nesting_issues"].append({
                        "line": i,
                        "expected": env_stack[-1][0],
                        "found": env_name,
                        "hint": f"期望 \\end{{{env_stack[-1][0]}}}，但找到 \\end{{{env_name}}}",
                    })
                    # 尝试恢复：弹出栈顶
                    env_stack.pop()
                else:
                    analysis["env_nesting_issues"].append({
                        "line": i,
                        "expected": None,
                        "found": env_name,
                        "hint": f"多余的 \\end{{{env_name}}}，无对应 \\begin",
                    })

        for env_name, line_no in env_stack:
            analysis["env_nesting_issues"].append({
                "line": line_no,
                "expected": env_name,
                "found": None,
                "hint": f"\\begin{{{env_name}}} 在第 {line_no} 行未闭合",
            })

        # ── 3. 数学模式边界分析 ──
        in_math = False
        math_start_line = 0
        for i, line in enumerate(lines, 1):
            stripped = line.split('%')[0] if '%' in line else line
            # 统计行内 $ 符号（排除 $$）
            dollar_count = 0
            j = 0
            while j < len(stripped):
                if stripped[j] == '$':
                    if j + 1 < len(stripped) and stripped[j + 1] == '$':
                        j += 2  # 跳过 $$
                    else:
                        dollar_count += 1
                        j += 1
                else:
                    j += 1

            # 奇数个 $ 意味着数学模式切换
            if dollar_count % 2 == 1:
                if not in_math:
                    in_math = True
                    math_start_line = i
                else:
                    in_math = False

        if in_math:
            analysis["math_mode_issues"].append({
                "line": math_start_line,
                "hint": f"从第 {math_start_line} 行开始的 $ 未闭合",
            })

        # ── 4. 表格结构分析 ──
        in_tabular = False
        tabular_start = 0
        tabular_col_spec = ""
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if re.match(r'\\begin\{tabular', stripped):
                in_tabular = True
                tabular_start = i
                # 提取列规格
                col_match = re.search(r'\{([^}]+)\}', stripped)
                if col_match:
                    tabular_col_spec = col_match.group(1)
            elif re.match(r'\\end\{tabular', stripped):
                in_tabular = False
            elif in_tabular and '\\\\' in stripped and tabular_col_spec:
                # 计算列数（简单统计 & 分隔符）
                col_count = tabular_col_spec.count('l') + tabular_col_spec.count('c') + \
                            tabular_col_spec.count('r') + tabular_col_spec.count('p')
                if col_count > 0:
                    # 统计行中 & 的数量
                    # 排除数学模式中的 &
                    row_content = stripped.split('\\\\')[0]
                    amp_count = row_content.count('&')
                    if amp_count != col_count - 1 and amp_count > 0:
                        analysis["table_issues"].append({
                            "line": i,
                            "hint": f"第 {i} 行: 列数不匹配 (声明 {col_count} 列, 实际 {amp_count + 1} 列)",
                        })

        analysis["total_issues"] = (
            len(analysis["brace_balance"]) +
            len(analysis["math_mode_issues"]) +
            len(analysis["env_nesting_issues"]) +
            len(analysis["table_issues"])
        )

        return analysis

    # ═══════════════════════════════════════════════════════════
    # 自动修复（v3.0：规则驱动 + LLM 分批）
    # ═══════════════════════════════════════════════════════════

    def _auto_fix(self, issues: List[Dict], tex_path: str, bib_path: str) -> Dict:
        """
        自动修复：规则驱动（结构分析）+ LLM 分批辅助。
        """
        fix_report = {
            "total_issues": len(issues),
            "fixed": 0,
            "fixed_by_rule": 0,
            "fixed_by_llm": 0,
            "fixes_applied": [],
        }

        if not os.path.exists(tex_path):
            return fix_report

        try:
            with open(tex_path, "r", encoding="utf-8") as f:
                tex_content = f.read()

            original_content = tex_content

            # ── 第一步：结构分析驱动的规则修复 ──
            structure = self._analyze_tex_structure(tex_content)

            # 修复 1: 环境嵌套不匹配
            for issue in structure["env_nesting_issues"]:
                if issue.get("found") is None and issue.get("expected"):
                    # 缺少 \end{X}
                    env_name = issue["expected"]
                    tex_content += f'\n\\end{{{env_name}}}'
                    fix_report["fixed"] += 1
                    fix_report["fixed_by_rule"] += 1
                    fix_report["fixes_applied"].append(
                        f"Rule: 补充缺失的 \\end{{{env_name}}} (第 {issue['line']} 行)"
                    )

                elif issue.get("expected") is None and issue.get("found"):
                    # 多余的 \end{X}，删除该行
                    env_name = issue["found"]
                    lines = tex_content.split('\n')
                    line_idx = issue["line"] - 1
                    if 0 <= line_idx < len(lines):
                        old_line = lines[line_idx]
                        if f'\\end{{{env_name}}}' in old_line:
                            lines[line_idx] = re.sub(
                                r'\s*\\end\{' + re.escape(env_name) + r'\}\s*', '', old_line
                            )
                            tex_content = '\n'.join(lines)
                            fix_report["fixed"] += 1
                            fix_report["fixed_by_rule"] += 1
                            fix_report["fixes_applied"].append(
                                f"Rule: 移除多余的 \\end{{{env_name}}} (第 {issue['line']} 行)"
                            )

            # 修复 2: 引用缺失 → 添加占位符到 .bib
            for issue in issues:
                if issue.get("type") == "undefined_citation":
                    match = re.search(r"Citation '([^']+)' undefined", issue.get("message", ""))
                    if match and os.path.exists(bib_path):
                        cite_key = match.group(1)
                        with open(bib_path, "a", encoding="utf-8") as f:
                            f.write(f"\n@misc{{{cite_key},\n")
                            f.write(f"  title = {{Placeholder for {cite_key}}},\n")
                            f.write(f"  author = {{Unknown}},\n")
                            f.write(f"  year = {{2026}},\n")
                            f.write(f"  note = {{Auto-generated placeholder}}\n")
                            f.write(f"}}\n")
                        fix_report["fixed"] += 1
                        fix_report["fixed_by_rule"] += 1
                        fix_report["fixes_applied"].append(f"Rule: 添加引用占位符 {cite_key}")

            # 修复 3: 图片缺失 → 替换 includegraphics 为占位符
            for issue in issues:
                if issue.get("type") == "file_not_found":
                    match = re.search(r"File '([^']+)' not found", issue.get("message", ""))
                    if match:
                        filepath = match.group(1)
                        if filepath.endswith((".png", ".jpg", ".jpeg", ".pdf", ".eps")):
                            placeholder = (
                                f"\\fbox{{\\parbox{{0.8\\linewidth}}{{\\centering "
                                f"[Placeholder: {filepath}]}}}}"
                            )
                            pattern = (
                                re.escape("\\includegraphics") +
                                r"[^\{]*\{" + re.escape(filepath) + r"\}"
                            )
                            tex_content = re.sub(pattern, placeholder, tex_content)
                            fix_report["fixed"] += 1
                            fix_report["fixed_by_rule"] += 1
                            fix_report["fixes_applied"].append(f"Rule: 替换缺失图片 {filepath}")

            # ── 第二步：LLM 分批修复剩余的复杂问题 ──
            remaining_issues = [
                issue for issue in issues
                if issue.get("severity") == "critical"
                and issue.get("type") == "latex_error"
                and not issue.get("_cascade_group")  # 跳过纯级联错误
            ]

            if remaining_issues and self.api_client:
                llm_result = self._llm_batch_fix(remaining_issues, tex_content)
                if llm_result.get("success"):
                    tex_content = llm_result["fixed_content"]
                    llm_fixed = llm_result.get("fixes_count", 0)
                    fix_report["fixed"] += llm_fixed
                    fix_report["fixed_by_llm"] += llm_fixed
                    fix_report["fixes_applied"].append(
                        f"LLM: 修复 {llm_fixed} 个复杂问题"
                    )

            # 写回文件
            if tex_content != original_content:
                with open(tex_path, "w", encoding="utf-8") as f:
                    f.write(tex_content)
                logger.info(
                    f"[Phase 8.5] 修复完成: {fix_report['fixed']} 个 "
                    f"(规则 {fix_report['fixed_by_rule']}, LLM {fix_report['fixed_by_llm']})"
                )

        except Exception as e:
            logger.error(f"[Phase 8.5] 自动修复失败: {e}")

        return fix_report

    def _llm_batch_fix(
        self,
        issues: List[Dict],
        tex_content: str,
        batch_size: int = 10,
    ) -> Dict:
        """
        LLM 分批修复：每次只发送错误上下文（错误行前后 10 行），而非完整 .tex。

        Returns:
            {"success": bool, "fixed_content": str, "fixes_count": int, "error": str}
        """
        if not self.api_client:
            return {"success": False, "error": "No API client"}

        lines = tex_content.split('\n')
        context_radius = 10  # 取错误行前后 10 行

        # 分批处理
        all_fixed = False
        fixed_count = 0
        current_content = tex_content

        for batch_start in range(0, len(issues), batch_size):
            batch = issues[batch_start:batch_start + batch_size]

            # 为每个错误提取上下文
            error_contexts = []
            affected_line_ranges = set()

            for issue in batch:
                msg = issue.get("message", "")
                # 尝试从错误消息中提取行号
                line_match = re.search(r'(?:line |at line |lines )(\d+)', msg)
                if line_match:
                    line_no = int(line_match.group(1))
                    start = max(0, line_no - 1 - context_radius)
                    end = min(len(lines), line_no + context_radius)
                    context = '\n'.join(
                        f"{j+1}: {lines[j]}" for j in range(start, end)
                    )
                    error_contexts.append({
                        "message": msg,
                        "context": context,
                        "line_range": (start, end),
                    })
                    affected_line_ranges.add((start, end))

            if not error_contexts:
                continue

            # 构建 prompt：只发送错误上下文
            prompt_parts = [
                "你是 LaTeX 修复专家。以下是需要修复的编译错误及其上下文。\n",
                "要求：\n",
                "1. 只修复语法错误，不修改学术内容\n",
                "2. 保持原有结构和格式\n",
                "3. 返回修复后的 **完整** .tex 文件\n\n",
                f"## 错误列表（{len(error_contexts)} 个）：\n\n",
            ]
            for i, ctx in enumerate(error_contexts, 1):
                prompt_parts.append(f"### 错误 {i}:\n")
                prompt_parts.append(f"错误信息: {ctx['message']}\n")
                prompt_parts.append(f"上下文:\n```latex\n{ctx['context']}\n```\n\n")

            # 限制总 prompt 长度
            prompt = ''.join(prompt_parts)
            if len(prompt) > 8000:
                prompt = prompt[:8000] + "\n\n(截断)"

            prompt += f"\n## 完整 .tex 文件（修复后返回）:\n\n{current_content}"

            # 限制总长度
            if len(prompt) > 30000:
                prompt = prompt[:30000]

            try:
                response = self.api_client.call_light(prompt)
                fixed_content = response.strip()

                # 结构化验证（而非长度比较）
                if self._is_valid_latex_response(fixed_content, current_content):
                    current_content = fixed_content
                    fixed_count += len(error_contexts)
                    all_fixed = True
                else:
                    logger.warning(
                        f"[Phase 8.5] LLM 批次 {batch_start // batch_size + 1} 修复结果无效"
                    )
            except Exception as e:
                logger.error(f"[Phase 8.5] LLM 批次修复调用失败: {e}")

        if all_fixed:
            return {
                "success": True,
                "fixed_content": current_content,
                "fixes_count": fixed_count,
            }
        return {"success": False, "error": "All LLM batches failed validation"}

    def _is_valid_latex_response(self, response: str, original: str) -> bool:
        """
        规则驱动的响应验证：检查 LLM 返回是否为有效的 LaTeX 修复。

        规则：
        1. 必须包含 \begin{document} 和 \end{document}
        2. 长度不应小于原文的 30%（防止返回空壳）
        3. 不应包含 LLM 自言自语（如 "Here is the fixed..."）
        """
        if not response:
            return False

        # 规则 1: 必须有完整的文档结构
        has_begin_doc = '\\begin{document}' in response
        has_end_doc = '\\end{document}' in response
        if not (has_begin_doc and has_end_doc):
            return False

        # 规则 2: 长度阈值
        if len(response) < len(original) * 0.3:
            return False

        # 规则 3: 过滤 LLM 自言自语
        chat_patterns = [
            r'^Here is', r'^I have fixed', r'^Below is',
            r'^The fixed', r'^Here are the', r'^Sure[,!]',
            r'^```', r'^I\'ll fix',
        ]
        first_line = response.split('\n')[0].strip()
        for pattern in chat_patterns:
            if re.match(pattern, first_line, re.IGNORECASE):
                return False

        return True


def run_pdf_validator(output_dir: str, api_client=None, max_retries: int = 3) -> Dict:
    """PDF 验证器入口函数"""
    validator = PDFValidator(output_dir, api_client)
    return validator.run_validation(max_retries)
