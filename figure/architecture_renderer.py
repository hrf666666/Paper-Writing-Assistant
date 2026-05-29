# -*- coding: utf-8 -*-
"""
架构图高级渲染器 (Architecture Renderer)

从项目代码中提取模块依赖图，用 TikZ 组件库组装，
支持 pdflatex 编译验证。

TikZ 组件库:
  - 基础模块: 矩形框 + 文字 + 连接线
  - 编码器/解码器: 梯形/三角形
  - 注意力层: 菱形
  - 残差连接: 弧线
  - 数据流: 粗箭头
  - 创新: 高亮边框
"""

from __future__ import annotations

import json
import os
import logging
import subprocess
import shutil
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


# TikZ 组件库
TIKZ_COMPONENTS = {
    "basic_module": (
        "\\node[draw, rounded corners, minimum width=2.5cm, minimum height=0.8cm, "
        "fill={color}!10, text centered, font=\\small] ({name}) at ({x},{y}) {{{label}}};"
    ),
    "encoder": (
        "\\node[draw, trapezium, trapezium left angle=70, trapezium right angle=110, "
        "minimum width=2cm, minimum height=0.8cm, fill={color}!10, "
        "text centered, font=\\small] ({name}) at ({x},{y}) {{{label}}};"
    ),
    "attention": (
        "\\node[draw, diamond, minimum width=1.5cm, minimum height=1cm, "
        "fill={color}!10, text centered, font=\\small] ({name}) at ({x},{y}) {{{label}}};"
    ),
    "residual": (
        "\\draw[->, thick, dashed, {color}] ({from_x},{from_y}) "
        "to[out=60, in=120] ({to_x},{to_y});"
    ),
    "arrow": (
        "\\draw[->, thick] ({from_name}) -- ({to_name});"
    ),
    "innovation_highlight": (
        "\\node[draw, rounded corners, minimum width=2.5cm, minimum height=0.8cm, "
        "fill=red!5, draw=red!70, line width=1.2pt, text centered, font=\\small\\bfseries] "
        "({name}) at ({x},{y}) {{{label}}};"
    ),
}

# TikZ 文档模板
TIKZ_DOCUMENT = r"""\documentclass[border=5pt]{standalone}
\usepackage{tikz}
\usetikzlibrary{{shapes.geometric, arrows.meta, positioning, calc, fit}}
\begin{{document}}
\begin{{tikzpicture}}[
    node distance=0.8cm,
    >=Stealth,
]
{content}
\end{{tikzpicture}}
\end{{document}}
"""


