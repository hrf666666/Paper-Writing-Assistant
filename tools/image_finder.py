# -*- coding: utf-8 -*-
"""
Tool: 图片查找器 v9.2 (Image Finder)

从目标项目的数据集中查找合适的对比场景图片，
用于生成定性对比网格图。

工作方式：
1. 发现数据集目录结构
2. 找到已有的结果图片（depth maps, analysis overlays 等）
3. 按场景/方法组织图片，供 generate_image_grid 使用
"""

import logging
import os
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def find_qualitative_images(
    project_path: str,
    max_scenes: int = 4,
    max_methods: int = 5,
) -> Dict:
    """
    查找可用于定性对比的图片。

    Args:
        project_path: 项目根目录
        max_scenes: 最多展示的场景数
        max_methods: 最多展示的方法数

    Returns:
        {
            "scenes": [
                {
                    "name": "scene_name",
                    "images": {
                        "input": "path/to/input.png",
                        "ground_truth": "path/to/gt.png",
                        "method_name": "path/to/result.png",
                        ...
                    }
                }
            ],
            "method_names": ["Method1", "Method2", ...],
            "grid_config": {
                "n_rows": 4,
                "n_cols": 5,
                "row_labels": [...],
                "col_labels": [...]
            }
        }
    """
    result = {
        "scenes": [],
        "method_names": [],
        "grid_config": {},
    }

    # 1. 搜索已有结果图片目录
    image_dirs = _find_image_dirs(project_path)

    # 2. 从 outputs/energy_maps/ 等目录收集图片
    organized = _organize_by_scene(image_dirs, max_scenes, max_methods)

    if organized["scenes"]:
        result = organized
        logger.info(
            f"[ImageFinder] 找到 {len(result['scenes'])} 个场景, "
            f"{len(result['method_names'])} 种方法"
        )
    else:
        # 3. 退而求其次：找任意有意义的分析图片
        fallback_images = _find_fallback_images(project_path)
        if fallback_images:
            result = _organize_fallback(fallback_images)

    return result


def get_grid_image_paths(qual_data: Dict) -> List[str]:
    """从 qual_data 中提取所有图片路径（按行排列）"""
    paths = []
    for scene in qual_data.get("scenes", []):
        images = scene.get("images", {})
        # 按 input → methods → ground_truth 的顺序
        if "input" in images:
            paths.append(images["input"])
        for method in qual_data.get("method_names", []):
            if method in images:
                paths.append(images[method])
        if "ground_truth" in images:
            paths.append(images["ground_truth"])
    return paths


def get_grid_titles(qual_data: Dict) -> List[str]:
    """从 qual_data 中提取列标题"""
    titles = ["Input"]
    titles.extend(qual_data.get("method_names", []))
    if qual_data.get("scenes") and "ground_truth" in qual_data["scenes"][0].get("images", {}):
        titles.append("Ground Truth")
    return titles


# ═══════════════════════════════════════════════════════════════
# 内部工具
# ═══════════════════════════════════════════════════════════════

def _find_image_dirs(project_path: str) -> List[str]:
    """找到可能包含结果图片的目录"""
    candidates = []
    search_patterns = [
        "outputs/energy_maps",
        "outputs/comparisons",
        "outputs/visualizations",
        "workspace",
        "analysis",
        "results",
        "figures",
    ]

    for pattern in search_patterns:
        dpath = os.path.join(project_path, pattern)
        if os.path.isdir(dpath):
            candidates.append(dpath)

    return candidates


