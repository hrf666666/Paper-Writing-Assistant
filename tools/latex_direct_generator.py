# -*- coding: utf-8 -*-
"""
LaTeX 后处理修复函数集（精简版）

本文件原为 v9.0 "LaTeX 直出" 模块（含 compile_latex / generate_section_latex /
assemble_full_paper / _overflow_heal_loop / _fix_long_equations 等），但 v12+ 架构
改为 latex_converter 主路径后，这些入口函数全部不可达（agent/ 从不 import）。

经一手追踪确认，当前仅有 4 个后处理 fix 函数仍被 latex_converter 调用：
  _validate_float_sizing / _fix_textwidth_confusion /
  _ensure_table_resizebox / _ensure_tikz_fits
其余（_fix_long_equations / _overflow_heal_loop / generate_section_latex /
assemble_full_paper / compile_* / _call_llm 等）均为死代码，已删除。
"""

import re
import logging

logger = logging.getLogger(__name__)

def _validate_float_sizing(latex_code: str) -> str:
    """
    后处理：检查 LLM 生成的 figure/table 尺寸选择是否合理。
    
    规则：
    - table*: >4列 或 包含长文本单元格 → 合理
    - table*: ≤4列 且 都是短文本 → 降级为 table (单栏)
    - figure*: 架构图/多组件图/多子图 → 合理  
    - figure*: 单张小图/简单图 → 降级为 figure (单栏)
    """
    # ── 表格尺寸验证 ──
    # 找到所有 table* 环境，检查列数
    def _check_table_star(match):
        env_content = match.group(0)
        # 提取列规格
        col_spec_match = re.search(r'\\begin\{tabular[*]?\}(?:\{[^}]*\})?\{([^}]+)\}', env_content)
        if not col_spec_match:
            return env_content  # 无法解析，保持原样
        
        col_spec = col_spec_match.group(1)
        # 清理 @{...} 和 p{...} 等，数 l/c/r/p 数量
        clean_spec = re.sub(r'@\{[^}]*\}', '', col_spec)
        clean_spec = re.sub(r'\{[^}]*\}', '', clean_spec)
        col_count = len(re.findall(r'[lcrp]', clean_spec))
        
        if col_count <= 4:
            logger.info(f"[float_sizing] table* ({col_count} cols) → table (downgrade)")
            result = env_content.replace('\\begin{table*}', '\\begin{table}', 1)
            result = result.replace('\\end{table*}', '\\end{table}', 1)
            # 去掉可能残留的 \resizebox{\textwidth}{!}{ 包裹
            result = re.sub(r'\\resizebox\{\\textwidth\}\{!\}\{\s*\n', '', result)
            # 去掉 resizebox 关闭的孤立 }
            result = re.sub(r'(\\end\{tabular\})\s*\n\s*\}', r'\1', result)
            # 重新包裹 \resizebox{\columnwidth}{!}（修复 textwidth 混淆）
            if '\\resizebox' not in result:
                result = result.replace(
                    '\\begin{tabular}',
                    '\\resizebox{\\columnwidth}{!}{%\n\\begin{tabular}'
                )
                result = result.replace(
                    '\\end{tabular}',
                    '\\end{tabular}%\n}'
                )
            else:
                # 已有 resizebox 但可能用的是 \textwidth → 修正为 \columnwidth
                result = result.replace('\\resizebox{\\textwidth}', '\\resizebox{\\columnwidth}')
            result = result.replace('\\end{tabular*}', '\\end{tabular}')
            return result
        
        return env_content
    
    latex_code = re.sub(
        r'\\begin\{table\*\}.*?\\end\{table\*\}',
        _check_table_star, latex_code, flags=re.DOTALL
    )
    
    # ── 图片尺寸验证 ──
    # figure* 只保留给真正的大图，小图降级
    # 启发式：如果一个 figure* 里只有一个 \includegraphics 且没有 subfigure，
    # 或者 TikZ 的 node 数量 ≤3，降级为 figure
    def _check_figure_star(match):
        env_content = match.group(0)
        
        # 检查是否有多子图（subfloat / subfigure / minipage 组合）
        has_subfig = bool(re.search(r'\\subfloat|\\begin\{minipage\}|\\subfigure', env_content))
        
        # 检查 TikZ node 数量
        tikz_nodes = len(re.findall(r'\\node\b', env_content))
        
        # 检查 \includegraphics 数量
        img_count = len(re.findall(r'\\includegraphics', env_content))
        
        # 大图特征：多子图 或 多node TikZ 或 明确提到 architecture/pipeline/overview
        is_large = (
            has_subfig or 
            tikz_nodes > 5 or 
            img_count > 2 or
            bool(re.search(r'architecture|pipeline|overview|framework|overall', env_content, re.IGNORECASE))
        )
        
        if not is_large:
            logger.info(f"[float_sizing] figure* (small, nodes={tikz_nodes}, imgs={img_count}) → figure (downgrade)")
            result = env_content.replace('\\begin{figure*}', '\\begin{figure}', 1)
            result = result.replace('\\end{figure*}', '\\end{figure}', 1)
            # 同时把 width=\textwidth 改为 width=\columnwidth
            result = result.replace('width=\\textwidth', 'width=\\columnwidth')
            return result
        
        return env_content
    
    latex_code = re.sub(
        r'\\begin\{figure\*\}.*?\\end\{figure\*\}',
        _check_figure_star, latex_code, flags=re.DOTALL
    )
    
    return latex_code


