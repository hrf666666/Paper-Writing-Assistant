# -*- coding: utf-8 -*-
"""figure_review — v17 画后视觉自检闭环（融合 figure-skill 思想 + zai_vision MCP）。

思想来源：scipilot-figure-skill 的"第6步：自检闭环（机器+AI读图）"——
出图后渲染预览→AI读图复核→发现问题回改→直到通过。

实现：用 zai_vision（stdio @z_ai/mcp-server）的专项视觉工具审视生成的图：
  - architecture/teaser/module_detail → understand_technical_diagram（技术图解读）
  - ablation/comparison → analyze_data_visualization（数据图提炼）
  - qualitative/其他 → analyze_image（通用）
专项工具比通用 query_vision 拼 JSON prompt 专业得多（实测：返回结构化的
模块布局/文字重叠/箭头合理性评估，而非硬凑 score+defects）。

闭环：审视→解析评分→达标(≥7)升 VALIDATED→不达标驱动 LLM 重修 TikZ→重编重评，
最多 MAX_REVIEW_ROUNDS 轮。失败时降级（保持 RENDERED，不阻塞 pipeline）。
"""
import os
import re
import json
import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# 视觉自检通过阈值（1-10）+ 重修轮次上限
REVIEW_PASS_SCORE = 7
MAX_REVIEW_ROUNDS = 2

# fig_type → zai_vision 专项工具
_FIG_TYPE_TOOLS = {
    "teaser": "understand_technical_diagram",
    "architecture": "understand_technical_diagram",
    "module_detail": "understand_technical_diagram",
    "ablation": "analyze_data_visualization",
    "comparison": "analyze_data_visualization",
    "qualitative": "analyze_image",
}


def _pick_tool(fig_type: str) -> str:
    """按 fig_type 选视觉工具。"""
    return _FIG_TYPE_TOOLS.get(fig_type, "analyze_image")


def _call_vision_tool(image_path: str, fig_type: str, key_message: str = "") -> Optional[str]:
    """调用对应的 zai_vision 专项工具。

    传本地绝对路径（stdio server 直接读本地文件，不用 data URL）。
    """
    tool = _pick_tool(fig_type)
    prompt = _build_review_prompt(fig_type, key_message)
    try:
        from api.mcp_http_client import (
            mcp_understand_diagram, mcp_analyze_data_viz, mcp_analyze_image,
        )
        if tool == "understand_technical_diagram":
            return mcp_understand_diagram(image_path, prompt)
        elif tool == "analyze_data_visualization":
            return mcp_analyze_data_viz(image_path, prompt)
        else:
            return mcp_analyze_image(image_path, prompt)
    except Exception as e:
        logger.warning(f"[figure_review] 视觉工具 {tool} 调用失败: {e}")
        return None


def _build_review_prompt(fig_type: str, key_message: str = "") -> str:
    """构建视觉审视 prompt（融合 scipilot-figure-skill 的 8 项读图清单 + viz_pitfalls）。

    figure-skill 精神：不要扫一眼说"看起来不错"——逐项核对，找出具体问题。
    8 项清单（visual_review.md）：乱码方框/文字裁切/文字遮盖重叠/子图对齐/
    子图间距/配色灰度/数据完整性/跨子图一致性。
    key_message（论证目标）：让视觉模型评估"图是否传达了它该传达的论点"。
    """
    km = f"\n本图必须传达的核心论点：{key_message}" if key_message else ""
    if fig_type in ("teaser", "architecture", "module_detail"):
        # 架构图：映射清单的相关项（无误差棒/刻度，侧重布局/文字/配色）
        return (
            f"这是 IEEE 论文的架构图。请逐项核对（不要泛泛说「看起来不错」）：{km}\n\n"
            "## 文字层\n"
            "1. 乱码/方框：有无缺字变方框、希腊字母/特殊符号丢失？\n"
            "2. 文字裁切：标题/标签/注释有无被画布边缘切掉？\n"
            "3. 文字遮盖重叠：模块标签有无互相叠？图例有无压住连线/节点？\n"
            "\n## 布局层\n"
            "4. 模块布局：层级是否清晰？有无拥挤或大量留白？\n"
            "5. 箭头/连线：方向是否合理？有无穿过节点、交叉混乱？\n"
            "6. 子图对齐（若多面板）：a/b/c 是否横竖对齐？风格一致？\n"
            "\n## 视觉层\n"
            "7. 配色：是否专业（避免饱和红绿对比，色盲友好）？视觉层次分明吗？\n"
            "8. 数据完整性：有无模块/连线被坐标范围切掉、画了一半？\n"
            "\n## 论证目标\n"
            "9. 图是否清晰传达了上述核心论点？读者 5 秒能看懂吗？\n\n"
            "逐项给结论后，给出总体评分: N/10（10=完美，7=可用，<7=需重修）。"
            "并列出需改进的具体问题（每条指明位置）。用中文回答。"
        )
    elif fig_type in ("ablation", "comparison"):
        # 数据图：完整 8 项 + viz_pitfalls（均值柱/误差交代/色盲/rainbow）
        return (
            f"这是 IEEE 论文的数据图。请逐项核对（科研可视化避坑视角）：{km}\n\n"
            "## 文字层\n"
            "1. 乱码/方框：负号/±/μ/Δ 等有无缺字？\n"
            "2. 文字裁切：轴标签/图例/数值标注有无被切？\n"
            "3. 文字遮盖：图例有无压数据？刻度标签有无挤成一团？\n"
            "\n## 数据层\n"
            "4. 误差交代：有误差棒/阴影吗？图注是否说明类型(SD/SEM/CI)+n？\n"
            "5. 均值柱陷阱（viz_pitfalls P1）：n<10 却画均值柱？建议改箱线+stripplot？\n"
            "6. Y轴截断（P4）：比例图Y轴不从0起会误导？\n"
            "\n## 视觉层\n"
            "7. 配色/灰度：色盲友好吗？类别有无冗余编码（线型/marker）？\n"
            "8. 色图（P14）：用了 rainbow/jet？建议 viridis/magma？\n"
            "9. 数据完整：误差棒顶端/最高柱/最外点是否都在框内？\n"
            "\n## 论证目标\n"
            "10. 图是否清晰传达了核心论点？\n\n"
            "逐项给结论后，给出总体评分: N/10，并列出需改进的具体问题。用中文回答。"
        )
    else:
        return (
            f"这是 IEEE 论文的插图。请逐项核对（乱码/裁切/遮盖/配色/数据完整/论证目标）：{km}\n"
            "最后给出总体评分: N/10，并列出具体问题。用中文回答。"
        )


