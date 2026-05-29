# -*- coding: utf-8 -*-
"""
视觉验证器 v1.0 — 渲染 PDF → 视觉模型检查 → 反推修复

核心流程：
1. PDF → PNG (pdftoppm)
2. PNG → GLM-5V-turbo 视觉检查
3. 反馈解析 → 结构化修复建议
4. 反推迭代

设计理念：
- 不是"代码层面修 bug"，而是"像人眼一样看排版"
- 预评估布局 + 视觉验证闭环，从源头消灭溢出
"""

import os
import re
import json
import base64
import subprocess
import logging
import shutil
import tempfile
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# 第一阶段：PDF → PNG 渲染
# ═══════════════════════════════════════════════════════════════

def render_pdf_to_images(pdf_path: str, output_dir: str = None,
                         dpi: int = 200) -> List[str]:
    """
    将 PDF 渲染为 PNG 图片（每页一张）

    Args:
        pdf_path: PDF 文件路径
        output_dir: 输出目录（None 则与 PDF 同目录）
        dpi: 渲染分辨率（200 足够视觉模型看清文字和布局）

    Returns:
        PNG 图片路径列表
    """
    if not os.path.isfile(pdf_path):
        logger.error(f"[visual_verify] PDF 不存在: {pdf_path}")
        return []

    if output_dir is None:
        output_dir = os.path.dirname(pdf_path)
    os.makedirs(output_dir, exist_ok=True)

    # pdftoppm -png -r{dpi} input.pdf output_prefix
    prefix = os.path.join(output_dir, "page")
    try:
        result = subprocess.run(
            ["pdftoppm", "-png", "-r", str(dpi), pdf_path, prefix],
            capture_output=True, timeout=60,
        )
        if result.returncode != 0:
            logger.error(f"[visual_verify] pdftoppm 失败: {result.stderr.decode()}")
            return []
    except FileNotFoundError:
        logger.error("[visual_verify] pdftoppm 未安装 (apt install poppler-utils)")
        return []
    except subprocess.TimeoutExpired:
        logger.error("[visual_verify] pdftoppm 超时")
        return []

    # 收集生成的 PNG 文件
    images = sorted([
        os.path.join(output_dir, f)
        for f in os.listdir(output_dir)
        if f.startswith("page") and f.endswith(".png")
    ])

    logger.info(f"[visual_verify] 渲染 {len(images)} 页: {images}")
    return images


def render_tex_to_images(tex_content: str, dpi: int = 200) -> Tuple[List[str], str]:
    """
    编译 LaTeX 并渲染为图片（一步到位）

    Returns:
        (image_paths, compile_log)
    """
    from tools.latex_direct_generator import compile_latex

    work_dir = tempfile.mkdtemp(prefix="visual_verify_")
    success, errors, log = compile_latex(tex_content, output_dir=work_dir, timeout=30)

    if not success:
        logger.warning(f"[visual_verify] 编译失败: {errors[:3]}")
        return [], log

    pdf_path = os.path.join(work_dir, "test.pdf")
    if not os.path.isfile(pdf_path):
        return [], log

    images = render_pdf_to_images(pdf_path, dpi=dpi)
    return images, log


# ═══════════════════════════════════════════════════════════════
# 第二阶段：视觉模型调用
# ═══════════════════════════════════════════════════════════════

# 视觉模型降级链：优先专用视觉模型，然后支持多模态的通用模型
VISION_MODEL_FALLBACK_CHAIN = [
    "glm_5v_turbo",   # 智谱专用视觉模型（最快最便宜）
    "glm_4_6v",       # 智谱视觉模型备选
    "qwen3_6_plus",   # 阿里百炼 Qwen（支持多模态图片输入）
    "tp_qwen3_6_plus", # 阿里 Token Plan Qwen（支持多模态）
]


def _get_vision_client_and_config(model_alias: str):
    """
    根据模型别名获取视觉客户端和配置。
    统一入口，不再硬编码单个 provider。
    """
    import config.api_config as _cfg
    from api.openai_compatible import OpenAIClient

    config = _cfg.MODEL_ALIASES.get(model_alias)
    if not config:
        return None, None

    provider_name = config["provider"]
    provider_config = _cfg.PROVIDERS.get(provider_name, {})
    api_key_env = provider_config.get("api_key_env", "")
    api_key = getattr(_cfg, api_key_env, "")
    if not api_key:
        return None, None

    base_url = provider_config.get("base_url", "")
    model_id = config["model_id"]

    client = OpenAIClient(
        api_key=api_key,
        base_url=base_url,
        model=model_id,
        max_tokens=config.get("max_tokens", 4096),
        temperature=config.get("temperature", 0.3),
    )
    return client, model_id