class ArchitectureRenderer:
    """架构图高级渲染器"""

    def __init__(self, api_client=None):
        self.api_client = api_client

    def render(self, project_data: Dict, output_dir: str,
               venue_adapter=None) -> Dict[str, Any]:
        """
        渲染架构图

        Returns:
            {
                "tikz_code": str,
                "compiled_pdf": str or None,
                "modules": List[str],
                "innovation_modules": List[str],
            }
        """
        arch = project_data.get("model_architecture", {})
        innovations = project_data.get("innovation_points", [])

        # Step 1: 提取模块结构
        modules, connections = self._extract_modules(arch, innovations)
        logger.info(f"[ArchRenderer] 提取 {len(modules)} 个模块, {len(connections)} 个连接")

        # Step 2: 标记创新模块
        innovation_names = set()
        for inn in innovations:
            name = inn.get("创新点名称", "")
            if name:
                innovation_names.add(name.lower())

        # Step 3: 生成 TikZ 代码
        tikz_code = self._generate_tikz(modules, connections, innovation_names)

        # Step 4: 尝试编译验证
        compiled_pdf = self._try_compile(tikz_code, output_dir)

        result = {
            "tikz_code": tikz_code,
            "compiled_pdf": compiled_pdf,
            "modules": [m["name"] for m in modules],
            "innovation_modules": [m["name"] for m in modules if m["name"].lower() in innovation_names],
        }

        # 保存
        tikz_file = os.path.join(output_dir, "architecture_figure.tex")
        with open(tikz_file, 'w', encoding='utf-8') as f:
            f.write(tikz_code)

        return result

    def _extract_modules(self, arch: Dict, innovations: List) -> tuple:
        """从架构数据中提取模块和连接"""
        modules = []
        connections = []

        if isinstance(arch, dict):
            # 尝试从已有结构中提取
            components = arch.get("组件", arch.get("components", []))
            if isinstance(components, list):
                for i, comp in enumerate(components):
                    if isinstance(comp, dict):
                        name = comp.get("name", comp.get("名称", f"Module_{i}"))
                        modules.append({
                            "name": name,
                            "label": name[:25],
                            "type": comp.get("type", "basic_module"),
                        })
                    elif isinstance(comp, str):
                        modules.append({
                            "name": comp,
                            "label": comp[:25],
                            "type": "basic_module",
                        })

            # 如果没有组件列表，用创新点作为模块
            if not modules:
                for i, inn in enumerate(innovations[:6]):
                    name = inn.get("创新点名称", f"Module_{i}")
                    modules.append({
                        "name": name,
                        "label": name[:25],
                        "type": "basic_module",
                    })
                # 添加输入输出
                modules.insert(0, {"name": "Input", "label": "Input", "type": "basic_module"})
                modules.append({"name": "Output", "label": "Output", "type": "basic_module"})

        if not modules:
            modules = [
                {"name": "Input", "label": "Input", "type": "basic_module"},
                {"name": "Encoder", "label": "Encoder", "type": "encoder"},
                {"name": "Core Module", "label": "Core Module", "type": "basic_module"},
                {"name": "Decoder", "label": "Decoder", "type": "basic_module"},
                {"name": "Output", "label": "Output", "type": "basic_module"},
            ]

        # 生成顺序连接
        for i in range(len(modules) - 1):
            connections.append({
                "from": modules[i]["name"],
                "to": modules[i + 1]["name"],
                "type": "arrow",
            })

        return modules, connections

    def _generate_tikz(self, modules: List[Dict], connections: List[Dict],
                        innovation_names: set) -> str:
        """生成 TikZ 代码"""
        lines = []

        # 布局：纵向排列
        y_step = 1.5
        x_center = 0

        for i, mod in enumerate(modules):
            y = -i * y_step
            name = mod["name"].replace(" ", "_").replace("-", "_")
            label = mod.get("label", mod["name"])
            mod_type = mod.get("type", "basic_module")

            is_innovation = mod["name"].lower() in innovation_names
            color = "red" if is_innovation else "blue"

            if is_innovation:
                template = TIKZ_COMPONENTS["innovation_highlight"]
            else:
                template = TIKZ_COMPONENTS.get(mod_type, TIKZ_COMPONENTS["basic_module"])

            # 替换模板变量
            node_code = template.format(
                name=name, label=label, x=x_center, y=y, color=color,
            )
            lines.append(f"  {node_code}")

        # 添加连接线
        lines.append("")
        for conn in connections:
            from_name = conn["from"].replace(" ", "_").replace("-", "_")
            to_name = conn["to"].replace(" ", "_").replace("-", "_")
            template = TIKZ_COMPONENTS.get(conn.get("type", "arrow"), TIKZ_COMPONENTS["arrow"])
            arrow_code = template.format(
                from_name=from_name, to_name=to_name,
                from_x=0, from_y=0, to_x=0, to_y=0,
                color="black",
            )
            lines.append(f"  {arrow_code}")

        content = "\n".join(lines)
        return content

    def _try_compile(self, tikz_code: str, output_dir: str) -> Optional[str]:
        """尝试用 pdflatex 编译验证"""
        if not shutil.which("pdflatex"):
            logger.info("pdflatex not found, skipping compilation")
            return None

        compile_dir = os.path.join(output_dir, "_tikz_compile")
        os.makedirs(compile_dir, exist_ok=True)

        tex_file = os.path.join(compile_dir, "architecture.tex")
        with open(tex_file, 'w', encoding='utf-8') as f:
            f.write(TIKZ_DOCUMENT.format(content=tikz_code))

        try:
            result = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "architecture.tex"],
                cwd=compile_dir, capture_output=True, timeout=30,
            )

            pdf_file = os.path.join(compile_dir, "architecture.pdf")
            if os.path.exists(pdf_file):
                # 复制到输出目录
                target_pdf = os.path.join(output_dir, "architecture_figure.pdf")
                shutil.copy2(pdf_file, target_pdf)
                logger.info(f"[ArchRenderer] TikZ 编译成功: {target_pdf}")
                return target_pdf
            else:
                logger.warning("TikZ 编译未生成 PDF")
                return None

        except (subprocess.TimeoutExpired, Exception) as e:
            logger.warning(f"TikZ 编译失败: {e}")
            return None
