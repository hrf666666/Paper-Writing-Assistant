# -*- coding: utf-8 -*-
"""
声明式 LaTeX 约束引擎 v1.0

设计原则：
  - 每条规则解决一类问题（而非一个具体问题）
  - 规则声明"什么是合法的"，check() 发现违规，fix() 自动修复
  - LLM 生成内容不可控 → 用确定性规则兜底

5 条规则 → 10 类已知问题：

  ASCIITextConstraint        → TikZ中文乱码、非ASCII渲染空白
  EnvironmentConstraint      → \\textbf{Table} 嵌入正文、环境不闭合
  TemplateComplianceConstraint → IEEEPARstart缺失、手动章节编号、双栏缺失
  UniquenessConstraint       → caption/label重复、表格内容重复
  SizeConstraint             → 表格溢出、p{0.13}过窄列
  AbbreviationConstraint    → 缩写重复(EPI)(EPI)、全大写伪标题
"""

import re
import hashlib
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Tuple
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════════

class Violation:
    """约束违规记录"""

    def __init__(self, rule: str, severity: str, description: str,
                 location: str = "", fix_hint: str = ""):
        self.rule = rule            # 规则名
        self.severity = severity    # "critical" | "warning"
        self.description = description
        self.location = location    # 如 "line 42" 或 "\\node{...}"
        self.fix_hint = fix_hint

    def __repr__(self):
        return f"[{self.severity.upper()}] {self.rule}: {self.description}"


# ═══════════════════════════════════════════════════════════════
# 规则基类
# ═══════════════════════════════════════════════════════════════

class Constraint(ABC):
    """约束规则基类：声明什么合法，发现违规并修复"""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def check(self, tex_content: str, template_type: str = "ieee_trans") -> List[Violation]:
        """检查 tex 内容，返回违规列表"""
        ...

    def fix(self, tex_content: str, violations: List[Violation]) -> str:
        """根据违规列表自动修复，返回修复后的内容"""
        return tex_content  # 默认不做修复


# ═══════════════════════════════════════════════════════════════
# 规则 1: ASCII 文本约束
# 解决: TikZ 中文乱码、非 ASCII 字符渲染空白
# ═══════════════════════════════════════════════════════════════

class ASCIITextConstraint(Constraint):
    """
    所有 tikzpicture 环境中的节点标签和注释必须为纯 ASCII。
    通解：不管 LLM 用什么语言输出 TikZ，强制转为 ASCII。
    """

    @property
    def name(self): return "ASCII Text"

    def check(self, tex_content: str, template_type: str = "ieee_trans") -> List[Violation]:
        violations = []
        # 找所有 tikzpicture 环境
        for m in re.finditer(
            r'\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}',
            tex_content, re.DOTALL
        ):
            tikz_block = m.group(0)
            # 在 \node{} 和注释中查找非 ASCII
            non_ascii_positions = []
            for i, ch in enumerate(tikz_block):
                if ord(ch) > 127:
                    non_ascii_positions.append((i, ch))

            if non_ascii_positions:
                # 获取上下文
                pos, ch = non_ascii_positions[0]
                ctx_start = max(0, pos - 30)
                ctx_end = min(len(tikz_block), pos + 30)
                context = tikz_block[ctx_start:ctx_end].replace('\n', ' ')
                violations.append(Violation(
                    rule=self.name,
                    severity="critical",
                    description=f"TikZ 中发现 {len(non_ascii_positions)} 个非 ASCII 字符",
                    location=context[:80],
                    fix_hint="将自动 transliterate 为 ASCII",
                ))
        return violations

    def fix(self, tex_content: str, violations: List[Violation]) -> str:
        if not violations:
            return tex_content

        def _transliterate_tikz(match):
            """将 tikzpicture 中的非 ASCII 字符 transliterate"""
            tikz_block = match.group(0)
            result = []
            i = 0
            while i < len(tikz_block):
                ch = tikz_block[i]
                if ord(ch) <= 127:
                    result.append(ch)
                else:
                    # 尝试 transliterate
                    ascii_equiv = self._to_ascii(ch)
                    result.append(ascii_equiv)
                i += 1
            return ''.join(result)

        result = re.sub(
            r'\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}',
            _transliterate_tikz, tex_content, flags=re.DOTALL
        )

        fixed_count = sum(1 for v in violations if v.rule == self.name)
        if result != tex_content:
            logger.info(f"[Constraint:ASCII] 修复了 {fixed_count} 个 TikZ 非ASCII问题")

        return result

    @staticmethod
    def _to_ascii(ch: str) -> str:
        """Unicode → ASCII transliterate（常见学术字符映射）"""
        # 常见中文标点
        mappings = {
            '（': '(', '）': ')', '：': ':', '，': ',', '。': '.',
            '；': ';', '！': '!', '？': '?', '"': '"', '"': '"',
            '—': '-', '–': '-', '…': '...', '·': '.',
            '〈': '<', '〉': '>', '《': '"', '》': '"',
            '【': '[', '】': ']', '｛': '{', '｝': '}',
        }
        if ch in mappings:
            return mappings[ch]
        # CJK 字符 → 空格（TikZ 标签中中文无意义）
        if 0x4E00 <= ord(ch) <= 0x9FFF:
            return ''
        # 其他非 ASCII → 尝试 unicodedata normalize
        try:
            import unicodedata
            normalized = unicodedata.normalize('NFKD', ch)
            ascii_chars = [c for c in normalized if ord(c) < 128]
            if ascii_chars:
                return ''.join(ascii_chars)
        except Exception:
            pass
        return ''