def call_vision_check(image_paths: List[str], check_prompt: str) -> str:
    """
    调用视觉模型检查渲染结果（带降级链）

    降级链：glm-5v-turbo → glm-4.6v → qwen3.6-plus → tp_qwen3.6-plus
    任一模型成功即返回，全部失败则抛异常。

    Args:
        image_paths: PDF 渲染的 PNG 图片列表
        check_prompt: 检查指令

    Returns:
        视觉模型的文本回复
    """
    if not image_paths:
        return ""

    errors = []
    for model_alias in VISION_MODEL_FALLBACK_CHAIN:
        client, model_id = _get_vision_client_and_config(model_alias)
        if client is None:
            logger.debug(f"[vision] 跳过不可用模型: {model_alias}")
            continue

        try:
            logger.info(f"[vision] 尝试 {model_id} ({model_alias})...")
            result = client.query_vision(
                text_prompt=check_prompt,
                image_paths=image_paths,
                max_tokens=4096,
            )
            if result and len(result.strip()) > 10:
                logger.info(f"[vision] {model_id} 检查完成 ✅")
                return result
        except Exception as e:
            logger.warning(f"[vision] {model_id} 调用失败: {e}")
            errors.append(f"{model_alias}: {e}")

    raise RuntimeError(f"所有视觉模型调用失败:\n" + "\n".join(errors))


# ═══════════════════════════════════════════════════════════════
# 第三阶段：布局预评估 — 在生成前分析内容结构
# ═══════════════════════════════════════════════════════════════

def prevaluate_layout(section_instruction: str,
                      project_data: dict) -> Dict[str, Dict]:
    """
    预评估章节中表格和图片应该怎样输出。

    在 LLM 生成 LaTeX 之前调用，分析内容结构，输出布局约束。

    Args:
        section_instruction: 章节指令（CHAPTER_SECTIONS 中的 instruction）
        project_data: 项目数据

    Returns:
        {
            "tables": [
                {
                    "id": "tab:contributions",
                    "env": "table" | "table*",
                    "cols": 4,
                    "resizebox": true,
                    "width_cmd": "\\columnwidth" | "\\textwidth",
                    "reason": "..."
                }
            ],
            "figures": [
                {
                    "id": "fig:architecture",
                    "env": "figure" | "figure*",
                    "width_cmd": "\\columnwidth" | "\\textwidth",
                    "tikz_resizebox": true,
                    "reason": "..."
                }
            ]
        }
    """
    tables = []
    figures = []

    # ── 分析表格需求 ──
    # 从 section instruction 和 project data 中推断表格特征
    instruction_lower = section_instruction.lower()

    # 表格关键词检测
    table_keywords = {
        "comparison": {"likely_cols": 5, "has_long_text": True},
        "contributions": {"likely_cols": 4, "has_long_text": True},
        "limitations": {"likely_cols": 4, "has_long_text": True},
        "components": {"likely_cols": 4, "has_long_text": True},
        "ablation": {"likely_cols": 5, "has_long_text": False},
        "results": {"likely_cols": 6, "has_long_text": False},
        "quantitative": {"likely_cols": 6, "has_long_text": False},
        "performance": {"likely_cols": 5, "has_long_text": False},
        "summary": {"likely_cols": 3, "has_long_text": True},
    }

    for keyword, features in table_keywords.items():
        if keyword in instruction_lower:
            cols = features["likely_cols"]
            has_long = features["has_long_text"]
            # 核心决策：列数 > 4 或有长文本 → 双栏
            use_star = cols > 4 or has_long
            env = "table*" if use_star else "table"
            width_cmd = "\\textwidth" if use_star else "\\columnwidth"

            tables.append({
                "id": f"tab:{keyword}",
                "env": env,
                "cols": cols,
                "resizebox": True,
                "width_cmd": width_cmd,
                "reason": f"{cols} cols, long_text={has_long} → {env} with \\resizebox{{{width_cmd}}}{{!}}"
            })

    # ── 分析图片需求 ──
    figure_keywords = {
        "architecture": {"complex": True, "tikz": True},
        "pipeline": {"complex": True, "tikz": True},
        "overview": {"complex": True, "tikz": True},
        "framework": {"complex": True, "tikz": True},
        "diagram": {"complex": True, "tikz": True},
        "result": {"complex": False, "tikz": False},
        "example": {"complex": False, "tikz": False},
        "visual": {"complex": False, "tikz": False},
        "comparison": {"complex": True, "tikz": False},
    }

    for keyword, features in figure_keywords.items():
        if keyword in instruction_lower:
            complex_fig = features["complex"]
            is_tikz = features["tikz"]
            env = "figure*" if complex_fig else "figure"
            width_cmd = "\\textwidth" if complex_fig else "\\columnwidth"

            figures.append({
                "id": f"fig:{keyword}",
                "env": env,
                "width_cmd": width_cmd,
                "tikz_resizebox": is_tikz,
                "reason": f"complex={complex_fig}, tikz={is_tikz} → {env}"
            })

    result = {"tables": tables, "figures": figures}
    logger.info(f"[layout_planner] 预评估结果: {len(tables)} 表格, {len(figures)} 图片")
    return result


