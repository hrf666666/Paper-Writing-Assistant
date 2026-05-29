# -*- coding: utf-8 -*-
"""
Skill: 工程代码分析器
遍历项目实验工程代码，提炼核心创新点、模型/方法设计、实验设计、实验分析
"""

import os
import json
import re
from pathlib import Path
from tqdm import tqdm

from config.project_config import PROJECT_CODE_PATH, OUTPUT_DIR
from agent.base_orchestrator import BaseOrchestrator

import logging
logger = logging.getLogger(__name__)

# 基类实例：统一 LLM 调用、JSON 解析、文件保存
_orch = BaseOrchestrator(output_dir=OUTPUT_DIR)


# 关键文件名模式（用于识别工程代码中的核心文件）
KEY_FILE_PATTERNS = {
    "final_report": ["Final_Report", "Final_Project_Report", "PROJECT_REPORT"],
    "closure_report": ["Project_Closure_Report", "CLOSURE_REPORT"],
    "project_brief": ["PROJECT_BRIEF", "Project_Brief", "README"],
    "model_code": ["model", "network", "architecture", "module"],
    "train_script": ["train", "main", "run"],
    "eval_script": ["eval", "test", "validate", "validation"],
    "dataset": ["dataset", "dataloader", "data"],
    "config": ["config", "cfg", "setting", "hyperparameter"],
    "loss": ["loss", "criterion"],
    "utils": ["utils", "helper", "tool"],
}


def _classify_file(filepath):
    """根据文件名判断文件类别"""
    name = Path(filepath).stem.lower()
    for category, patterns in KEY_FILE_PATTERNS.items():
        for pattern in patterns:
            if pattern.lower() in name:
                return category
    return "other"


def scan_project_code(project_path):
    """扫描项目代码目录，收集所有源文件并分类"""
    project_path = Path(project_path)
    if not project_path.exists():
        logger.warning(f"[project_analyzer] 项目路径不存在: {project_path}")
        return {}
    
    file_inventory = {
        "final_report": [],
        "closure_report": [],
        "project_brief": [],
        "model_code": [],
        "train_script": [],
        "eval_script": [],
        "dataset": [],
        "config": [],
        "loss": [],
        "utils": [],
        "other": [],
    }
    
    # 支持的文件扩展名
    supported_exts = {".py", ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".cfg"}
    
    for root, dirs, files in os.walk(project_path):
        # 跳过隐藏目录和常见无用目录
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in 
                   ['__pycache__', 'node_modules', '.git', 'archive', 'logs', 'wandb', 'checkpoints']]
        for f in files:
            filepath = Path(root) / f
            if filepath.suffix in supported_exts:
                category = _classify_file(filepath)
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as fh:
                        content = fh.read()
                    file_inventory[category].append({
                        "path": str(filepath.relative_to(project_path)),
                        "content": content,
                        "size": len(content),
                    })
                except Exception:
                    pass
    
    return file_inventory


def extract_project_info(file_inventory):
    """从工程代码中提取项目核心信息"""
    
    # 1. 读取报告类文件（Final_Report, Closure_Report, PROJECT_BRIEF）
    report_content = ""
    for category in ["final_report", "closure_report", "project_brief"]:
        for item in file_inventory.get(category, []):
            report_content += f"\n--- {category}: {item['path']} ---\n{item['content']}\n"
    
    # 2. 读取模型代码
    model_content = ""
    for item in file_inventory.get("model_code", []):
        model_content += f"\n--- model: {item['path']} ---\n{item['content']}\n"
    
    # 3. 读取训练和评估脚本
    train_content = ""
    for category in ["train_script", "eval_script"]:
        for item in file_inventory.get(category, []):
            train_content += f"\n--- {category}: {item['path']} ---\n{item['content']}\n"
    
    # 4. 读取损失函数和配置
    loss_config_content = ""
    for category in ["loss", "config"]:
        for item in file_inventory.get(category, []):
            loss_config_content += f"\n--- {category}: {item['path']} ---\n{item['content']}\n"
    
    # 5. 读取数据集相关
    dataset_content = ""
    for item in file_inventory.get("dataset", []):
        dataset_content += f"\n--- dataset: {item['path']} ---\n{item['content']}\n"
    
    return {
        "report_content": report_content,
        "model_content": model_content,
        "train_content": train_content,
        "loss_config_content": loss_config_content,
        "dataset_content": dataset_content,
    }


def extract_innovation_points(project_info, paper_title):
    """提炼核心创新点"""
    prompt = f"""
    你是一名人工智能与计算机领域的资深审稿专家。
    以下是一篇标题为"{paper_title}"的论文的实验工程代码和相关报告。
    
    请从以下材料中提炼出2-3个核心创新点。每个创新点需要包含：
    1. 创新点名称
    2. 创新点所包含的具体工作内容（详细描述）
    3. 创新点的价值和意义
    4. 支撑该创新点的关键代码/实验证据
    
    <report_content>
    {project_info['report_content'][:8000]}
    </report_content>
    
    <model_content>
    {project_info['model_content'][:8000]}
    </model_content>
    
    <loss_config_content>
    {project_info['loss_config_content'][:4000]}
    </loss_config_content>
    
    请以json-list格式给出，每个dict包含"创新点名称"、"创新点工作内容"(list)、"创新点价值"、"支撑证据"四个字段。
    回复以```json开头，以```结尾，无需添加任何解释说明。
    """
    
    innovation_points = _orch.parse_json_with_retry(
        prompt, call_method="call_reasoning", expected_type=list,
        default=[{"创新点名称": "核心方法创新", "创新点工作内容": ["待补充"], "创新点价值": "待补充", "支撑证据": "待补充"}]
    )
    
    return innovation_points