# ═══════════════════════════════════════════════════════════════
# 规则 2: 环境完整性约束
# 解决: \textbf{Table I:...} 嵌入正文、环境未正确包裹
# ═══════════════════════════════════════════════════════════════

class EnvironmentConstraint(Constraint):
    """
    每个表格/图必须使用正确的 LaTeX 环境包裹。
    通解：检测"伪环境"（\textbf{Table}、\textbf{Figure} 等）并转为正规环境。
    """

    # 匹配伪表格：\textbf{Table I: Caption...} 或 \textbf{TABLE I} 或 \textbf{TABLE II}
    PSEUDO_TABLE_RE = re.compile(
        r'\\textbf\{(Table\s+[\dIVX]+[\.:]?\s*[^}]*?)\}',
        re.IGNORECASE
    )
    PSEUDO_FIGURE_RE = re.compile(
        r'\\textbf\{(Figure\s+[\dIVX]+[\.:]?\s*[^}]*?)\}',
        re.IGNORECASE
    )

    @property
    def name(self): return "Environment Integrity"

    def check(self, tex_content: str, template_type: str = "ieee_trans") -> List[Violation]:
        violations = []
        lines = tex_content.split('\n')

        # 预计算每行的起始偏移量，避免 find() 在重复行时返回错误位置
        line_offsets = []
        offset = 0
        for line in lines:
            line_offsets.append(offset)
            offset += len(line) + 1  # +1 for '\n'

        # 检测伪表格
        for i, line in enumerate(lines):
            for m in self.PSEUDO_TABLE_RE.finditer(line):
                # 检查是否已在 table 环境内
                preceding = tex_content[:line_offsets[i]]
                open_tables = preceding.count(r'\begin{table')
                close_tables = preceding.count(r'\end{table')
                if open_tables <= close_tables:
                    violations.append(Violation(
                        rule=self.name,
                        severity="critical",
                        description=f"伪表格标题 '{m.group(1)[:50]}' 未在 \\begin{{table}} 环境内",
                        location=f"line {i + 1}",
                        fix_hint="将自动包裹为 \\begin{table} 环境",
                    ))

            for m in self.PSEUDO_FIGURE_RE.finditer(line):
                preceding = tex_content[:line_offsets[i]]
                open_figs = preceding.count(r'\begin{figure')
                close_figs = preceding.count(r'\end{figure')
                if open_figs <= close_figs:
                    violations.append(Violation(
                        rule=self.name,
                        severity="critical",
                        description=f"伪图片标题 '{m.group(1)[:50]}' 未在 \\begin{{figure}} 环境内",
                        location=f"line {i + 1}",
                        fix_hint="将自动包裹为 \\begin{figure} 环境",
                    ))

        return violations

    def fix(self, tex_content: str, violations: List[Violation]) -> str:
        if not violations:
            return tex_content

        lines = tex_content.split('\n')
        fixed_lines = []
        env_stack = []  # 跟踪当前环境嵌套

        for i, line in enumerate(lines, 1):
            # 跟踪环境嵌套
            for m in re.finditer(r'\\begin\{(\w+\*?)\}', line):
                env_stack.append(m.group(1))
            for m in re.finditer(r'\\end\{(\w+\*?)\}', line):
                if env_stack and env_stack[-1] == m.group(1):
                    env_stack.pop()

            in_table = any('table' in e.lower() for e in env_stack)
            in_figure = any('figure' in e.lower() for e in env_stack)

            # 修复伪表格
            if not in_table:
                table_match = self.PSEUDO_TABLE_RE.search(line)
                if table_match:
                    caption_text = table_match.group(1)
                    # 提取编号和说明
                    cap_match = re.match(
                        r'Table\s+([\dIVX]+)[\.:]\s*(.+)', caption_text, re.IGNORECASE
                    )
                    if cap_match:
                        table_num = cap_match.group(1)
                        caption_content = cap_match.group(2).strip()
                        label = f"tab:table{table_num}"
                        # 替换伪标题为正规环境（包含闭合 \end{table}）
                        new_line = line.replace(
                            table_match.group(0),
                            f'\\begin{{table}}[!t]\n\\caption{{{caption_content}}}\n\\label{{{label}}}'
                        )
                        # 在后续最近的空行或下一节标题前关闭环境
                        # 向后查找插入 \end{table} 的位置
                        close_inserted = False
                        for j in range(i, len(lines)):
                            if j > i and (lines[j].strip() == '' or re.match(r'\\(section|subsection|subsubsection)', lines[j].strip())):
                                # 在此行之前插入 \end{table}
                                fixed_lines.append(new_line)
                                # 补上中间可能遗漏的行
                                for k in range(i, j):
                                    if k > i - 1 and k < len(lines):
                                        # 跳过已经处理的当前行，直接找后续行
                                        pass
                                fixed_lines.append('\\end{table}')
                                close_inserted = True
                                break
                        if not close_inserted:
                            fixed_lines.append(new_line)
                            fixed_lines.append('\\end{table}')
                        continue

            # 修复伪图片
            if not in_figure:
                fig_match = self.PSEUDO_FIGURE_RE.search(line)
                if fig_match:
                    caption_text = fig_match.group(1)
                    cap_match = re.match(
                        r'Figure\s+([\dIVX]+)[\.:]\s*(.+)', caption_text, re.IGNORECASE
                    )
                    if cap_match:
                        fig_num = cap_match.group(1)
                        caption_content = cap_match.group(2).strip()
                        label = f"fig:figure{fig_num}"
                        new_line = line.replace(
                            fig_match.group(0),
                            f'\\begin{{figure}}[!t]\n\\caption{{{caption_content}}}\n\\label{{{label}}}'
                        )
                        # 查找插入 \end{figure} 的位置
                        close_inserted = False
                        for j in range(i, len(lines)):
                            if j > i and (lines[j].strip() == '' or re.match(r'\\(section|subsection|subsubsection)', lines[j].strip())):
                                fixed_lines.append(new_line)
                                fixed_lines.append('\\end{figure}')
                                close_inserted = True
                                break
                        if not close_inserted:
                            fixed_lines.append(new_line)
                            fixed_lines.append('\\end{figure}')
                        continue

            fixed_lines.append(line)

        result = '\n'.join(fixed_lines)
        if result != tex_content:
            logger.info(f"[Constraint:Environment] 修复了 {len(violations)} 个伪环境问题")

        return result