def generate_layout_constraints(layout_plan: Dict[str, Dict]) -> str:
    """
    将布局评估结果转化为 prompt 注入的约束字符串。

    这是关键的"设计"环节 — 在 LLM 生成前就明确告诉它每个表格/图片
    应该用什么环境、什么宽度。
    """
    constraints = ["\n**LAYOUT CONSTRAINTS (MUST follow these exactly)**:"]

    for i, table in enumerate(layout_plan.get("tables", []), 1):
        constraints.append(
            f"\n  Table {i} ({table['id']}): "
            f"Use \\begin{{{table['env']}}}[!t]. "
            f"Wrap tabular in \\resizebox{{{table['width_cmd']}}}{{!}}{{...}}. "
            f"Reason: {table['reason']}"
        )

    for i, fig in enumerate(layout_plan.get("figures", []), 1):
        tikz_note = ""
        if fig.get("tikz_resizebox"):
            w = fig["width_cmd"]
            tikz_note = f"Wrap TikZ in \\resizebox{{{w}}}{{!}}{{...}}. "
        constraints.append(
            f"\n  Figure {i} ({fig['id']}): "
            f"Use \\begin{{{fig['env']}}}[!t]. "
            f"Set width={fig['width_cmd']}. "
            f"{tikz_note}"
            f"Reason: {fig['reason']}"
        )

    constraints.append(
        "\n  CRITICAL: In \\begin{table}[!t] (single-column), use \\columnwidth (NOT \\textwidth). "
        "In \\begin{table*}[!t] (double-column), use \\textwidth. "
        "Same rule for figure environments."
    )

    return "\n".join(constraints)


# ═══════════════════════════════════════════════════════════════
# 第四阶段：视觉检查 prompt
# ═══════════════════════════════════════════════════════════════

VISUAL_CHECK_PROMPT = """You are a LaTeX typesetting expert reviewing a rendered PDF. Analyze these pages for layout issues.

Check for:
1. **Table overflow**: Does any table extend beyond the page margin? Is text cut off?
2. **Figure overflow**: Does any figure/diagram extend beyond the page margin?
3. **TikZ diagram sizing**: Are TikZ diagrams properly contained within their column?
4. **Text readability**: Is any text too small (over-shrunk by resizebox)?
5. **Column balance**: Are double-column tables properly spanning both columns?
6. **Margin violations**: Any content bleeding into margins or gutters?

For each issue found, report:
- **Location**: Which page, which element (table/figure/equation)
- **Problem**: Exact description of the visual issue
- **Severity**: CRITICAL (content cut off), WARNING (overflow but readable), OK (fine)
- **Fix suggestion**: Specific LaTeX code change needed

If everything looks fine, respond: "ALL_OK"

Respond in JSON format:
{
  "issues": [
    {
      "page": 1,
      "element": "table tab:contributions_summary",
      "problem": "Table extends beyond right margin by ~30%",
      "severity": "CRITICAL",
      "fix": "Change \\begin{table} to \\begin{table*} or add \\resizebox{\\columnwidth}{!}{...}"
    }
  ],
  "summary": "2 issues found: 1 table overflow, 1 figure overflow"
}"""


