# -*- coding: utf-8 -*-
"""
Tool: TikZ架构图生成器
根据模型架构描述和参考论文的图片设计风格，生成TikZ代码

v4改进：
1. 更精准的prompt，确保TikZ代码与论文内容对齐
2. 集成ref_pdf的图表风格参考
3. 添加架构图验证步骤
4. 支持创新点高亮
"""

import os
import re
import json
import logging
from config.project_config import PAPER_TITLE, OUTPUT_DIR, GENERATION_MODELS
from tools.base_tool import get_tool_api
from utils.json_utils import extract_json_from_string

logger = logging.getLogger(__name__)


def _get_api():
    """延迟获取API客户端"""
    return get_tool_api()


def generate_tikz_from_architecture(model_architecture, figure_style=None, output_path=None,
                                     innovation_points=None, article_type_info=None):
    """
    根据模型架构描述生成TikZ架构图代码
    
    Args:
        model_architecture: 模型架构描述(dict)
        figure_style: 参考论文的图片风格(dict, 可选)
        output_path: 输出文件路径(可选)
        innovation_points: 创新点列表(用于突出显示核心模块)
        article_type_info: 文章类型信息(用于适配图表风格)
    
    Returns:
        tikz_code: TikZ代码字符串
    """
    
    arch_str = json.dumps(model_architecture, ensure_ascii=False, indent=2)
    style_str = json.dumps(figure_style, ensure_ascii=False, indent=2) if figure_style else "默认风格"
    
    # 构建创新点高亮指令
    innovation_highlight = ""
    if innovation_points:
        if isinstance(innovation_points, list):
            core_names = []
            for ip in innovation_points:
                if isinstance(ip, dict):
                    name = ip.get("name", ip.get("创新点名称", ""))
                else:
                    name = str(ip)
                if name:
                    core_names.append(name)
            if core_names:
                innovation_highlight = "**核心创新模块（必须用醒目颜色突出显示）**：\n"
                for name in core_names:
                    innovation_highlight += f'- {name} (使用橙色或红色填充，fill=orange!30或fill=red!20)\n'
                innovation_highlight += "\n"
    
    # 构建论文等级适配
    figure_size_hint = ""
    if article_type_info:
        fig_style = article_type_info.get("figure_style", "column_width")
        if fig_style == "column_width":
            # IEEEtran 双栏: figure* 用 \textwidth (~7inch), figure 用 \columnwidth (~3.5inch)
            # 架构图用 figure*（双栏），宽度适配 \textwidth
            figure_size_hint = "图使用 figure* 环境（占满双栏宽度，约\\\\textwidth ≈ 7 inch），总宽度不超过 7 inch"
        else:
            figure_size_hint = "图的宽度适合双栏论文（约\\\\textwidth）"
    else:
        figure_size_hint = "图使用 figure* 环境（占满双栏宽度，约\\\\textwidth ≈ 7 inch），总宽度不超过 7 inch"
    
    # 构建参考图表风格指令
    ref_style_hint = ""
    if figure_style and isinstance(figure_style, dict):
        layout = figure_style.get("布局方式", "")
        module_style = figure_style.get("模块样式", {})
        connection_style = figure_style.get("连接样式", {})
        color_scheme = figure_style.get("配色方案", [])
        annotation = figure_style.get("标注规范", {})
        
        if layout:
            ref_style_hint += f"- 参考布局方式: {layout}\n"
        if module_style:
            ref_style_hint += f"- 参考模块样式: {json.dumps(module_style, ensure_ascii=False)[:300]}\n"
        if connection_style:
            ref_style_hint += f"- 参考连接样式: {json.dumps(connection_style, ensure_ascii=False)[:200]}\n"
        if color_scheme:
            ref_style_hint += f"- 参考配色方案: {color_scheme}\n"
        if annotation:
            ref_style_hint += f"- 参考标注规范: {json.dumps(annotation, ensure_ascii=False)[:200]}\n"
    
    if not ref_style_hint:
        ref_style_hint = "- 使用默认学术风格：自左向右数据流，圆角矩形模块，实线箭头连接\n"
    
    prompt = f"""
你是一名LaTeX/TikZ绘图专家。请为论文"{PAPER_TITLE}"的模型生成一个高质量的TikZ架构图。

**模型架构信息**：
{arch_str[:8000]}

{innovation_highlight}

**设计风格参考**：
{ref_style_hint}

**TikZ代码要求**：
1. 使用 \\begin{{tikzpicture}} 环境
2. 使用 positioning 库进行相对定位
3. 使用 arrows.meta 库设置箭头样式
4. 使用 shapes.geometric 库获取更多节点形状
5. **总宽度不超过 \\textwidth（IEEEtran双栏约 7inch / 17.8cm）**，使用 figure* 双栏环境
6. 模块使用圆角矩形，数据使用平行四边形
7. 连接使用 \\draw[-{{Stealth[length=2mm]}}, thick] (A) -- (B)
8. 颜色方案：编码器=blue!20，解码器=green!20，创新模块=orange!30，损失=red!20
9. 标注关键维度和操作名称
10. {figure_size_hint}
11. **所有模块名称必须与上面的模型架构信息完全一致，不要用"Module A/B"这种占位符**
12. 数据流方向必须与架构描述一致
13. **布局策略：垂直堆叠优于水平展开，避免宽度超出页边距**

**锚点命名规则（严格遵守）**：
TikZ 锚点用 PGF 标准：.north .south .west .east（不是 .top .bottom .left .right）

**防止文字与模块重叠（CRITICAL）**：
1. **必须设置 text width**：每个节点必须设置 `text width=2.2cm`（或根据文字长度调整），
   让长文字自动换行，而不是撑大节点导致重叠
2. **使用边缘间距（outer sep）**：`outer sep=3pt`，确保节点之间有物理间隙
3. **node distance 是中心距**：如果节点宽 3cm，`node distance=2cm` 意味着中心距 2cm，
   节点会重叠 1cm！所以 node distance 必须 ≥ max(节点宽度) + 间距
   推荐：`node distance=1.5cm and 2.5cm`（垂直 1.5cm，水平 2.5cm）
4. **超过 5 个模块时用两行布局**：第一行放前半，第二行放后半，
   用箭头连接上下行，不要全部水平排列
5. **每行不超过 4 个模块**：每个模块 text width=2.2cm + 间距 = 总宽 ~12cm，安全不超 16cm
6. **使用 `align=center`**：配合 text width 让多行文字居中显示
7. **字体用 \\footnotesize 或 \\small**：不要用 \\normalsize，节省空间

**重要约束**：
1. 必须能编译通过
2. 所有文字必须英文ONLY
3. **禁止使用 & 字符**（用 \\& 替代）
4. **每个节点的标签必须是架构中真实的模块名，严禁用"Proposed Module A"这种泛化标签**

请直接给出可编译的TikZ代码，以\\begin{{tikzpicture}}开头，以\\end{{tikzpicture}}结尾。
不要包含\\documentclass等外层代码。
"""
    
    tikz_code = ""
    try:
        tikz_code = _get_api().call_generation(prompt)
    except Exception as e:
        logger.error(f"TikZ代码生成失败: {e}")
        return ""

    if not tikz_code:
        logger.warning("TikZ代码生成返回空结果")
        return ""
    
    # 清理markdown包裹
    tikz_code = tikz_code.strip()
    if tikz_code.startswith("```"):
        lines = tikz_code.split("\n")
        tikz_code = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    tikz_code = tikz_code.strip()
    
    # 验证TikZ代码基本结构
    has_begin = "\\begin{tikzpicture}" in tikz_code
    has_end = "\\end{tikzpicture}" in tikz_code
    if not has_begin or not has_end:
        # 区分“漏标签的合法 TikZ”与“LLM 思考过程文本”
        # 合法 TikZ 体应含 \\node/\\draw/\\path 等命令；否则判定为无效输出
        has_tikz_cmd = any(cmd in tikz_code for cmd in
                           ("\\node", "\\draw", "\\path", "\\coordinate", "\\fill"))
        if not has_tikz_cmd:
            logger.warning("TikZ输出不含 tikzpicture 环境且无 TikZ 命令（疑为 LLM 思考过程），判废返回空")
            return ""
        logger.warning("TikZ代码缺少tikzpicture环境，补全标签...")
        if not has_begin:
            tikz_code = "\\begin{tikzpicture}\n" + tikz_code
        if not has_end:
            tikz_code = tikz_code + "\n\\end{tikzpicture}"

    # ── PGF 锚点自动修正 ──
    # LLM 可能生成非法锚点名 (.bottom/.top/.left/.right)，自动替换为 PGF 标准
    anchor_fixes = {
        r'\.bottom\b': '.south',
        r'\.top\b': '.north',
        r'\.left\b': '.west',
        r'\.right\b': '.east',
    }
    anchor_fix_count = 0
    for wrong, correct in anchor_fixes.items():
        new_code = re.sub(wrong, correct, tikz_code)
        if new_code != tikz_code:
            count = len(tikz_code) - len(new_code.replace(correct, wrong))
            anchor_fix_count += 1
            tikz_code = new_code
    if anchor_fix_count:
        logger.info(f"[TikZ] 锚点自动修正: {anchor_fix_count} 类非法锚点已替换")

    # ── TikZ 节点标签内 & 转义 ──
    # LLM 可能在节点文本中使用裸 &，自动转义为 \&
    # 但保留 matrix/tabular 环境中的列分隔符 &
    def _escape_amp_in_nodes(m):
        prefix = m.group(1) or ''
        text = m.group(2)
        suffix = m.group(3) or ''
        escaped = text.replace('&', r'\&')
        return f"{prefix}{escaped}{suffix}"

    tikz_code = re.sub(
        r'(\\node[^\{]*\{)(.*?)(\})',
        _escape_amp_in_nodes,
        tikz_code,
        flags=re.DOTALL
    )

    # ── ASCII 清洗后处理（约束引擎） ──
    # 不管 LLM 用什么语言输出，强制清洗非 ASCII 字符
    try:
        from tools.latex_constraint_checker import sanitize_tikz
        pre_ascii_len = len(tikz_code)
        tikz_code = sanitize_tikz(tikz_code)
        if len(tikz_code) != pre_ascii_len:
            logger.info(f"[TikZ] ASCII 清洗: {pre_ascii_len} → {len(tikz_code)} 字符")
    except Exception as e:
        logger.warning(f"[TikZ] ASCII 清洗失败（不阻塞）: {e}")

    # ── 编译验证 + 自动修复（最多 1 轮） ──
    tikz_code = _compile_verify_and_fix(tikz_code)

    if output_path:
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(tikz_code)
            logger.info(f"TikZ架构图已保存到: {output_path}")
        except IOError as e:
            logger.error(f"TikZ文件保存失败 {output_path}: {e}")
    
    return tikz_code