# ═══════════════════════════════════════════════════════════════
# 规则 3: 模板合规约束
# 解决: IEEEPARstart缺失、手动章节编号、双栏检测
# ═══════════════════════════════════════════════════════════════

class TemplateComplianceConstraint(Constraint):
    """
    对标 IEEE 模板的结构要求。
    通解：检查文档是否符合选定模板的结构规范，自动修复常见偏差。
    """

    @property
    def name(self): return "Template Compliance"

    def check(self, tex_content: str, template_type: str = "ieee_trans") -> List[Violation]:
        violations = []

        if template_type == "ieee_trans":
            # 检查 1: IEEEPARstart
            if '\\IEEEPARstart' not in tex_content:
                # 检查是否有 Introduction section
                if re.search(r'\\section\{.*Introduction', tex_content, re.IGNORECASE):
                    violations.append(Violation(
                        rule=self.name,
                        severity="warning",
                        description="IEEE 模板要求使用 \\IEEEPARstart 首字母放大",
                        location="Introduction section",
                        fix_hint="在 Introduction 第一段前自动插入 \\IEEEPARstart",
                    ))

            # 检查 2: 手动章节编号 \section{4. Experiments} 或 \section{1. Introduction}
            manual_nums = re.findall(
                r'\\(section|subsection|subsubsection)\{(\d+\.?\d*\s+[^}]+)\}',
                tex_content
            )
            for cmd, title in manual_nums:
                violations.append(Violation(
                    rule=self.name,
                    severity="critical",
                    description=f"手动章节编号: \\{cmd}{{{title}}}",
                    location=f"\\{cmd}{{{title[:40]}}}",
                    fix_hint="将自动移除手动编号前缀",
                ))

            # 检查 3: 双栏文档类
            if 'IEEEtran' not in tex_content:
                violations.append(Violation(
                    rule=self.name,
                    severity="warning",
                    description="非 IEEEtran 文档类",
                    fix_hint="检查是否使用正确的模板",
                ))

        return violations

    def fix(self, tex_content: str, violations: List[Violation]) -> str:
        if not violations:
            return tex_content

        fixes = 0

        # 修复 1: 移除手动章节编号
        def _strip_heading_number(match):
            cmd = match.group(1)
            title = match.group(2)
            cleaned = re.sub(r'^\d+\.?\d*\s+', '', title)
            if cleaned != title:
                nonlocal fixes
                fixes += 1
            return f'\\{cmd}{{{cleaned}}}'

        tex_content = re.sub(
            r'\\(section|subsection|subsubsection|paragraph|subparagraph)\{(\d+\.?\d*\s+[^}]+)\}',
            _strip_heading_number, tex_content
        )

        # 修复 2: 注入 IEEEPARstart（对标 bare_jrnl_new_sample4.tex 格式）
        # IEEE 标准格式: \IEEEPARstart{T}{his is the first sentence...}
        # 不是包裹整个段落，而是只取第一个单词的 {首字母}{剩余字母}
        has_ieeeparstart = '\\IEEEPARstart' in tex_content
        if not has_ieeeparstart:
            intro_match = re.search(
                r'\\section\{.*?Introduction.*?\}\s*\n',
                tex_content, re.IGNORECASE
            )
            if intro_match:
                insert_pos = intro_match.end()
                after_intro = tex_content[insert_pos:insert_pos + 1000]
                # 跳过空行，找到第一段的第一个字母
                first_char_match = re.search(r'[A-Za-z]', after_intro)
                if first_char_match:
                    char_pos = insert_pos + first_char_match.start()
                    first_char = tex_content[char_pos]
                    # 找到第一个单词的结束位置（空格或标点）
                    rest_of_word = ""
                    j = char_pos + 1
                    while j < len(tex_content) and tex_content[j].isalpha():
                        rest_of_word += tex_content[j]
                        j += 1
                    # 替换: \IEEEPARstart{T}{his} + 剩余文字
                    word_end = char_pos + 1 + len(rest_of_word)
                    ieeeparstart = f'\\IEEEPARstart{{{first_char}}}{{{rest_of_word}}}'
                    tex_content = (
                        tex_content[:char_pos] +
                        ieeeparstart +
                        tex_content[word_end:]
                    )
                    fixes += 1

        if fixes > 0:
            logger.info(f"[Constraint:Template] 修复了 {fixes} 个模板合规问题")

        return tex_content