def _parse_score(review_text: str) -> Tuple[int, list]:
    """从视觉审视文本中解析评分和问题列表。

    视觉模型返回的是自然语言（不是硬凑 JSON），所以用正则提取"总体评分: N"。
    返回 (score, issues)。解析失败返回 (5, [])——不阻塞，偏向保守。
    """
    if not review_text:
        return 5, []
    # 提取评分：匹配 "总体评分: 8/10" / "评分：7" / "score: 8" 等
    m = re.search(r'(?:总体评分|评分|score|Score)\s*[:：]\s*(\d+)\s*(?:/\s*10)?', review_text)
    score = int(m.group(1)) if m else 5
    score = max(1, min(10, score))  # 钳制到 1-10
    # 提取问题：含"问题"/"改进"/"需"/"缺陷"的行
    issues = []
    for line in review_text.split('\n'):
        line = line.strip()
        if any(kw in line for kw in ('问题', '改进', '需要', '建议', '缺陷', '重叠', '溢出', '裁切', 'issue', 'improve', 'fix')):
            if len(line) > 5:
                issues.append(line[:120])
    return score, issues[:5]


def review_figure(png_path: str, fig_plan: dict) -> Dict:
    """对生成的图做视觉自检。

    Args:
        png_path: 生成的 PNG 预览路径
        fig_plan: figure_plan 里的图定义（含 fig_type, key_message, fig_id）

    Returns:
        {
            "score": int 1-10,
            "passed": bool,          # score >= REVIEW_PASS_SCORE
            "issues": list[str],     # 发现的问题
            "review_text": str,      # 完整审视文本（供重修参考）
            "tool": str,             # 用的视觉工具
            "available": bool,       # zai_vision 是否可用（False 时跳过）
        }
    """
    fig_type = fig_plan.get("fig_type", "architecture")
    fig_id = fig_plan.get("fig_id", "fig")
    key_message = fig_plan.get("key_message", "")
    tool = _pick_tool(fig_type)

    # 检查 zai_vision 可用性
    try:
        from api.mcp_http_client import mcp_vision_available
        if not mcp_vision_available():
            logger.info(f"[figure_review] {fig_id}: zai_vision 不可用，跳过视觉自检")
            return {"score": 0, "passed": True, "issues": [], "review_text": "",
                    "tool": tool, "available": False}
    except Exception:
        return {"score": 0, "passed": True, "issues": [], "review_text": "",
                "tool": tool, "available": False}

    # 检查图片存在
    if not png_path or not os.path.exists(png_path):
        logger.warning(f"[figure_review] {fig_id}: PNG 不存在 {png_path}，跳过")
        return {"score": 0, "passed": True, "issues": [], "review_text": "",
                "tool": tool, "available": False}

    # 调视觉工具
    review_text = _call_vision_tool(png_path, fig_type, key_message)
    if not review_text:
        logger.warning(f"[figure_review] {fig_id}: 视觉工具无返回，降级跳过")
        return {"score": 0, "passed": True, "issues": [], "review_text": "",
                "tool": tool, "available": False}

    score, issues = _parse_score(review_text)
    passed = score >= REVIEW_PASS_SCORE
    logger.info(f"[figure_review] {fig_id} ({fig_type}): 视觉评分 {score}/10 "
                f"{'✓ 通过' if passed else '✗ 需改进'} ({tool})")
    if issues:
        for iss in issues[:3]:
            logger.info(f"  - {iss}")

    return {
        "score": score, "passed": passed, "issues": issues,
        "review_text": review_text, "tool": tool, "available": True,
    }