def _fix_textwidth_confusion(latex_code: str) -> str:
    """
    后处理：将单栏环境（table / figure，非 table* / figure*）中的
    \\textwidth 替换为 \\columnwidth，防止单栏元素撑到双栏宽度溢出。
    """
    # ── 单栏 table 环境 ──
    def _fix_table_env(match):
        env = match.group(0)
        old = env
        env = env.replace(r'\textwidth', r'\columnwidth')
        if env != old:
            logger.info("[fix_textwidth] 单栏 table 中 \\textwidth → \\columnwidth")
        return env

    # 匹配 \begin{table} 到 \end{table}，但排除 \begin{table*} 到 \end{table*}
    # 使用负向前瞻确保 \begin{table} 后面不是 *
    # 同时确保 \end{table} 后面不是 *
    # 简单策略：用 (?!...) 做前后约束
    latex_code = re.sub(
        r'\\begin\{table\}(?!\*).*?\\end\{table\}(?!\*)',
        _fix_table_env, latex_code, flags=re.DOTALL,
    )

    # ── 单栏 figure 环境 ──
    def _fix_figure_env(match):
        env = match.group(0)
        old = env
        env = env.replace(r'width=\textwidth', r'width=\columnwidth')
        env = env.replace(r'\textwidth', r'\columnwidth')
        if env != old:
            logger.info("[fix_textwidth] 单栏 figure 中 \\textwidth → \\columnwidth")
        return env

    latex_code = re.sub(
        r'\\begin\{figure\}(?!\*).*?\\end\{figure\}(?!\*)',
        _fix_figure_env, latex_code, flags=re.DOTALL,
    )

    return latex_code


def _ensure_table_resizebox(latex_code: str) -> str:
    """
    后处理：为缺少 \\resizebox 缩放包裹的 tabular 环境自动添加缩放。
    同时处理单栏 table 和双栏 table* 环境。
    v10.1: 对宽表格（>5列）强制添加 \\small/\\footnotesize 缩小字体。
    """
    def _fix_one_table(match):
        env = match.group(0)
        # 已有 resizebox → 不动
        if r'\resizebox' in env:
            return env

        # 找 tabular 开始位置
        tabular_start = re.search(r'\\begin\{tabular[*]?\}', env)
        if not tabular_start:
            return env

        # 判断单栏 / 双栏
        is_star = r'\begin{table*}' in env
        width_cmd = r'\textwidth' if is_star else r'\columnwidth'

        # 检测列数，宽表格需要缩小字体
        col_spec_match = re.search(r'\\begin\{tabular[*]?\}(?:\{[^}]*\})?\{([^}]+)\}', env)
        col_count = 0
        font_size_prefix = ''
        if col_spec_match:
            clean_spec = re.sub(r'@\{[^}]*\}', '', col_spec_match.group(1))
            clean_spec = re.sub(r'\{[^}]*\}', '', clean_spec)
            col_count = len(re.findall(r'[lcrp]', clean_spec))
            if col_count > 5:
                font_size_prefix = '\\footnotesize\n'
            elif col_count > 4:
                font_size_prefix = '\\small\n'

        # 在 \begin{tabular} 前插入 \resizebox{width}{!}{
        before = env[:tabular_start.start()]
        tabular_and_rest = env[tabular_start.start():]

        # 找 \end{tabular} 位置
        tabular_end = re.search(r'\\end\{tabular[*]?\}', tabular_and_rest)
        if not tabular_end:
            return env

        tabular_body = tabular_and_rest[:tabular_end.end()]
        after = tabular_and_rest[tabular_end.end():]

        # 包裹 resizebox
        result = (
            before + font_size_prefix +
            r'\resizebox{' + width_cmd + r'}{!}{%' + '\n' +
            tabular_body + '%' + '\n' + '}' +
            after
        )

        logger.info(f"[ensure_resizebox] table{'*' if is_star else ''} ({col_count} cols) 添加 resizebox({width_cmd})")
        return result

    # 匹配所有 table 环境（含 table*）
    latex_code = re.sub(
        r'\\begin\{table\*?\}.*?\\end\{table\*?\}',
        _fix_one_table, latex_code, flags=re.DOTALL,
    )

    return latex_code


def _ensure_tikz_fits(latex_code: str) -> str:
    """
    后处理：所有未被 \\resizebox 包裹的 tikzpicture 统一包裹 resizebox，
    确保缩放到所在环境（table/figure/table*/figure*）的可用宽度。
    """
    def _fix_one_tikz(match):
        tikz_block = match.group(0)

        # 检查 tikzpicture 前面是否有 \resizebox 包裹（看前 100 个字符）
        pos = match.start()
        preceding = latex_code[max(0, pos - 100):pos].strip()
        if r'\resizebox' in preceding:
            return tikz_block

        # 判断 tikzpicture 所在环境是单栏还是双栏
        all_preceding = latex_code[:pos]

        # 最近的环境类型
        last_fig_star = all_preceding.rfind(r'\begin{figure*}')
        last_fig = all_preceding.rfind(r'\begin{figure}')
        last_tab_star = all_preceding.rfind(r'\begin{table*}')
        last_tab = all_preceding.rfind(r'\begin{table}')

        # 判断是否双栏
        max_star = max(last_fig_star, last_tab_star)
        max_normal = max(last_fig, last_tab)

        if max_star > max_normal and max_star >= 0:
            width_cmd = r'\textwidth'
        else:
            width_cmd = r'\columnwidth'

        # 包裹整个 tikzpicture
        result = r'\resizebox{' + width_cmd + r'}{!}{' + '\n' + tikz_block + '\n' + '}'
        logger.info(f"[ensure_tikz_fits] tikzpicture 包裹 resizebox({width_cmd})")
        return result

    # 匹配 tikzpicture 环境
    latex_code = re.sub(
        r'\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}',
        _fix_one_tikz, latex_code, flags=re.DOTALL,
    )

    return latex_code