# ═══════════════════════════════════════════════════════════════
# 规则 4: 唯一性约束
# 解决: caption/label重复、表格内容重复
# ═══════════════════════════════════════════════════════════════

class UniquenessConstraint(Constraint):
    """
    所有 label、caption 必须全局唯一；表格内容不应高度重复。
    通解：检测所有重复标识符和内容，自动去重。
    """

    SIMILARITY_THRESHOLD = 0.80  # 80% 以上相似度视为重复

    @property
    def name(self): return "Uniqueness"

    def check(self, tex_content: str, template_type: str = "ieee_trans") -> List[Violation]:
        violations = []

        # 检查 1: 重复 label
        labels = re.findall(r'\\label\{([^}]+)\}', tex_content)
        label_counts = {}
        for label in labels:
            label_counts[label] = label_counts.get(label, 0) + 1
        for label, count in label_counts.items():
            if count > 1:
                violations.append(Violation(
                    rule=self.name,
                    severity="critical",
                    description=f"重复 \\label{{{label}}} 出现 {count} 次",
                    fix_hint="将自动添加后缀保证唯一性",
                ))

        # 检查 2: 重复 caption
        captions = re.findall(r'\\caption\{([^}]+)\}', tex_content)
        caption_counts = {}
        for cap in captions:
            normalized = cap.strip().lower()
            caption_counts.setdefault(normalized, []).append(cap)
        for norm_cap, originals in caption_counts.items():
            if len(originals) > 1:
                violations.append(Violation(
                    rule=self.name,
                    severity="warning",
                    description=f"重复 caption: '{norm_cap[:50]}' 出现 {len(originals)} 次",
                    fix_hint="将自动区分重复 caption",
                ))

        # 检查 3: 表格内容相似度
        tables = re.findall(
            r'\\begin\{table\*?\}.*?\\end\{table\*?\}',
            tex_content, re.DOTALL
        )
        for i in range(len(tables)):
            for j in range(i + 1, len(tables)):
                # 提取表格内容（排除 caption 和 label）
                content_i = self._extract_table_content(tables[i])
                content_j = self._extract_table_content(tables[j])
                if content_i and content_j:
                    similarity = SequenceMatcher(
                        None, content_i[:500], content_j[:500]
                    ).ratio()
                    if similarity > self.SIMILARITY_THRESHOLD:
                        violations.append(Violation(
                            rule=self.name,
                            severity="critical",
                            description=f"表格 {i+1} 和 {j+1} 内容相似度 {similarity:.0%}",
                            fix_hint=f"表格 {j+1} 可能是重复的，建议删除或合并",
                        ))

        return violations

    def fix(self, tex_content: str, violations: List[Violation]) -> str:
        if not violations:
            return tex_content

        fixes = 0

        # 修复 1: 重复 label
        label_positions = []
        for m in re.finditer(r'\\label\{([^}]+)\}', tex_content):
            label_positions.append((m.start(), m.end(), m.group(1)))

        seen_labels = {}
        for start, end, label in reversed(label_positions):  # 反向替换避免偏移
            if label in seen_labels:
                seen_labels[label] += 1
                new_label = f"{label}_{seen_labels[label]}"
                tex_content = tex_content[:start] + f'\\label{{{new_label}}}' + tex_content[end:]
                fixes += 1
            else:
                seen_labels[label] = 0

        # 修复 2: 重复 caption
        caption_positions = []
        for m in re.finditer(r'\\caption\{([^}]+)\}', tex_content):
            caption_positions.append((m.start(), m.end(), m.group(1)))

        seen_captions = {}
        for start, end, caption in reversed(caption_positions):
            norm = caption.strip().lower()
            if norm in seen_captions:
                seen_captions[norm] += 1
                idx = seen_captions[norm]
                # 在 caption 末尾添加区分后缀
                new_caption = f"{caption.rstrip('.')} ({idx + 1})."
                tex_content = tex_content[:start] + f'\\caption{{{new_caption}}}' + tex_content[end:]
                fixes += 1
            else:
                seen_captions[norm] = 0

        if fixes > 0:
            logger.info(f"[Constraint:Uniqueness] 修复了 {fixes} 个唯一性问题")

        return tex_content

    @staticmethod
    def _extract_table_content(table_tex: str) -> str:
        """提取表格的纯文本内容（不含结构命令）"""
        # 提取 tabular 环境内的内容
        tab_match = re.search(
            r'\\begin\{tabular\*?\}.*?\}(.*?)\\end\{tabular\*?\}',
            table_tex, re.DOTALL
        )
        if not tab_match:
            return ""
        content = tab_match.group(1)
        # 移除 LaTeX 命令，保留文本
        content = re.sub(r'\\[a-zA-Z]+\{[^}]*\}', '', content)
        content = re.sub(r'\\[a-zA-Z]+', '', content)
        return content.strip()


