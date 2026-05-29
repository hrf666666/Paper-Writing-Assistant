# -*- coding: utf-8 -*-
"""
Tool: 消融实验运行器
设计并运行消融实验，代码放在 workspace/ablation_test/code，图表放在 workspace/ablation_test/fig
"""

import os
import json
import re
import shutil
from pathlib import Path

from config.project_config import (
    PAPER_TITLE, OUTPUT_DIR, WORKSPACE_DIR, PROJECT_CODE_PATH, LIGHT_MODELS
)
import logging

from utils.chapter1_utils import extract_json_from_string

logger = logging.getLogger(__name__)


ABLATION_DIR = Path(WORKSPACE_DIR) / "ablation_test"
ABLATION_CODE_DIR = ABLATION_DIR / "code"
ABLATION_FIG_DIR = ABLATION_DIR / "fig"


def generate_ablation_scripts(ablation_design, model_architecture, experiment_design):
    """
    根据消融实验设计，生成可运行的消融实验脚本
    
    Args:
        ablation_design: 消融实验设计(dict, 来自chapter4)
        model_architecture: 模型架构(dict)
        experiment_design: 实验设计(dict)
    
    Returns:
        generated_scripts: 生成的脚本路径列表
    """
    ABLATION_CODE_DIR.mkdir(parents=True, exist_ok=True)
    ABLATION_FIG_DIR.mkdir(parents=True, exist_ok=True)
    
    experiments = ablation_design.get("ablation_experiments", [])
    generated_scripts = []
    
    for exp in experiments:
        exp_name = exp.get("experiment_name", "unnamed")
        safe_name = re.sub(r'[\\/:*?"<>|]', '_', exp_name)
        
        # 生成消融实验配置
        config_content = f"""# Ablation Experiment: {exp_name}
# Target Module: {exp.get('target_module', 'N/A')}
# Hypothesis: {exp.get('hypothesis', 'N/A')}
# Modification: {exp.get('modification', 'N/A')}
# Expected: {exp.get('expected_result', 'N/A')}
# Comparison: {exp.get('comparison_with', 'N/A')}

ablation_config = {{
    "experiment_name": "{exp_name}",
    "target_module": "{exp.get('target_module', '')}",
    "modification": "{exp.get('modification', '')}",
    "comparison_with": "{exp.get('comparison_with', '')}",
}}
"""
        
        config_path = ABLATION_CODE_DIR / f"{safe_name}_config.py"
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(config_content)
        except IOError as e:
            logger.error(f"写入配置文件失败 {config_path}: {e}")
        
        # 生成实验运行脚本模板
        run_script = f"""#!/usr/bin/env python3
# -*- coding: utf-8 -*-
\"\"\"
Ablation Experiment: {exp_name}
Target: {exp.get('target_module', 'N/A')}
\"\"\"

import sys
import os
# 添加项目代码路径
sys.path.insert(0, "{PROJECT_CODE_PATH}")

# TODO: 根据修改说明，修改对应的模型代码
# Modification: {exp.get('modification', 'N/A')}

# 以下是运行消融实验的模板代码
def run_ablation():
    \"\"\"运行消融实验\"\"\"
    # 1. 导入修改后的模型
    # from models.xxx import ModifiedModel
    
    # 2. 使用与full model相同的训练配置
    # config = {{
    #     "epochs": ...,
    #     "batch_size": ...,
    #     "learning_rate": ...,
    #     ...
    # }}
    
    # 3. 训练模型
    # model = ModifiedModel(...)
    # train(model, config)
    
    # 4. 评估并记录结果
    # results = evaluate(model, test_dataset)
    # save_results(results, "{ABLATION_FIG_DIR}/{safe_name}_results.json")
    
    print("Ablation experiment '{exp_name}' - Please implement the actual training logic.")
    print(f"Target module: {exp.get('target_module', 'N/A')}")
    print(f"Modification: {exp.get('modification', 'N/A')}")

if __name__ == "__main__":
    run_ablation()
"""
        
        script_path = ABLATION_CODE_DIR / f"{safe_name}_run.py"
        try:
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(run_script)
        except IOError as e:
            logger.error(f"写入脚本文件失败 {script_path}: {e}")
            continue
        
        generated_scripts.append(str(script_path))
    
    # 生成对比结果汇总脚本
    summary_script = f"""#!/usr/bin/env python3
# -*- coding: utf-8 -*-
\"\"\"汇总所有消融实验结果并生成对比表格和图表\"\"\"

import json
import os
import matplotlib.pyplot as plt
import numpy as np

RESULTS_DIR = "{ABLATION_FIG_DIR}"

def collect_results():
    \"\"\"收集所有消融实验结果\"\"\"
    results = {{}}
    for fname in os.listdir(RESULTS_DIR):
        if fname.endswith('_results.json'):
            exp_name = fname.replace('_results.json', '')
            with open(os.path.join(RESULTS_DIR, fname), 'r') as f:
                results[exp_name] = json.load(f)
    return results

def plot_comparison(results):
    \"\"\"绘制消融对比图\"\"\"
    if not results:
        print("No results found. Please run ablation experiments first.")
        return
    
    # TODO: 根据实际指标和结果格式调整绘图逻辑
    fig, ax = plt.subplots(figsize=(10, 6))
    
    exp_names = list(results.keys())
    metrics = []  # 从结果中提取指标
    
    x = np.arange(len(exp_names))
    width = 0.3
    
    ax.bar(x, metrics, width, label='MAE')
    ax.set_xlabel('Configuration')
    ax.set_ylabel('MAE')
    ax.set_title('Ablation Study Results')
    ax.set_xticks(x)
    ax.set_xticklabels(exp_names, rotation=45, ha='right')
    ax.legend()
    
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, 'ablation_comparison.png'), dpi=300)
    plt.savefig(os.path.join(RESULTS_DIR, 'ablation_comparison.pdf'), dpi=300)
    print(f"Figure saved to {{RESULTS_DIR}}/ablation_comparison.png")

if __name__ == "__main__":
    results = collect_results()
    if results:
        plot_comparison(results)
    else:
        print("No results found. Run individual ablation experiments first.")
"""
    
    try:
        with open(ABLATION_CODE_DIR / "summarize_ablations.py", 'w', encoding='utf-8') as f:
            f.write(summary_script)
    except IOError as e:
        logger.error(f"写入汇总脚本失败: {e}")
    
    return generated_scripts