def _compile_verify_and_fix(tikz_code: str, max_retries: int = 1) -> str:
    """
    编译验证 TikZ 代码，失败时让 LLM 自动修复。

    策略：
    1. 包裹为 standalone 文档 → pdflatex 编译
    2. 编译成功 → 返回原始 tikz_code
    3. 编译失败 → 把错误信息喂给 LLM 修复 → 重新编译
    """
    import subprocess
    import tempfile
    import shutil

    # 包裹为完整文档
    full_doc = (
        r"\documentclass[border=4pt]{standalone}" "\n"
        r"\usepackage{tikz}" "\n"
        r"\usetikzlibrary{positioning, arrows.meta, shapes.geometric, calc, fit, backgrounds}" "\n"
        r"\usepackage{amsmath,amssymb}" "\n"
        r"\begin{document}" "\n"
        + tikz_code + "\n"
        r"\end{document}"
    )

    # 查找 pdflatex
    pdflatex = "pdflatex"
    for candidate in [
        "/usr/local/texlive/2026/bin/x86_64-linux/pdflatex",
        "/usr/local/texlive/2025/bin/x86_64-linux/pdflatex",
        "/usr/local/texlive/2024/bin/x86_64-linux/pdflatex",
        "/usr/bin/pdflatex",
    ]:
        if os.path.isfile(candidate):
            pdflatex = candidate
            break

    tmp_dir = tempfile.mkdtemp(prefix="tikz_verify_")
    try:
        # 第 1 次编译
        tex_path = os.path.join(tmp_dir, "verify.tex")
        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(full_doc)

        result = subprocess.run(
            [pdflatex, "-interaction=nonstopmode", "-halt-on-error", "verify.tex"],
            cwd=tmp_dir, capture_output=True, text=True, timeout=30,
        )

        pdf_path = os.path.join(tmp_dir, "verify.pdf")
        if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 500:
            logger.info("[TikZ] 编译验证通过 ✅")
            return tikz_code

        # 编译失败 → LLM 修复
        error_msg = result.stdout[-600:] if result.stdout else "unknown error"
        logger.warning(f"[TikZ] 编译验证失败，尝试 LLM 修复: {error_msg[:200]}")

        for attempt in range(max_retries):
            fix_prompt = f"""Fix the TikZ compilation error. Output ONLY the corrected \\begin{{tikzpicture}}...\\end{{tikzpicture}} code.

## Current Code
```latex
{tikz_code[:4000]}
```

## Compilation Error
```
{error_msg[:500]}
```

## Common Fixes
- Missing semicolons at end of \\draw or \\node commands
- Undefined styles → add them to tikzpicture options
- Unmatched braces {{ }} or brackets [ ]
- Invalid anchor names (.bottom → .south, .top → .north, .left → .west, .right → .east)
- Missing \\usetikzlibrary

Output ONLY the fixed tikzpicture code:"""

            try:
                fixed = _get_api().call_generation(fix_prompt)
            except Exception as e:
                logger.error(f"[TikZ] LLM 修复失败: {e}")
                break

            # 清理修复结果
            fixed = fixed.strip()
            if fixed.startswith("```"):
                lines = fixed.split("\n")
                fixed = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            fixed = fixed.strip()

            # 验证修复后的代码
            fixed_doc = (
                r"\documentclass[border=4pt]{standalone}" "\n"
                r"\usepackage{tikz}" "\n"
                r"\usetikzlibrary{positioning, arrows.meta, shapes.geometric, calc, fit, backgrounds}" "\n"
                r"\usepackage{amsmath,amssymb}" "\n"
                r"\begin{document}" "\n"
                + fixed + "\n"
                r"\end{document}"
            )

            with open(tex_path, "w", encoding="utf-8") as f:
                f.write(fixed_doc)

            result2 = subprocess.run(
                [pdflatex, "-interaction=nonstopmode", "-halt-on-error", "verify.tex"],
                cwd=tmp_dir, capture_output=True, text=True, timeout=30,
            )

            if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 500:
                logger.info(f"[TikZ] LLM 修复成功 ✅ (attempt {attempt + 1})")
                return fixed

            error_msg = result2.stdout[-600:] if result2.stdout else "still failing"
            logger.warning(f"[TikZ] LLM 修复后仍编译失败: {error_msg[:200]}")

        # 编译失败 = tikz_code 是垃圾（可能是 LLM 的思考过程而非代码）
        # 返回空字符串，避免垃圾代码泄漏进 main.tex 导致 xelatex 崩溃
        logger.warning("[TikZ] 编译验证失败，丢弃无效代码（返回空，避免污染 main.tex）")
        return ""

    except subprocess.TimeoutExpired:
        # 超时时无法确认代码是否合法，保守返回空
        logger.warning("[TikZ] 编译验证超时，丢弃代码（返回空）")
        return ""
    except FileNotFoundError:
        logger.info("[TikZ] pdflatex 不可用，跳过编译验证")
        return tikz_code
    except Exception as e:
        logger.warning(f"[TikZ] 编译验证异常: {e}，使用原始代码")
        return tikz_code
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def refine_tikz(tikz_code, feedback):
    """根据反馈修改TikZ代码"""
    
    prompt = f"""
请根据以下反馈修改TikZ架构图代码：

原始代码：
{tikz_code[:4000]}

修改反馈：
{feedback}

请直接给出修改后的完整TikZ代码（\\begin{{tikzpicture}}到\\end{{tikzpicture}}）：
确保代码可编译，括号匹配，node ID唯一。
"""
    
    try:
        refined = _get_api().call_generation(prompt)
    except Exception as e:
        logger.error(f"TikZ代码修改失败: {e}")
        return tikz_code

    if not refined:
        logger.warning("TikZ修改返回空结果，返回原始代码")
        return tikz_code

    refined = refined.strip()
    if refined.startswith("```"):
        lines = refined.split("\n")
        refined = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    
    return refined.strip()


if __name__ == "__main__":
    arch_path = f"{OUTPUT_DIR}/model_architecture.json"
    if os.path.exists(arch_path):
        with open(arch_path, 'r', encoding='utf-8') as f:
            arch = json.load(f)
        
        tikz = generate_tikz_from_architecture(arch, output_path=f"{OUTPUT_DIR}/architecture_figure.tex")
        logger.info("TikZ架构图生成完成")
