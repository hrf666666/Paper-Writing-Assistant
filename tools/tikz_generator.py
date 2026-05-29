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
6. 使用紧凑布局：`node distance=0.8cm and 1.2cm`，`x=0.5cm, y=0.5cm`
7. 模块使用圆角矩形：\\node[draw, rounded corners, fill=color!20, minimum width=2cm, minimum height=1cm]
8. 数据使用平行四边形或圆柱体
9. 连接使用：\\draw[-{{Stealth[length=2mm]}}, thick] (A) -- (B)
10. 使用颜色区分不同类型模块：
   - 编码器/特征提取：蓝色 (fill=blue!20)
   - 解码器/预测：绿色 (fill=green!20)
   - 核心创新模块：橙色 (fill=orange!30)
   - 损失/约束：红色 (fill=red!20)
11. 标注关键维度和操作名称
12. {figure_size_hint}
13. 所有模块名称必须与论文正文中的模块名称完全一致
14. 数据流方向必须与论文描述的输入→处理→输出流程一致
15. **布局策略：垂直堆叠优于水平展开，避免宽度超出页边距**
16. **锚点命名规则（严格遵守）**：TikZ 节点锚点必须使用 PGF 标准名称：
    - 上: `.north`（不是 `.top`）
    - 下: `.south`（不是 `.bottom`）
    - 左: `.west`（不是 `.left`）
    - 右: `.east`（不是 `.right`）
    - 例如: `(input.south) -- (decomp.north)`，禁止 `(input.bottom) -- (decomp.top)`
17. **禁止使用 `&` 字符**：TikZ 节点标签中如需表达"and"语义，使用 `\\&` 或直接用 `and`

**重要约束**：
1. 生成的TikZ代码必须能编译通过。
2. **所有节点标签、注释、模块名称必须使用英文ONLY**。绝对不要在TikZ代码中使用任何中文字符。
3. 所有括号使用英文半角符号。
4. **节点最小宽度 2cm，最大宽度 3.5cm**；禁止 minimum width > 3.5cm
5. **总坐标范围 x 方向不超过 14cm**（否则在论文中会溢出叠加）

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
    if "\\begin{tikzpicture}" not in tikz_code or "\\end{tikzpicture}" not in tikz_code:
        logger.warning("TikZ代码缺少tikzpicture环境，尝试修复...")
        if "\\begin{tikzpicture}" not in tikz_code:
            tikz_code = "\\begin{tikzpicture}\n" + tikz_code
        if "\\end{tikzpicture}" not in tikz_code:
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
    tikz_code = re.sub(r'(?<!\\)&', r'\\&', tikz_code)

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

    if output_path:
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(tikz_code)
            logger.info(f"TikZ架构图已保存到: {output_path}")
        except IOError as e:
            logger.error(f"TikZ文件保存失败 {output_path}: {e}")
    
    return tikz_code


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