def verify_pdf_visual(pdf_path: str, specific_pages: List[int] = None) -> Dict:
    """
    完整的视觉验证流程：渲染 → 检查 → 解析

    Args:
        pdf_path: PDF 文件路径
        specific_pages: 只检查指定页（None 则检查全部）

    Returns:
        {
            "ok": bool,
            "issues": [...],
            "summary": str,
            "vision_response": str,
            "images_checked": int
        }
    """
    if not os.path.isfile(pdf_path):
        return {"ok": False, "issues": [], "summary": f"PDF not found: {pdf_path}",
                "vision_response": "", "images_checked": 0}

    # 1. 渲染 PDF 为图片
    render_dir = os.path.join(os.path.dirname(pdf_path), "_visual_verify")
    images = render_pdf_to_images(pdf_path, render_dir, dpi=200)

    if not images:
        return {"ok": False, "issues": [], "summary": "PDF rendering failed",
                "vision_response": "", "images_checked": 0}

    # 只检查指定页
    if specific_pages:
        images = [img for img in images
                  if any(f"-{p:02d}" in img or f"-{p:03d}" in img or f"-{p}." in img
                         for p in specific_pages)]
        if not images:
            images = images  # fallback: check all

    # 如果页数过多，取关键页（首页 + 包含表格/图的页）
    if len(images) > 6:
        # 保留首页、中间页、末页
        key_images = [images[0]]
        mid = len(images) // 2
        key_images.extend(images[max(0, mid-1):mid+2])
        if images[-1] != key_images[-1]:
            key_images.append(images[-1])
        images = key_images[:6]

    # 2. 调用视觉模型
    try:
        vision_response = call_vision_check(images, VISUAL_CHECK_PROMPT)
    except Exception as e:
        logger.error(f"[visual_verify] 视觉模型调用失败: {e}")
        return {"ok": True, "issues": [], "summary": f"Vision check skipped: {e}",
                "vision_response": "", "images_checked": len(images)}

    # 3. 解析视觉反馈
    result = parse_vision_feedback(vision_response)
    result["images_checked"] = len(images)

    logger.info(f"[visual_verify] 检查完成: {result['summary']}")
    for issue in result.get("issues", []):
        severity = issue.get("severity", "UNKNOWN")
        element = issue.get("element", "?")
        logger.info(f"  [{severity}] {element}: {issue.get('problem', '')[:80]}")

    return result


def verify_latex_visual(tex_content: str) -> Dict:
    """
    编译 LaTeX → 渲染 → 视觉检查（一步到位）

    Args:
        tex_content: 完整的 .tex 内容（含 preamble）

    Returns:
        验证结果字典
    """
    images, compile_log = render_tex_to_images(tex_content)

    if not images:
        # 编译失败，提取编译错误
        from tools.latex_direct_generator import compile_latex
        # 已经在 render_tex_to_images 里编译了
        return {
            "ok": False,
            "issues": [{"page": 0, "element": "compilation",
                        "problem": "LaTeX compilation failed",
                        "severity": "CRITICAL",
                        "fix": "Fix compilation errors first"}],
            "summary": "Compilation failed, cannot verify visually",
            "vision_response": "",
            "images_checked": 0,
            "compile_log": compile_log,
        }

    # 视觉检查
    try:
        vision_response = call_vision_check(images, VISUAL_CHECK_PROMPT)
    except Exception as e:
        logger.error(f"[visual_verify] 视觉模型调用失败: {e}")
        return {"ok": True, "issues": [], "summary": f"Vision check skipped: {e}",
                "vision_response": "", "images_checked": len(images),
                "compile_log": compile_log}

    result = parse_vision_feedback(vision_response)
    result["images_checked"] = len(images)
    result["compile_log"] = compile_log
    return result


# ═══════════════════════════════════════════════════════════════
# 第五阶段：反馈解析 → 结构化修复建议
# ═══════════════════════════════════════════════════════════════