# ═══════════════════════════════════════════════════════════════
# 规则 5: 尺寸约束
# 解决: 表格溢出、p{0.13\textwidth} 过窄
# ═══════════════════════════════════════════════════════════════

class SizeConstraint(Constraint):
    """
    表格/图片尺寸必须适合页面。
    通解：检测所有尺寸问题，自动调整为合理尺寸。
    """

    # 最小列宽阈值（低于此值会溢出）
    MIN_COL_WIDTH = 0.10  # \textwidth 的 10%

    @property
    def name(self): return "Size"

    def check(self, tex_content: str, template_type: str = "ieee_trans") -> List[Violation]:
        violations = []

        # 检查 1: 过窄的 p{} 列宽
        narrow_cols = re.findall(
            r'p\{(0\.\d+)\\(?:textwidth|linewidth|columnwidth)\}',
            tex_content
        )
        for width_str in narrow_cols:
            width = float(width_str)
            if width < self.MIN_COL_WIDTH:
                violations.append(Violation(
                    rule=self.name,
                    severity="warning",
                    description=f"列宽 p{{{width_str}\\textwidth}} 过窄（< {self.MIN_COL_WIDTH:.0%}）",
                    fix_hint="将自动替换为 l 类型或适当宽度",
                ))

        # 检查 2: 多列表格缺少 resizebox
        tables = re.findall(
            r'\\begin\{table\*?\}(.*?)\\end\{table\*?\}',
            tex_content, re.DOTALL
        )
        for i, table_content in enumerate(tables, 1):
            # 提取列规格
            col_spec_match = re.search(
                r'\\begin\{tabular\*?\}\{[^}]*\}\{([^}]+)\}',
                table_content
            )
            if not col_spec_match:
                col_spec_match = re.search(
                    r'\\begin\{tabular\}\{([^}]+)\}',
                    table_content
                )
            if col_spec_match:
                col_spec = col_spec_match.group(1)
                # 简单计数列数
                col_count = sum(1 for c in col_spec if c in 'lcr')
                p_count = col_spec.count('p')
                total_cols = col_count + p_count

                if total_cols > 5:
                    has_resizebox = '\\resizebox' in table_content
                    has_table_star = '\\begin{table*}' in tex_content[
                        tex_content.find(table_content) - 100:
                        tex_content.find(table_content) + len(table_content) + 100
                    ]
                    if not has_resizebox and not has_table_star:
                        violations.append(Violation(
                            rule=self.name,
                            severity="warning",
                            description=f"表格 {i} 有 {total_cols} 列但缺少 \\resizebox 或 table*",
                            fix_hint="将自动添加 \\resizebox 或升级为 table*",
                        ))

        return violations

    def fix(self, tex_content: str, violations: List[Violation]) -> str:
        if not violations:
            return tex_content

        fixes = 0

        # 修复 1: 过窄 p{} 列宽 → 替换为 l
        def _fix_narrow_col(match):
            nonlocal fixes
            width_str = match.group(1)
            width = float(width_str)
            if width < self.MIN_COL_WIDTH:
                fixes += 1
                return 'l'
            return match.group(0)

        tex_content = re.sub(
            r'p\{(0\.\d+)\\(?:textwidth|linewidth|columnwidth)\}',
            _fix_narrow_col, tex_content
        )

        if fixes > 0:
            logger.info(f"[Constraint:Size] 修复了 {fixes} 个尺寸问题")

        return tex_content