def _organize_by_scene(
    image_dirs: List[str],
    max_scenes: int,
    max_methods: int,
) -> Dict:
    """按场景组织图片"""
    result = {
        "scenes": [],
        "method_names": [],
        "grid_config": {},
    }

    # 收集所有图片
    all_images = []
    for dpath in image_dirs:
        for root, dirs, files in os.walk(dpath):
            for f in files:
                if f.lower().endswith((".png", ".jpg", ".jpeg")):
                    all_images.append(os.path.join(root, f))

    if not all_images:
        return result

    # 尝试从文件名中提取场景名和方法名
    scene_map = {}
    method_set = set()

    for img_path in all_images:
        fname = os.path.basename(img_path).lower()
        dirname = os.path.basename(os.path.dirname(img_path))

        # 常见的命名模式
        # scene_method_metric.png 或 method_scene.png
        parts = fname.replace(".png", "").replace(".jpg", "").split("_")

        # 简单启发式：第一个部分通常是场景名或方法名
        scene_name = _extract_scene_name(fname, dirname)
        method_name = _extract_method_name(fname, dirname)

        if scene_name not in scene_map:
            scene_map[scene_name] = {}
        scene_map[scene_name][method_name] = img_path
        method_set.add(method_name)

    # 选取场景和方法
    method_names = sorted(method_set)[:max_methods]
    scenes = list(scene_map.keys())[:max_scenes]

    result["method_names"] = method_names
    result["scenes"] = []

    for scene_name in scenes:
        scene_data = {
            "name": scene_name,
            "images": {},
        }
        for method in method_names:
            if method in scene_map[scene_name]:
                scene_data["images"][method] = scene_map[scene_name][method]
        if scene_data["images"]:
            result["scenes"].append(scene_data)

    # Grid 配置
    n_cols = 1 + len(method_names) + (1 if any("ground_truth" in s.get("images", {}) for s in result["scenes"]) else 0)
    result["grid_config"] = {
        "n_rows": len(result["scenes"]),
        "n_cols": n_cols,
        "row_labels": [s["name"] for s in result["scenes"]],
        "col_labels": ["Input"] + method_names,
    }

    return result


def _extract_scene_name(fname: str, dirname: str) -> str:
    """从文件名提取场景名"""
    # 常见模式: HCInew_antinous, NL_David_50, UrbanLF_Image1
    import re

    # HCI 数据集
    match = re.search(r'(hci\w*|david\w*|apple\w*|antinous\w*|boxes\w*|urban\w*_image\d+)',
                      fname, re.IGNORECASE)
    if match:
        return match.group(0)

    # 从目录名推断
    if dirname and dirname not in (".", ".."):
        return dirname

    return fname.split("_")[0]


def _extract_method_name(fname: str, dirname: str) -> str:
    """从文件名提取方法名"""
    keywords = ["comparison", "depth", "gt", "input", "result", "overlay",
                "heatmap", "energy", "material", "decomposition", "epi",
                "ours", "baseline", "proposed"]

    for kw in keywords:
        if kw in fname:
            return kw.capitalize()

    return os.path.basename(dirname) if dirname else "Unknown"


def _find_fallback_images(project_path: str) -> List[str]:
    """找任意有意义的分析图片作为 fallback"""
    images = []
    priority_dirs = [
        os.path.join(project_path, "analysis"),
        os.path.join(project_path, "workspace"),
        os.path.join(project_path, "outputs"),
    ]

    for dpath in priority_dirs:
        if not os.path.isdir(dpath):
            continue
        for root, dirs, files in os.walk(dpath):
            # 优先找 summary/comparison 类型的图
            for f in sorted(files):
                if f.lower().endswith(".png"):
                    images.append(os.path.join(root, f))
                    if len(images) >= 12:
                        return images

    return images


def _organize_fallback(image_paths: List[str]) -> Dict:
    """将 fallback 图片组织为简单的网格结构"""
    n = len(image_paths)
    method_names = []
    for p in image_paths:
        name = os.path.basename(p).replace(".png", "")
        if len(name) > 20:
            name = name[:17] + "..."
        method_names.append(name)

    return {
        "scenes": [{
            "name": "Analysis Results",
            "images": {method_names[i]: image_paths[i] for i in range(n)},
        }],
        "method_names": method_names,
        "grid_config": {
            "n_rows": 1,
            "n_cols": n,
            "row_labels": ["Analysis"],
            "col_labels": method_names,
        },
    }