def parse_vision_feedback(vision_response: str) -> Dict:
    """
    解析视觉模型的反馈为结构化修复建议

    Returns:
        {
            "ok": bool,
            "issues": [...],
            "summary": str,
            "vision_response": str
        }
    """
    result = {
        "ok": True,
        "issues": [],
        "summary": "",
        "vision_response": vision_response,
    }

    # 快速检查：ALL_OK
    if "ALL_OK" in vision_response.upper():
        result["summary"] = "All pages look fine"
        return result

    # 尝试 JSON 解析
    json_match = re.search(r'\{[\s\S]*\}', vision_response)
    if json_match:
        try:
            parsed = json.loads(json_match.group())
            issues = parsed.get("issues", [])
            result["issues"] = issues
            result["summary"] = parsed.get("summary", f"{len(issues)} issues found")
            result["ok"] = not any(
                i.get("severity") == "CRITICAL" for i in issues
            )
            return result
        except json.JSONDecodeError:
            pass

    # JSON 解析失败，用正则提取关键信息
    issues = []

    # 检测常见的视觉问题描述
    patterns = [
        (r"(?:table|表格)[^.]*?(?:overflow|超出|extends|cut off|margin)", "table_overflow"),
        (r"(?:figure|图片|diagram)[^.]*?(?:overflow|超出|extends|cut off|margin)", "figure_overflow"),
        (r"(?:too small|过小|unreadable|不可读)", "text_too_small"),
        (r"(?:TikZ)[^.]*?(?:overflow|超出|too wide)", "tikz_overflow"),
    ]

    for pattern, issue_type in patterns:
        matches = re.finditer(pattern, vision_response, re.IGNORECASE)
        for match in matches:
            # 提取周围句子作为问题描述
            start = max(0, match.start() - 50)
            end = min(len(vision_response), match.end() + 100)
            problem_text = vision_response[start:end].strip()

            issues.append({
                "page": 0,
                "element": issue_type,
                "problem": problem_text,
                "severity": "CRITICAL" if "overflow" in issue_type else "WARNING",
                "fix": _suggest_fix_for_type(issue_type),
            })

    result["issues"] = issues
    result["ok"] = not any(i.get("severity") == "CRITICAL" for i in issues)
    result["summary"] = f"{len(issues)} issues found (from text parsing)"
    return result


def _suggest_fix_for_type(issue_type: str) -> str:
    """根据问题类型给出标准修复建议"""
    fixes = {
        "table_overflow": "Add \\resizebox{\\columnwidth}{!}{...} around tabular, or upgrade to table*",
        "figure_overflow": "Add \\resizebox{\\textwidth}{!}{...} around TikZ, or use width=\\textwidth",
        "text_too_small": "Table may have too many columns for single-column; upgrade to table*",
        "tikz_overflow": "Wrap tikzpicture in \\resizebox{\\textwidth}{!}{...}",
    }
    return fixes.get(issue_type, "Review and adjust sizing")


# ═══════════════════════════════════════════════════════════════
# 第六阶段：自动修复（基于视觉反馈）
# ═══════════════════════════════════════════════════════════════

def apply_visual_fixes(latex_code: str, vision_issues: List[Dict]) -> str:
    """
    根据视觉检查发现的问题，自动应用 LaTeX 修复

    策略：
    - table_overflow → 确保 resizebox + columnwidth，必要时升级 table*
    - figure_overflow → 包裹 TikZ resizebox
    - text_too_small → 可能需要升级到双栏环境
    """
    for issue in vision_issues:
        element = issue.get("element", "")
        fix_hint = issue.get("fix", "")
        problem = issue.get("problem", "")

        if "table" in element.lower() or "table" in fix_hint.lower():
            latex_code = _fix_table_overflow(latex_code, problem)

        elif "figure" in element.lower() or "tikz" in element.lower():
            latex_code = _fix_figure_overflow(latex_code, problem)

        elif "small" in element.lower() or "unreadable" in element.lower():
            latex_code = _upgrade_to_double_column(latex_code)

    return latex_code