# ═══════════════════════════════════════════════════════════════
# 约束引擎：组合所有规则
# ═══════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════
# 规则 6: 缩写规范约束
# 解决: (EPI) (EPI)、(EPI)s (EPIs)、重复定义缩写
# ═══════════════════════════════════════════════════════════════

class AbbreviationConstraint(Constraint):
    """
    缩写使用规范：首次定义后，后续直接使用缩写。
    通解：检测所有括号重复定义和复数形式重复。
    """

    # 匹配 "full name (ABBR) (ABBR)" 或 "(ABBR)s (ABBR)s"
    REPEATED_ABBR_RE = re.compile(
        r'\(([A-Z]{2,})\)\s*\(\1\)',  # (EPI) (EPI)
        re.IGNORECASE
    )
    PLURAL_DUP_RE = re.compile(
        r'\(([A-Z]{2,})\)s\s*\(\1s\)',  # (EPI)s (EPIs)
        re.IGNORECASE
    )
    # 匹配 "\textbf{TABLE I}" 或 "\textbf{TABLE II}" 全大写标题行
    TABLE_CAPS_RE = re.compile(
        r'\\textbf\{(TABLE\s+[\dIVX]+)\}',
        re.IGNORECASE
    )

    @property
    def name(self): return "Abbreviation"

    def check(self, tex_content: str, template_type: str = "ieee_trans") -> List[Violation]:
        violations = []

        # 检查 1: 重复缩写定义 (EPI) (EPI)
        for m in self.REPEATED_ABBR_RE.finditer(tex_content):
            violations.append(Violation(
                rule=self.name,
                severity="critical",
                description=f"重复缩写定义: ({m.group(1)}) ({m.group(1)})",
                location=m.group(0),
                fix_hint="移除重复的括号定义",
            ))

        # 检查 2: 复数重复 (EPI)s (EPIs)
        for m in self.PLURAL_DUP_RE.finditer(tex_content):
            violations.append(Violation(
                rule=self.name,
                severity="critical",
                description=f"重复复数缩写: ({m.group(1)})s ({m.group(1)})s",
                location=m.group(0),
                fix_hint="移除重复的复数形式",
            ))

        # 检查 3: 全大写伪表格标题
        for m in self.TABLE_CAPS_RE.finditer(tex_content):
            violations.append(Violation(
                rule=self.name,
                severity="critical",
                description=f"全大写伪标题: \\textbf{{{m.group(1)}}}",
                location=m.group(0),
                fix_hint="移除 \\textbf 伪标题行",
            ))

        return violations

    def fix(self, tex_content: str, violations: List[Violation]) -> str:
        if not violations:
            return tex_content

        fixes = 0

        # 修复 1: (EPI) (EPI) → (EPI)
        def _fix_repeated_abbr(match):
            nonlocal fixes
            fixes += 1
            return f'({match.group(1)})'

        tex_content = self.REPEATED_ABBR_RE.sub(_fix_repeated_abbr, tex_content)

        # 修复 2: (EPI)s (EPIs) → (EPI)s
        def _fix_plural_dup(match):
            nonlocal fixes
            fixes += 1
            return f'({match.group(1)})s'

        tex_content = self.PLURAL_DUP_RE.sub(_fix_plural_dup, tex_content)

        # 修复 3: 移除 \textbf{TABLE I} 全大写行（独立行的）
        def _remove_caps_table_line(line):
            nonlocal fixes
            stripped = line.strip()
            if self.TABLE_CAPS_RE.fullmatch(stripped):
                fixes += 1
                return ''  # 删除整行
            # 部分匹配（行内包含全大写表格标题）
            new_line = self.TABLE_CAPS_RE.sub('', stripped)
            if new_line != stripped:
                fixes += 1
            return new_line

        lines = tex_content.split('\n')
        cleaned_lines = []
        for line in lines:
            if self.TABLE_CAPS_RE.search(line):
                # 检查是否是独立的 TABLE 标题行
                stripped = line.strip()
                if self.TABLE_CAPS_RE.fullmatch(stripped):
                    fixes += 1
                    continue  # 跳过整行
                else:
                    # 行内移除
                    new_line = self.TABLE_CAPS_RE.sub('', line)
                    if new_line.strip():
                        cleaned_lines.append(new_line)
                    fixes += 1
            else:
                cleaned_lines.append(line)

        tex_content = '\n'.join(cleaned_lines)

        if fixes > 0:
            logger.info(f"[Constraint:Abbreviation] 修复了 {fixes} 个缩写问题")

        return tex_content


