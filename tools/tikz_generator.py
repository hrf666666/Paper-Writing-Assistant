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
import json
import logging
from config.project_config import PAPER_TITLE, OUTPUT_DIR, GENERATION_MODELS
from agent.api_client import get_api_client
from utils.json_utils import extract_json_from_string

logger = logging.getLogger(__name__)


def _get_api():
    """延迟获取API客户端"""
    return get_api_client()


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
            figure_size_hint = "图的宽度适合单栏论文（约0.48\\\\textwidth 或 \\\\linewidth）"
        else:
            figure_size_hint = "图的宽度适合双栏论文（约\\\\textwidth）"
    else:
        figure_size_hint = "图的宽度适合单栏论文（约0.48\\\\textwidth 或 \\\\linewidth）"
    
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
5. 模块使用圆角矩形：\\node[draw, rounded corners, fill=color!20, minimum width=Xcm, minimum height=Ycm]
6. 数据使用平行四边形或圆柱体
7. 连接使用：\\draw[-{{Stealth[length=3mm]}}, thick] (A) -- (B)
8. 使用颜色区分不同类型模块：
   - 编码器/特征提取：蓝色 (fill=blue!20)
   - 解码器/预测：绿色 (fill=green!20)
   - 核心创新模块：橙色 (fill=orange!30)
   - 损失/约束：红色 (fill=red!20)
9. 标注关键维度和操作名称
10. {figure_size_hint}
11. 所有模块名称必须与论文正文中的模块名称完全一致
12. 数据流方向必须与论文描述的输入→处理→输出流程一致

**重要**：生成的TikZ代码必须能编译通过。请确保：
- 所有node都有唯一ID
- 所有坐标引用都存在
- 括号匹配正确
- 没有语法错误

请直接给出可编译的TikZ代码，以\\begin{{tikzpicture}}开头，以\\end{{tikzpicture}}结尾。
不要包含\\documentclass等外层代码。
"""
    
    tikz_code = _get_api().call_generation(prompt)
    
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
    
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(tikz_code)
        logger.info(f"TikZ架构图已保存到: {output_path}")
    
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
    
    refined = _get_api().call_generation(prompt)
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
        print("TikZ架构图生成完成")