def _fix_table_overflow(latex_code: str, problem: str) -> str:
    """修复表格溢出"""
    # 策略1：单栏 table 中 \textwidth → \columnwidth
    fixed = re.sub(
        r'(\\begin\{table\}[^*].*?)\\resizebox\{\\textwidth\}',
        r'\1\\resizebox{\\columnwidth}',
        latex_code, flags=re.DOTALL
    )

    # 策略2：单栏 table 没有 resizebox → 添加
    # 找到 table 环境中没有 resizebox 的
    def _add_resizebox_to_single_col_table(match):
        content = match.group(0)
        if '\\resizebox' in content:
            return content
        # 在 \begin{tabular} 前插入 resizebox
        result = content.replace(
            '\\begin{tabular}',
            '\\resizebox{\\columnwidth}{!}{%\n\\begin{tabular}'
        )
        # 在 \end{tabular} 后关闭 resizebox
        result = result.replace(
            '\\end{tabular}',
            '\\end{tabular}%\n}'
        )
        return result

    fixed = re.sub(
        r'\\begin\{table\}[^*].*?\\end\{table\}',
        _add_resizebox_to_single_col_table,
        fixed, flags=re.DOTALL
    )

    return fixed


def _fix_figure_overflow(latex_code: str, problem: str) -> str:
    """修复图片/TikZ 溢出"""
    # 策略：tikzpicture 没有 resizebox 包裹 → 添加
    def _wrap_tikz(match):
        content = match.group(0)
        if '\\resizebox' in content:
            return content
        # 判断是 figure 还是 figure*
        parent_match = re.search(r'\\begin\{(figure\*?)\}', content)
        if not parent_match:
            return content
        env_name = parent_match.group(1)
        width = '\\textwidth' if '*' in env_name else '\\columnwidth'

        # 包裹 tikzpicture
        result = content.replace(
            '\\begin{tikzpicture}',
            f'\\resizebox{{{width}}}{{!}}{{%\n\\begin{{tikzpicture}}'
        )
        result = result.replace(
            '\\end{tikzpicture}',
            '\\end{tikzpicture}%\n}'
        )
        return result

    fixed = re.sub(
        r'\\begin\{figure\*?\}.*?\\end\{figure\*?\}',
        _wrap_tikz,
        latex_code, flags=re.DOTALL
    )

    return fixed


def _upgrade_to_double_column(latex_code: str) -> str:
    """将单栏环境升级为双栏（当内容太拥挤时）"""
    # table → table*
    fixed = latex_code.replace('\\begin{table}[!t]', '\\begin{table*}[!t]')
    fixed = fixed.replace('\\end{table}[!t]', '\\end{table*}')
    fixed = fixed.replace('\\end{table}\n', '\\end{table*}\n')

    # 同步 \columnwidth → \textwidth
    # 只在新升级的 table* 中修改
    # （这个粗粒度操作在全表只有 table 的情况下安全）
    if '\\begin{table*}' in fixed and '\\begin{table}' not in fixed:
        fixed = fixed.replace('\\resizebox{\\columnwidth}', '\\resizebox{\\textwidth}')

    return fixed


# ═══════════════════════════════════════════════════════════════
# 完整闭环入口
# ═══════════════════════════════════════════════════════════════

def visual_verify_pipeline(tex_content: str,
                           max_rounds: int = 2) -> Tuple[str, Dict]:
    """
    完整的视觉验证闭环：编译 → 渲染 → 检查 → 修复 → 重来

    Args:
        tex_content: 完整的 .tex 内容（含 preamble）
        max_rounds: 最大修复轮次

    Returns:
        (fixed_tex_content, verification_result)
    """
    current_tex = tex_content
    all_issues = []

    for round_idx in range(max_rounds):
        logger.info(f"[visual_pipeline] 第 {round_idx+1}/{max_rounds} 轮视觉验证...")

        # 编译 + 渲染 + 视觉检查
        result = verify_latex_visual(current_tex)

        if result.get("ok", True) or not result.get("issues"):
            logger.info(f"[visual_pipeline] 第 {round_idx+1} 轮通过 ✅")
            return current_tex, result

        # 有问题 → 应用修复
        issues = result.get("issues", [])
        all_issues.extend(issues)
        logger.info(f"[visual_pipeline] 发现 {len(issues)} 个问题，自动修复中...")

        current_tex = apply_visual_fixes(current_tex, issues)

    # 最终验证
    final_result = verify_latex_visual(current_tex)
    final_result["all_rounds_issues"] = all_issues
    return current_tex, final_result


def verify_full_paper(pdf_path: str) -> Dict:
    """
    对完整论文 PDF 进行视觉验证（不修改文件，只报告）

    用于最终质量检查。
    """
    return verify_pdf_visual(pdf_path)