class ConstraintChecker:
    """
    约束引擎：运行所有规则，汇总违规并批量修复。
    """

    def __init__(self, template_type: str = "ieee_trans"):
        self.template_type = template_type
        self.rules: List[Constraint] = [
            ASCIITextConstraint(),
            EnvironmentConstraint(),
            TemplateComplianceConstraint(),
            UniquenessConstraint(),
            SizeConstraint(),
            AbbreviationConstraint(),
        ]

    def check_all(self, tex_content: str) -> List[Violation]:
        """运行所有规则的 check()，返回全部违规"""
        all_violations = []
        for rule in self.rules:
            try:
                violations = rule.check(tex_content, self.template_type)
                all_violations.extend(violations)
            except Exception as e:
                logger.error(f"[ConstraintChecker] 规则 {rule.name} 检查异常: {e}")
        return all_violations

    def fix_all(self, tex_content: str) -> Tuple[str, List[Violation]]:
        """
        运行所有规则：check → fix → re-check 循环。
        返回 (修复后内容, 修复后的剩余违规)。
        """
        for iteration in range(3):  # 最多 3 轮修复
            violations = self.check_all(tex_content)
            if not violations:
                logger.info(f"[ConstraintChecker] 第 {iteration + 1} 轮: 所有约束通过")
                return tex_content, []

            critical = [v for v in violations if v.severity == "critical"]
            logger.info(
                f"[ConstraintChecker] 第 {iteration + 1} 轮: "
                f"{len(violations)} 个违规 ({len(critical)} critical)"
            )

            # 按规则修复
            for rule in self.rules:
                rule_violations = [v for v in violations if v.rule == rule.name]
                if rule_violations:
                    tex_content = rule.fix(tex_content, rule_violations)

            # 修复后重新检查
            remaining = self.check_all(tex_content)
            if len(remaining) < len(violations):
                logger.info(
                    f"[ConstraintChecker] 修复有效: {len(violations)} → {len(remaining)} 个违规"
                )
            if len(remaining) == 0:
                break

        final_violations = self.check_all(tex_content)
        return tex_content, final_violations


# ═══════════════════════════════════════════════════════════════
# 公共接口
# ═══════════════════════════════════════════════════════════════

def run_constraint_check(tex_content: str, template_type: str = "ieee_trans",
                         auto_fix: bool = True) -> Dict:
    """
    运行约束引擎的公共接口。

    Args:
        tex_content: LaTeX 源码
        template_type: 模板类型（ieee_trans / acm_conf）
        auto_fix: 是否自动修复

    Returns:
        {
            "violations": [...],       # 违规列表
            "fixed_content": str,      # 修复后内容
            "critical_count": int,     # 严重违规数
            "warning_count": int,      # 警告数
            "all_passed": bool,        # 是否全部通过
        }
    """
    checker = ConstraintChecker(template_type)

    if auto_fix:
        fixed_content, remaining = checker.fix_all(tex_content)
    else:
        remaining = checker.check_all(tex_content)
        fixed_content = tex_content

    critical = [v for v in remaining if v.severity == "critical"]
    warnings = [v for v in remaining if v.severity == "warning"]

    result = {
        "violations": [
            {
                "rule": v.rule,
                "severity": v.severity,
                "description": v.description,
                "location": v.location,
                "fix_hint": v.fix_hint,
            }
            for v in remaining
        ],
        "fixed_content": fixed_content,
        "critical_count": len(critical),
        "warning_count": len(warnings),
        "all_passed": len(critical) == 0,
    }

    if remaining:
        logger.info(
            f"[ConstraintChecker] 结果: {len(critical)} critical, "
            f"{len(warnings)} warnings"
        )
        for v in critical:
            logger.warning(f"  [CRITICAL] {v.rule}: {v.description[:80]}")

    return result


def sanitize_tikz(tikz_code: str) -> str:
    """
    TikZ ASCII 清洗公共接口。
    在 tikz_generator.py 生成后调用。
    """
    constraint = ASCIITextConstraint()
    violations = constraint.check(tikz_code)
    if violations:
        tikz_code = constraint.fix(tikz_code, violations)
    return tikz_code


