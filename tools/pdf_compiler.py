# -*- coding: utf-8 -*-
"""
Tool: PDF 编译器

从 Markdown / LaTeX 生成 PDF。

方案优先级：
1. XeLaTeX — 最高质量（需系统安装 texlive-xetex）
2. Pandoc  — 从 Markdown 直接生成（需系统安装 pandoc + texlive）
3. fpdf2   — 纯 Python fallback（无外部依赖）
"""

import os
import re
import json
import shutil
import logging
import subprocess
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


class PDFCompiler:
    """PDF 编译器 — 多引擎自动选择"""

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        self.latex_dir = os.path.join(output_dir, "latex")
        self._engine = self._detect_engine()

    # texlive 已知安装路径
    _TEXLIVE_CANDIDATES = [
        "/usr/local/texlive/2026/bin/x86_64-linux",
        "/usr/local/texlive/2025/bin/x86_64-linux",
        "/usr/local/texlive/2024/bin/x86_64-linux",
        "/usr/local/texlive/bin/x86_64-linux",
    ]

    @classmethod
    def _find_tex_binary(cls, name: str) -> Optional[str]:
        """在 PATH 和已知 texlive 路径中搜索二进制"""
        # 1. 系统 PATH
        found = shutil.which(name)
        if found:
            return found
        # 2. texlive 已知路径
        for base in cls._TEXLIVE_CANDIDATES:
            candidate = os.path.join(base, name)
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
        # 3. glob 搜索 /usr/local/texlive/*/bin/*/
        import glob
        for match in glob.glob(f"/usr/local/texlive/*/bin/*/{name}"):
            if os.access(match, os.X_OK):
                return match
        return None

    def _detect_engine(self) -> str:
        """检测可用的编译引擎"""
        # 尝试 xelatex
        if self._find_tex_binary("xelatex"):
            logger.info("[PDFCompiler] 使用 XeLaTeX 引擎")
            return "xelatex"
        # 尝试 pdflatex
        if self._find_tex_binary("pdflatex"):
            logger.info("[PDFCompiler] 使用 PDFLaTeX 引擎")
            return "pdflatex"
        # 尝试 pandoc
        if shutil.which("pandoc"):
            logger.info("[PDFCompiler] 使用 Pandoc 引擎")
            return "pandoc"
        # fallback 到 fpdf2
        logger.info("[PDFCompiler] 使用 fpdf2 (纯 Python)")
        return "fpdf2"

    def compile_pdf(self) -> Dict:
        """
        编译 PDF — 自动选择最佳引擎

        Returns:
            {
                "pdf_path": str,
                "engine": str,
                "success": bool,
                "pages": int,
                "error": str|None,
            }
        """
        os.makedirs(self.output_dir, exist_ok=True)
        pdf_path = os.path.join(self.output_dir, "full_paper.pdf")

        if self._engine in ("xelatex", "pdflatex"):
            result = self._compile_latex()
        elif self._engine == "pandoc":
            result = self._compile_pandoc()
        else:
            result = self._compile_fpdf2()

        # 如果主引擎失败，尝试 fpdf2 降级
        if not result.get("success") and self._engine != "fpdf2":
            logger.warning(f"[PDFCompiler] {self._engine} 失败，降级到 fpdf2")
            result = self._compile_fpdf2()

        return result

    def _compile_latex(self) -> Dict:
        """XeLaTeX / PDFLaTeX 编译"""
        tex_path = os.path.join(self.latex_dir, "main.tex")
        if not os.path.exists(tex_path):
            return {"success": False, "error": f"main.tex 不存在: {tex_path}"}

        pdf_path = os.path.join(self.output_dir, "full_paper.pdf")
        engine_name = self._engine  # xelatex or pdflatex
        engine_bin = self._find_tex_binary(engine_name)
        if not engine_bin:
            return {"success": False, "engine": engine_name,
                    "error": f"找不到 {engine_name} 二进制"}

        bibtex_bin = self._find_tex_binary("bibtex")

        try:
            env = os.environ.copy()
            # 确保 texlive 路径在 PATH 中
            texlive_dir = os.path.dirname(engine_bin)
            env["PATH"] = texlive_dir + os.pathsep + env.get("PATH", "")

            # 第一遍编译（在 latex 目录下运行，不指定 output-directory）
            r1 = subprocess.run(
                [engine_bin, "-interaction=nonstopmode", "main.tex"],
                capture_output=True, text=True, timeout=180,
                cwd=self.latex_dir, env=env,
            )

            # 运行 BibTeX（如果 .bib 存在）
            if bibtex_bin and os.path.exists(os.path.join(self.latex_dir, "references.bib")):
                bibtex_env = env.copy()
                bibtex_dir = os.path.dirname(bibtex_bin)
                bibtex_env["PATH"] = bibtex_dir + os.pathsep + bibtex_env.get("PATH", "")
                subprocess.run(
                    [bibtex_bin, "main"],
                    capture_output=True, text=True, timeout=60,
                    cwd=self.latex_dir, env=bibtex_env,
                )

            # 第二遍编译（解决交叉引用 + 引用编号）
            r2 = subprocess.run(
                [engine_bin, "-interaction=nonstopmode", "main.tex"],
                capture_output=True, text=True, timeout=180,
                cwd=self.latex_dir, env=env,
            )

            # 第三遍编译（确保引用和页码稳定）
            subprocess.run(
                [engine_bin, "-interaction=nonstopmode", "main.tex"],
                capture_output=True, text=True, timeout=180,
                cwd=self.latex_dir, env=env,
            )

            # 检查是否生成了 PDF
            compiled_pdf = os.path.join(self.latex_dir, "main.pdf")
            if not os.path.exists(compiled_pdf):
                # 尝试解析错误
                log_content = r1.stdout + r1.stderr
                if os.path.exists(os.path.join(self.latex_dir, "main.log")):
                    with open(os.path.join(self.latex_dir, "main.log"), "r",
                              encoding="utf-8", errors="ignore") as lf:
                        log_content = lf.read()
                errors = self._parse_latex_errors(log_content)

                # v15.2: LLM 编译修复兜底（1 轮 — 逐章验证已排除大部分错误）
                logger.warning(f"[PDFCompiler] 全量编译失败, 尝试 LLM 修复 (1 轮)")
                try:
                    tex_path = os.path.join(self.latex_dir, "main.tex")
                    with open(tex_path, "r", encoding="utf-8") as f:
                        current_tex = f.read()

                    from tools.latex_converter import _fix_compile_errors
                    fixed_tex = _fix_compile_errors(current_tex, errors)

                    if fixed_tex != current_tex:
                        with open(tex_path, "w", encoding="utf-8") as f:
                            f.write(fixed_tex)

                        # 重编译 3 遍
                        for _ in range(3):
                            subprocess.run(
                                [engine_bin, "-interaction=nonstopmode", "main.tex"],
                                capture_output=True, text=True, timeout=180,
                                cwd=self.latex_dir, env=env,
                            )

                        if os.path.exists(compiled_pdf):
                            logger.info("[PDFCompiler] LLM 修复后编译成功")
                        else:
                            # 更新错误信息
                            if os.path.exists(os.path.join(self.latex_dir, "main.log")):
                                with open(os.path.join(self.latex_dir, "main.log"), "r",
                                          encoding="utf-8", errors="ignore") as lf:
                                    log_content = lf.read()
                                errors = self._parse_latex_errors(log_content)
                            return {"success": False, "engine": engine_name,
                                    "error": f"编译失败 (LLM修复后仍失败): {errors[:800]}"}
                    else:
                        logger.warning("[PDFCompiler] LLM 未做出修改")
                        return {"success": False, "engine": engine_name,
                                "error": f"编译失败: {errors[:800]}"}
                except Exception as fix_err:
                    logger.warning(f"[PDFCompiler] LLM 修复异常: {fix_err}")
                    return {"success": False, "engine": engine_name,
                            "error": f"编译失败: {errors[:800]}"}

            # 复制到目标路径
            shutil.copy2(compiled_pdf, pdf_path)

            pages = self._count_pdf_pages(pdf_path)
            logger.info(f"[PDFCompiler] LaTeX 编译成功: {pdf_path} ({pages} 页)")

            return {
                "success": True, "pdf_path": pdf_path,
                "engine": engine_name, "pages": pages,
            }

        except subprocess.TimeoutExpired:
            return {"success": False, "engine": engine_name, "error": "编译超时 (180s)"}
        except Exception as e:
            return {"success": False, "engine": engine_name, "error": str(e)}

    def _compile_pandoc(self) -> Dict:
        """Pandoc 快速通道"""
        md_path = os.path.join(self.output_dir, "full_paper.md")
        pdf_path = os.path.join(self.output_dir, "full_paper.pdf")

        if not os.path.exists(md_path):
            return {"success": False, "error": f"Markdown 不存在: {md_path}"}

        try:
            r = subprocess.run(
                ["pandoc", md_path, "-o", pdf_path,
                 "--pdf-engine=xelatex",
                 "-V", "geometry:margin=1in",
                 "-V", "classoption=journal"],
                capture_output=True, text=True, timeout=120,
            )

            if r.returncode != 0:
                return {"success": False, "engine": "pandoc",
                        "error": r.stderr[:500]}

            pages = self._count_pdf_pages(pdf_path)
            return {
                "success": True, "pdf_path": pdf_path,
                "engine": "pandoc", "pages": pages,
            }

        except Exception as e:
            return {"success": False, "engine": "pandoc", "error": str(e)}

    def _compile_fpdf2(self) -> Dict:
        """
        纯 Python PDF 生成 (fpdf2)

        从 Markdown 读取内容，用 fpdf2 渲染为 PDF。
        支持标题、段落、粗体/斜体、公式占位。
        """
        md_path = os.path.join(self.output_dir, "full_paper.md")
        pdf_path = os.path.join(self.output_dir, "full_paper.pdf")

        if not os.path.exists(md_path):
            return {"success": False, "error": f"Markdown 不存在: {md_path}"}

        try:
            from fpdf import FPDF

            with open(md_path, "r", encoding="utf-8") as f:
                md_content = f.read()

            pdf = FPDF()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.set_left_margin(15)
            pdf.set_right_margin(15)
            pdf.add_page()
            # 设置 Unicode 支持
            pdf.set_font("helvetica", "", 9)

            # 尝试使用内置中文字体（如果 fpdf2 支持的话）
            try:
                pdf.add_font("helvetica", "", uni=True)
            except Exception:
                pass

            lines = md_content.split("\n")
            i = 0
            pages = 1

            while i < len(lines):
                line = lines[i].strip()

                if not line:
                    i += 1
                    continue

                try:
                    # 标题
                    if line.startswith("# ") and not line.startswith("## "):
                        title = line[2:].strip()
                        title = re.sub(r'\*\*(.+?)\*\*', r'\1', title)
                        title = self._safe_text(title)
                        pdf.set_font("helvetica", "B", 14)
                        pdf.multi_cell(0, 7, title)
                        pdf.ln(3)
                    elif line.startswith("## "):
                        heading = line[3:].strip()
                        heading = re.sub(r'\*\*(.+?)\*\*', r'\1', heading)
                        heading = self._safe_text(heading)
                        pdf.set_font("helvetica", "B", 12)
                        pdf.multi_cell(0, 6, heading)
                        pdf.ln(2)
                    elif line.startswith("### "):
                        heading = line[4:].strip()
                        heading = re.sub(r'\*\*(.+?)\*\*', r'\1', heading)
                        heading = self._safe_text(heading)
                        pdf.set_font("helvetica", "B", 10)
                        pdf.multi_cell(0, 5, heading)
                        pdf.ln(2)
                    elif line.startswith("|"):
                        # 表格行 — 跳过分隔行
                        cells = [c.strip() for c in line.split("|") if c.strip()]
                        if cells and not all(set(c) <= set("-: ") for c in cells):
                            truncated = [c[:25] for c in cells]
                            row_text = " | ".join(truncated)
                            row_text = self._safe_text(row_text)
                            pdf.set_font("helvetica", "", 7)
                            pdf.cell(0, 4, row_text, ln=True)
                    elif line.startswith("$$"):
                        # 显示公式
                        formula_lines = []
                        if "$$" in line[2:]:
                            end_match = re.search(r'\$\$(.*?)\$\$', line, re.DOTALL)
                            if end_match:
                                formula_lines.append(end_match.group(1).strip())
                        else:
                            formula_lines.append(line.replace("$$", "").strip())
                            i += 1
                            while i < len(lines):
                                fl = lines[i].strip()
                                if "$$" in fl:
                                    formula_lines.append(fl.replace("$$", "").strip())
                                    break
                                formula_lines.append(fl)
                                i += 1
                        formula_text = self._safe_text(" ".join(formula_lines).strip())
                        if formula_text:
                            pdf.set_font("courier", "", 8)
                            pdf.cell(0, 5, f"  {formula_text[:100]}", ln=True)
                        pdf.ln(1)
                    else:
                        # 普通段落
                        para_lines = [line]
                        i += 1
                        while i < len(lines) and lines[i].strip() and not lines[i].startswith("#"):
                            para_lines.append(lines[i].strip())
                            i += 1

                        text = " ".join(para_lines)
                        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
                        text = re.sub(r'\*(.+?)\*', r'\1', text)
                        text = re.sub(r'\$([^$]+)\$', r'\1', text)
                        text = self._safe_text(text)

                        pdf.set_font("helvetica", "", 9)
                        pdf.multi_cell(0, 5, text)
                        pdf.ln(2)
                        continue
                except Exception:
                    pass  # 跳过无法渲染的行

                i += 1

            pdf.output(pdf_path)
            pages = pdf.pages_count
            logger.info(f"[PDFCompiler] fpdf2 生成成功: {pdf_path} ({pages} 页)")

            return {
                "success": True, "pdf_path": pdf_path,
                "engine": "fpdf2", "pages": pages,
            }

        except Exception as e:
            logger.error(f"[PDFCompiler] fpdf2 生成失败: {e}")
            return {"success": False, "engine": "fpdf2", "error": str(e)}

    @staticmethod
    def _safe_text(text: str) -> str:
        """清理文本中 fpdf2 无法渲染的字符"""
        # 移除控制字符和非 Latin-1 字符
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
        # 将常见非 ASCII 字符替换
        replacements = {
            '\u2019': "'", '\u2018': "'",
            '\u201c': '"', '\u201d': '"',
            '\u2013': '-', '\u2014': '--',
            '\u2026': '...', '\u00b7': '.',
            '\u2264': '<=', '\u2265': '>=',
            '\u2260': '!=', '\u2192': '->',
            '\u00d7': 'x', '\u00f7': '/',
            '\u03b1': 'alpha', '\u03b2': 'beta',
            '\u03b3': 'gamma', '\u03b4': 'delta',
            '\u03b8': 'theta', '\u03bb': 'lambda',
            '\u03c3': 'sigma', '\u03c9': 'omega',
            '\u03b5': 'epsilon', '\u03c0': 'pi',
        }
        for char, replacement in replacements.items():
            text = text.replace(char, replacement)
        # 移除剩余的非 Latin-1 字符
        text = text.encode('latin-1', errors='replace').decode('latin-1')
        return text

    def _parse_latex_errors(self, log_text: str) -> str:
        """解析 LaTeX 编译日志中的错误"""
        errors = []
        for line in log_text.split("\n"):
            if line.startswith("!"):
                errors.append(line)
        return "\n".join(errors[:10]) if errors else log_text[:500]

    def _count_pdf_pages(self, pdf_path: str) -> int:
        """统计 PDF 页数"""
        # 方法1: 从编译日志获取
        log_path = pdf_path.replace("full_paper.pdf", "latex/main.log")
        if not os.path.exists(log_path):
            log_path = pdf_path.replace(".pdf", ".log")
        if os.path.exists(log_path):
            try:
                with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                    log_content = f.read()
                match = re.search(r'Output written.*\((\d+)\s+pages?', log_content)
                if match:
                    return int(match.group(1))
            except Exception:
                pass
        # 方法2: PDF 文本解析
        try:
            with open(pdf_path, "rb") as f:
                content = f.read()
            count_match = re.search(rb'/Count\s+(\d+)', content)
            if count_match:
                return int(count_match.group(1))
            count = content.count(b"/Type /Page")
            pages_count = content.count(b"/Type /Pages")
            pages = max(count - pages_count, 1)
            return pages
        except Exception:
            return 0


def run_pdf_compiler(output_dir: str) -> Dict:
    """PDF 编译入口函数"""
    compiler = PDFCompiler(output_dir)
    return compiler.compile_pdf()