def generate_latex_comparison_table(ablation_design, experiment_results):
    """生成消融对比的LaTeX表格代码"""
    
    experiments = ablation_design.get("ablation_experiments", [])
    key_results = experiment_results.get("关键结果", {})
    
    if not experiments:
        return "% No ablation experiments designed yet"
    
    # 构建表格
    table = r"""\begin{table}[htbp]
\centering
\caption{Ablation study results on DATASET_NAME. Best results are in \textbf{bold}.}
\label{tab:ablation}
\begin{tabular}{lcc}
\toprule
Configuration & MAE & RMSE \\
\midrule
"""
    
    # Full model
    table += r"Full Model (Ours) & \textbf{X.XXX} & \textbf{X.XXX} \\" + "\n"
    
    # 各消融配置
    for exp in experiments:
        name = exp.get("experiment_name", "Unknown")
        # 简化名称
        short_name = name.replace("Without ", "w/o ").replace("Replace ", "w/ ")
        table += f"{short_name} & X.XXX & X.XXX \\\\\n"
    
    table += r"""\bottomrule
\end{tabular}
\end{table}
"""
    
    return table


def run_ablation_runner(ablation_design, model_architecture, experiment_design):
    """主入口：运行消融实验工具"""
    try:
        ABLATION_CODE_DIR.mkdir(parents=True, exist_ok=True)
        ABLATION_FIG_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.error(f"创建消融实验目录失败: {e}")
        raise

    logger.info("[ablation_runner] 生成消融实验脚本...")
    try:
        scripts = generate_ablation_scripts(ablation_design, model_architecture, experiment_design)
    except Exception as e:
        logger.error(f"消融实验脚本生成失败: {e}")
        scripts = []

    for script in scripts:
        logger.info(f"  生成: {script}")

    # 生成LaTeX对比表格
    try:
        latex_table = generate_latex_comparison_table(ablation_design, experiment_design)
        with open(ABLATION_FIG_DIR / "ablation_table.tex", 'w', encoding='utf-8') as f:
            f.write(latex_table)
    except Exception as e:
        logger.error(f"生成LaTeX对比表格失败: {e}")

    logger.info(f"[ablation_runner] 消融实验脚本已生成至 {ABLATION_CODE_DIR}")
    logger.info(f"[ablation_runner] 图表输出目录: {ABLATION_FIG_DIR}")
    logger.info("[ablation_runner] 请根据模板实现具体的训练逻辑后运行各实验脚本")

    return scripts


if __name__ == "__main__":
    ablation_path = f"{OUTPUT_DIR}/ablation_design.json"
    arch_path = f"{OUTPUT_DIR}/model_architecture.json"
    exp_path = f"{OUTPUT_DIR}/experiment_design.json"
    
    ablation_design = {}
    model_architecture = {}
    experiment_design = {}
    
    if os.path.exists(ablation_path):
        with open(ablation_path, 'r', encoding='utf-8') as f:
            ablation_design = json.load(f)
    if os.path.exists(arch_path):
        with open(arch_path, 'r', encoding='utf-8') as f:
            model_architecture = json.load(f)
    if os.path.exists(exp_path):
        with open(exp_path, 'r', encoding='utf-8') as f:
            experiment_design = json.load(f)
    
    run_ablation_runner(ablation_design, model_architecture, experiment_design)