def validate_table_compilable(table_latex: str, latex_dir: str) -> Dict:
    """
    Render-then-insert 策略：单独编译验证表格 LaTeX 代码。

    借鉴 reckoning.dev 的分块编译验证策略：
    每个表格独立编译，确认无误后再组装到论文中。

    Args:
        table_latex: 单个表格的 LaTeX 代码（从 \begin{table} 到 \end{table}）
        latex_dir: LaTeX 工作目录（用于编译）

    Returns:
        {"compilable": bool, "errors": [...], "fixed_latex": str}
    """
    import subprocess
    import tempfile

    # 构建最小可编译文档包裹表格
    wrapper = r"""\documentclass[lettersize,journal]{IEEEtran}
\usepackage{amsmath,amssymb,amsfonts}
\usepackage{array}
\usepackage{booktabs}
\usepackage{multirow}
\usepackage{graphicx}
\usepackage{xcolor}
\begin{document}
""" + table_latex + r"""
\end{document}
"""

    # 写入临时文件并编译
    test_dir = os.path.join(latex_dir, "_table_test")
    os.makedirs(test_dir, exist_ok=True)
    test_tex = os.path.join(test_dir, "test_table.tex")

    try:
        with open(test_tex, 'w', encoding='utf-8') as f:
            f.write(wrapper)

        # 编译
        result = subprocess.run(
            ['xelatex', '-interaction=nonstopmode', '-file-line-error',
             '-output-directory', test_dir, test_tex],
            capture_output=True, text=True, timeout=30,
            env={**os.environ, 'PATH': os.environ.get('PATH', '') + ':/usr/local/texlive/2026/bin/x86_64-linux'}
        )

        # 检查编译日志
        log_path = os.path.join(test_dir, "test_table.log")
        errors = []
        if os.path.exists(log_path):
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                log = f.read()
            for line in log.split('\n'):
                if line.startswith('! '):
                    errors.append(line[2:].strip())

        compilable = len(errors) == 0

        if not compilable:
            logger.warning(f"[TableValidation] 表格编译失败: {len(errors)} 个错误")
            for e in errors[:5]:
                logger.warning(f"  - {e[:80]}")

        return {
            "compilable": compilable,
            "errors": errors,
            "fixed_latex": table_latex,
        }

    except Exception as e:
        logger.error(f"[TableValidation] 编译异常: {e}")
        return {"compilable": False, "errors": [str(e)], "fixed_latex": table_latex}

    finally:
        # 清理临时文件
        import shutil
        if os.path.exists(test_dir):
            try:
                shutil.rmtree(test_dir)
            except Exception:
                pass


def validate_all_tables(tex_content: str, latex_dir: str) -> str:
    """
    提取并验证所有表格，移除无法编译的表格。
    """
    tables = re.findall(
        r'(\\begin\{table\*?\}.*?\\end\{table\*?\})',
        tex_content, re.DOTALL
    )

    if not tables:
        return tex_content

    logger.info(f"[TableValidation] 验证 {len(tables)} 个表格...")

    for i, table in enumerate(tables, 1):
        result = validate_table_compilable(table, latex_dir)
        if result["compilable"]:
            logger.info(f"  表格 {i}: ✅ 编译通过")
        else:
            logger.warning(f"  表格 {i}: ❌ 编译失败，尝试简化...")
            # 尝试简化：移除 resizebox 包裹，使用简单 tabular
            simplified = _simplify_table(table)
            simp_result = validate_table_compilable(simplified, latex_dir)
            if simp_result["compilable"]:
                tex_content = tex_content.replace(table, simplified)
                logger.info(f"  表格 {i}: ✅ 简化后编译通过")
            else:
                logger.warning(f"  表格 {i}: 简化后仍失败，保留原样")

    return tex_content


def _simplify_table(table_latex: str) -> str:
    """将复杂表格简化为基础三线表"""
    # 提取 caption 和 label
    caption_match = re.search(r'\\caption\{([^}]+)\}', table_latex)
    label_match = re.search(r'\\label\{([^}]+)\}', table_latex)

    caption = caption_match.group(1) if caption_match else "Comparison results."
    label = label_match.group(1) if label_match else "tab:simplified"

    # 提取 tabular 内容
    tabular_match = re.search(
        r'\\begin\{tabular\*?\}.*?\}(.*?)\\end\{tabular\*?\}',
        table_latex, re.DOTALL
    )

    if not tabular_match:
        return table_latex

    tabular_content = tabular_match.group(1)

    # 计算列数（统计第一行的 & 数量）
    first_data_line = ""
    for line in tabular_content.split('\n'):
        stripped = line.strip()
        if stripped and not stripped.startswith('\\'):
            first_data_line = stripped
            break

    col_count = first_data_line.count('&') + 1 if first_data_line else 3
    col_spec = 'l' * col_count

    # 重建简单表格
    simplified = f"""\\begin{{table}}[!t]
\\caption{{{caption}}}
\\label{{{label}}}
\\centering
\\begin{{tabular}}{{{col_spec}}}
\\toprule
{tabular_content.strip()}
\\bottomrule
\\end{{tabular}}
\\end{{table}}"""

    return simplified