def extract_model_architecture(project_info, paper_title):
    """提炼模型架构设计"""
    prompt = f"""
    你是一名深度学习架构设计专家。
    以下是一篇标题为"{paper_title}"的论文的模型代码和实验报告。
    
    请详细描述该论文的模型架构，包括：
    1. 总体架构：输入什么，经过哪些模块处理，提取了哪些特征，做了哪些处理过程，最终输出什么
    2. 各模块的详细设计：每个模块的输入输出维度、核心操作、关键公式
    3. 模块之间的连接方式和数据流
    4. 关键超参数及其设置
    
    <model_content>
    {project_info['model_content'][:12000]}
    </model_content>
    
    <loss_config_content>
    {project_info['loss_config_content'][:4000]}
    </loss_config_content>
    
    <train_content>
    {project_info['train_content'][:4000]}
    </train_content>
    
    请以json格式给出，包含"总体架构"(str)、"模块详情"(list, 每个元素包含"模块名"、"输入"、"核心操作"、"输出"、"关键公式")、"模块连接"(str)、"关键超参数"(dict)。
    回复以```json开头，以```结尾，无需添加任何解释说明。
    """
    
    return _orch.parse_json_with_retry(
        prompt, call_method="call_reasoning",
        default={"总体架构": "待补充", "模块详情": [], "模块连接": "待补充", "关键超参数": {}}
    )


def extract_experiment_design(project_info, paper_title):
    """提炼实验设计"""
    prompt = f"""
    你是一名实验设计专家。
    以下是一篇标题为"{paper_title}"的论文的实验报告和训练代码。
    
    请详细梳理实验设计，包括：
    1. 使用的数据集及其描述（名称、规模、场景类型、划分方式）
    2. 评估指标及目标值
    3. 训练策略（优化器、学习率、batch size、epoch等）
    4. 对比方法（baselines）
    5. 消融实验设计（哪些模块被消融、对比方式）
    6. 关键实验结果
    
    <report_content>
    {project_info['report_content'][:8000]}
    </report_content>
    
    <train_content>
    {project_info['train_content'][:4000]}
    </train_content>
    
    <dataset_content>
    {project_info['dataset_content'][:4000]}
    </dataset_content>
    
    请以json格式给出，包含上述6个字段（"数据集"、"评估指标"、"训练策略"、"对比方法"、"消融设计"、"关键结果"）。
    回复以```json开头，以```结尾，无需添加任何解释说明。
    """
    
    return _orch.parse_json_with_retry(
        prompt, call_method="call_reasoning",
        default={
            "数据集": [], "评估指标": [], "训练策略": {},
            "对比方法": [], "消融设计": [], "关键结果": {}
        }
    )


def run_project_analyzer():
    """主入口：运行工程代码分析器"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    from config.project_config import PAPER_TITLE
    
    logger.info("[project_analyzer] 步骤1: 扫描项目工程代码...")
    try:
        file_inventory = scan_project_code(PROJECT_CODE_PATH)
    except Exception as e:
        logger.error(f"[project_analyzer] 步骤1 扫描失败: {e}")
        file_inventory = {}
    
    # 保存文件清单
    try:
        inventory_summary = {}
        for category, files in file_inventory.items():
            inventory_summary[category] = [{"path": f["path"], "size": f["size"]} for f in files]
        _orch.save_output("file_inventory.json", inventory_summary)
    except Exception as e:
        logger.error(f"[project_analyzer] 保存文件清单失败: {e}")
    
    logger.info(f"[project_analyzer] 扫描完成，共发现 {sum(len(v) for v in file_inventory.values())} 个文件")
    
    logger.info("[project_analyzer] 步骤2: 提取项目核心信息...")
    try:
        project_info = extract_project_info(file_inventory)
        _orch.save_output("project_info.json", {k: v[:2000] for k, v in project_info.items()})
    except Exception as e:
        logger.error(f"[project_analyzer] 步骤2 提取失败: {e}")
        project_info = {"report_content": "", "model_content": "", "train_content": "", "loss_config_content": "", "dataset_content": ""}
    
    logger.info("[project_analyzer] 步骤3: 提炼核心创新点...")
    try:
        innovation_points = extract_innovation_points(project_info, PAPER_TITLE)
        _orch.save_output("innovation_points.json", innovation_points)
    except Exception as e:
        logger.error(f"[project_analyzer] 步骤3 提炼失败: {e}")
        innovation_points = []
    
    logger.info("[project_analyzer] 步骤4: 提炼模型架构...")
    try:
        model_architecture = extract_model_architecture(project_info, PAPER_TITLE)
        _orch.save_output("model_architecture.json", model_architecture)
    except Exception as e:
        logger.error(f"[project_analyzer] 步骤4 提炼失败: {e}")
        model_architecture = {}
    
    logger.info("[project_analyzer] 步骤5: 提炼实验设计...")
    try:
        experiment_design = extract_experiment_design(project_info, PAPER_TITLE)
        _orch.save_output("experiment_design.json", experiment_design)
    except Exception as e:
        logger.error(f"[project_analyzer] 步骤5 提炼失败: {e}")
        experiment_design = {}
    
    logger.info("[project_analyzer] 分析完成！结果已保存至 output/ 目录")
    
    return {
        "innovation_points": innovation_points,
        "model_architecture": model_architecture,
        "experiment_design": experiment_design,
        "project_info": project_info,
    }


if __name__ == "__main__":
    results = run_project_analyzer()
    logger.info("=== 创新点 ===")
    for ip in results["innovation_points"]:
        logger.info(f"  - {ip.get('创新点名称', 'N/A')}: {ip.get('创新点价值', 'N/A')}")
