# -*- coding: utf-8 -*-
"""
Tool: 消融实验设计器

v5.0 核心新增：基于代码结构分析和参考论文的智能消融实验设计

完整流程：
1. 读取代码结构，搞清楚数据集读取方法
2. 了解怎么进行推理/测试
3. 参考ref_pdf，了解消融实验该怎么设计、做多少、为什么
4. 设计消融实验（替换不同模块做对比）
5. 生成可运行的消融实验代码

关键原则：
- 消融实验不是随意删减，而是有目的地验证每个模块的贡献
- 需要参考ref_pdf中同类论文的消融实验设计模式
- 实验数量取决于模型复杂度：一般每个核心创新点1-2个消融
"""

import os
import json
import re
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from config.project_config import (
    PAPER_TITLE, OUTPUT_DIR, WORKSPACE_DIR, PROJECT_CODE_PATH
)
from tools.base_tool import get_tool_api
from utils.json_utils import extract_json_from_string

logger = logging.getLogger(__name__)


def _get_api():
    """延迟获取API客户端"""
    return get_tool_api()


def _get_call_reasoning():
    """延迟获取reasoning调用函数"""
    return _get_api().call_reasoning


def _get_call_light():
    """延迟获取light调用函数"""
    return _get_api().call_light

ABLATION_DIR = Path(WORKSPACE_DIR) / "ablation_test"
ABLATION_CODE_DIR = ABLATION_DIR / "code"
ABLATION_FIG_DIR = ABLATION_DIR / "fig"
ABLATION_DATA_DIR = ABLATION_DIR / "data"


# ========== Step 1: 代码结构深度分析 ==========

def analyze_code_structure(project_code_path: str) -> Dict[str, Any]:
    """
    深度分析代码结构，提取：
    - 模型定义和各模块的类/函数
    - 数据集加载方式
    - 训练流程
    - 评估/推理流程
    - 配置系统
    """
    project_path = Path(project_code_path)
    if not project_path.exists():
        logger.warning(f"项目代码路径不存在: {project_code_path}")
        return {}

    # 收集所有Python文件
    py_files = []
    for root, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in
                   ['__pycache__', 'node_modules', '.git', 'wandb', 'checkpoints', 'logs']]
        for f in files:
            if f.endswith('.py'):
                py_files.append(Path(root) / f)

    # 按功能分类文件
    file_categories = {
        "model": [], "dataset": [], "train": [], "eval": [],
        "config": [], "loss": [], "utils": [], "other": [],
    }

    category_keywords = {
        "model": ["model", "network", "architecture", "module", "backbone", "encoder", "decoder", "head", "neck"],
        "dataset": ["dataset", "dataloader", "data", "loader"],
        "train": ["train", "main", "run", "fit"],
        "eval": ["eval", "test", "validate", "predict", "inference"],
        "config": ["config", "cfg", "setting", "hyperparameter", "args"],
        "loss": ["loss", "criterion", "cost"],
        "utils": ["utils", "helper", "tool"],
    }

    for fpath in py_files:
        name_lower = fpath.stem.lower()
        categorized = False
        for cat, keywords in category_keywords.items():
            if any(kw in name_lower for kw in keywords):
                try:
                    with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    file_categories[cat].append({
                        "path": str(fpath.relative_to(project_path)),
                        "content": content,
                        "size": len(content),
                    })
                except Exception as e:
                    logger.debug(f"读取文件失败 {fpath}: {e}")
                categorized = True
                break
        if not categorized:
            try:
                with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                file_categories["other"].append({
                    "path": str(fpath.relative_to(project_path)),
                    "content": content,
                    "size": len(content),
                })
            except Exception as e:
                logger.debug(f"读取文件失败 {fpath}: {e}")

    # 使用LLM深度分析代码结构
    code_analysis = _llm_analyze_code_structure(file_categories)
    return code_analysis


def _llm_analyze_code_structure(file_categories: Dict) -> Dict:
    """使用LLM深度分析代码结构"""

    # 构建模型代码摘要
    model_summary = ""
    for item in file_categories.get("model", [])[:5]:
        model_summary += f"\n--- {item['path']} ---\n{item['content'][:4000]}\n"

    # 构建数据集代码摘要
    dataset_summary = ""
    for item in file_categories.get("dataset", [])[:3]:
        dataset_summary += f"\n--- {item['path']} ---\n{item['content'][:3000]}\n"

    # 构建训练代码摘要
    train_summary = ""
    for item in file_categories.get("train", [])[:2]:
        train_summary += f"\n--- {item['path']} ---\n{item['content'][:3000]}\n"

    # 构建评估代码摘要
    eval_summary = ""
    for item in file_categories.get("eval", [])[:2]:
        eval_summary += f"\n--- {item['path']} ---\n{item['content'][:3000]}\n"

    prompt = f"""你是一名深度学习代码分析专家。请深度分析以下项目代码，提取消融实验所需的关键信息。

**论文标题**: {PAPER_TITLE}

**模型代码**:
{model_summary[:10000]}

**数据集代码**:
{dataset_summary[:5000]}

**训练代码**:
{train_summary[:5000]}

**评估代码**:
{eval_summary[:5000]}

请提取以下信息，以json格式返回：

1. **model_modules**: 模型的核心模块列表，每个模块包含：
   - name: 模块名称（与代码中的类名/函数名一致）
   - description: 模块功能描述
   - class_name: 代码中的类名
   - file_path: 所在文件路径
   - input_output: 输入输出描述
   - is_removable: 是否可以独立移除（True/False）
   - replacement: 移除后可用什么替代（如"identity mapping", "simple conv"等）

2. **dataset_info**: 数据集加载信息，包含：
   - dataset_class: 数据集类名
   - dataset_path: 数据路径
   - load_method: 如何加载数据（具体代码片段）
   - preprocessing: 预处理步骤
   - train_val_test_split: 如何划分训练/验证/测试集

3. **training_pipeline**: 训练流程，包含：
   - entry_point: 训练入口（文件:函数）
   - optimizer: 优化器
   - scheduler: 学习率调度器
   - batch_size: 批大小
   - epochs: 训练轮数
   - loss_functions: 损失函数列表
   - checkpoint_save: 检查点保存方式
   - how_to_modify_model: 如何替换模型组件（具体代码位置和修改方法）

4. **evaluation_pipeline**: 评估流程，包含：
   - entry_point: 评估入口（文件:函数）
   - metrics: 评估指标及计算方式
   - how_to_run_eval: 运行评估的具体命令或代码
   - output_format: 结果输出格式

回复以```json开头，以```结尾。"""

    response = _get_call_reasoning()(prompt)
    try:
        analysis = extract_json_from_string(response)
        if not isinstance(analysis, dict):
            analysis = {}
    except Exception:
        analysis = {}

    return analysis


# ========== Step 2: 参考ref_pdf的消融实验模式 ==========

def analyze_ablation_patterns_from_refs(ref_data: Dict) -> Dict:
    """
    从参考论文中学习消融实验设计模式

    分析ref_pdf中的消融实验部分，提炼：
    - 消融实验数量和类型
    - 每个消融的验证目标
    - 结果呈现方式（表格/图表）
    - 实验设计逻辑
    """
    papers = ref_data.get("papers", [])
    if not papers:
        return {"ablation_patterns": [], "recommendation": "no_ref_papers"}

    # 从参考论文中提取消融实验相关内容
    ablation_sections = []
    for p in papers[:8]:
        text = p.get("text", "")
        # 查找消融实验相关章节
        patterns = [
            r'(?i)(?:ablation|ablative)\s+(?:study|analysis|experiment|evaluation).*?(?=\n\d+\.|\n[A-Z][a-z]+\n|\Z)',
            r'(?i)4\.\d+\s+.*?ablation.*?(?=\n\d+\.\d+|\n\d+\.\s|\Z)',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                if len(match) > 200:  # 必须有足够的内容
                    ablation_sections.append({
                        "paper": p.get("filename", ""),
                        "content": match[:3000],
                    })

    if not ablation_sections:
        return {"ablation_patterns": [], "recommendation": "no_ablation_in_refs"}

    # 使用LLM分析消融实验模式
    combined = "\n\n---\n\n".join([
        f"Paper: {s['paper']}\n{s['content']}"
        for s in ablation_sections[:5]
    ])

    prompt = f"""你是一名学术论文实验设计专家。请分析以下参考论文中的消融实验（Ablation Study）设计模式。

**参考论文消融实验部分**:
{combined[:16000]}

请分析并提取以下信息，以json格式返回：

1. **ablation_patterns**: 从参考论文中观察到的消融实验设计模式，每个模式包含：
   - pattern_name: 模式名称（如"逐模块移除"、"组件替换"、"特征维度变化"）
   - description: 模式描述
   - typical_count: 典型消融实验数量
   - when_to_use: 何时使用此模式

2. **result_presentation**: 结果呈现方式
   - table_format: 表格格式描述（列名、如何标注最优值等）
   - figure_format: 图表格式描述（如果有）
   - metrics_shown: 通常展示哪些指标

3. **design_logic**: 消融实验设计的逻辑
   - core_principle: 核心原则
   - what_to_ablate: 应该消融什么
   - how_many: 做多少个消融实验（规则）
   - why: 为什么这样做（因果关系验证）

4. **recommendation**: 基于参考论文，对本论文的消融实验设计建议

回复以```json开头，以```结尾。"""

    response = _get_call_reasoning()(prompt)
    try:
        patterns = extract_json_from_string(response)
        if not isinstance(patterns, dict):
            patterns = {"ablation_patterns": [], "recommendation": "parse_error"}
    except Exception:
        patterns = {"ablation_patterns": [], "recommendation": "error"}

    return patterns


# ========== Step 3: 设计消融实验 ==========

def design_ablation_experiments(code_analysis: Dict, ref_patterns: Dict,
                                project_data: Dict, ref_data: Dict) -> Dict:
    """
    综合代码分析和参考论文模式，设计消融实验

    Args:
        code_analysis: 代码结构分析结果
        ref_patterns: 参考论文消融模式
        project_data: 项目数据（含innovation_points, model_architecture等）
        ref_data: 参考PDF数据

    Returns:
        消融实验设计方案
    """
    model_modules = code_analysis.get("model_modules", [])
    innovation_points = project_data.get("innovation_points", [])
    model_arch = project_data.get("model_architecture", {})

    # 构建上下文
    modules_text = json.dumps(model_modules, ensure_ascii=False, indent=2)[:6000]
    innovation_text = json.dumps(innovation_points, ensure_ascii=False, indent=2)[:3000]
    patterns_text = json.dumps(ref_patterns, ensure_ascii=False, indent=2)[:4000]

    prompt = f"""你是一名深度学习实验设计专家。请根据代码分析结果和参考论文的消融模式，为本论文设计消融实验。

**论文标题**: {PAPER_TITLE}

**代码中识别的模型模块**:
{modules_text}

**创新点**:
{innovation_text}

**参考论文的消融实验模式**:
{patterns_text}

**消融实验设计原则**：
1. 每个核心创新点至少1个消融实验验证其贡献
2. 消融方式必须与代码结构对应——移除或替换的模块必须在代码中真实存在
3. 参考同领域论文的消融实验模式
4. Full Model 必须作为基线对比
5. 移除模块后应有合理的替代方案（如identity mapping, simple conv等），而非直接删除导致维度不匹配

请设计消融实验，以json格式返回：

{{
  "design_rationale": "整体设计思路说明",
  "ablation_experiments": [
    {{
      "experiment_name": "w/o Module Name",
      "target_module": "要消融的模块名（与代码中一致）",
      "target_class": "代码中的类名",
      "hypothesis": "假设该模块对性能的贡献是XXX",
      "modification": "具体修改方式（如：将XXX模块替换为identity mapping / 简单的2层MLP / 移除XXX分支）",
      "modification_detail": "修改的具体代码位置和方式（文件路径、行号、替换为）",
      "comparison_with": "与Full Model对比",
      "expected_result": "预期该模块移除后性能会下降XX%",
      "requires_retraining": true/false,
      "training_config_override": {{}}  // 如果需要不同的训练配置
    }}
  ],
  "result_table_format": {{
    "columns": ["Configuration", "Metric1", "Metric2", "..."],
    "row_order": ["Full Model (Ours)"] + experiment_names,
    "best_marking": "加粗最优值"
  }}
}}

回复以```json开头，以```结尾。"""

    response = _get_call_reasoning()(prompt)
    try:
        design = extract_json_from_string(response)
        if not isinstance(design, dict):
            design = {"design_rationale": "分析失败", "ablation_experiments": []}
    except Exception:
        design = {"design_rationale": "分析失败", "ablation_experiments": []}

    return design


# ========== Step 4: 生成消融实验代码 ==========

def generate_ablation_code(ablation_design: Dict, code_analysis: Dict) -> List[str]:
    """
    根据消融实验设计方案和代码结构分析，生成可运行的消融实验代码

    Returns:
        生成的脚本路径列表
    """
    try:
        ABLATION_CODE_DIR.mkdir(parents=True, exist_ok=True)
        ABLATION_FIG_DIR.mkdir(parents=True, exist_ok=True)
        ABLATION_DATA_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.error(f"创建消融实验目录失败: {e}")
        raise

    experiments = ablation_design.get("ablation_experiments", [])
    generated_scripts = []

    # 保存代码结构分析
    try:
        with open(ABLATION_CODE_DIR / "code_analysis.json", 'w', encoding='utf-8') as f:
            json.dump(code_analysis, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logger.error(f"保存代码分析失败: {e}")

    # 保存消融实验设计
    try:
        with open(ABLATION_CODE_DIR / "ablation_design.json", 'w', encoding='utf-8') as f:
            json.dump(ablation_design, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logger.error(f"保存消融实验设计失败: {e}")

    dataset_info = code_analysis.get("dataset_info", {})
    training_pipeline = code_analysis.get("training_pipeline", {})
    evaluation_pipeline = code_analysis.get("evaluation_pipeline", {})

    for exp in experiments:
        exp_name = exp.get("experiment_name", "unnamed")
        safe_name = re.sub(r'[\\/:*?"<>|]', '_', exp_name)

        # 使用LLM生成具体的消融代码
        try:
            exp_code = _generate_single_ablation_script(
                exp, code_analysis, safe_name
            )
        except Exception as e:
            logger.error(f"生成消融脚本失败 {exp_name}: {e}")
            exp_code = f'# 生成失败: {e}\n# 请手动实现 {exp_name} 消融实验\n'

        script_path = ABLATION_CODE_DIR / f"{safe_name}_run.py"
        try:
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(exp_code)
            generated_scripts.append(str(script_path))
        except IOError as e:
            logger.error(f"写入消融脚本失败 {script_path}: {e}")

    # 生成汇总运行脚本
    try:
        _generate_master_script(ablation_design, code_analysis)
    except Exception as e:
        logger.error(f"生成主控脚本失败: {e}")

    # 生成结果汇总脚本
    try:
        _generate_summary_script(ablation_design)
    except Exception as e:
        logger.error(f"生成汇总脚本失败: {e}")

    return generated_scripts


def _generate_single_ablation_script(exp: Dict, code_analysis: Dict,
                                      safe_name: str) -> str:
    """使用LLM生成单个消融实验的运行脚本"""

    dataset_info = code_analysis.get("dataset_info", {})
    training_pipeline = code_analysis.get("training_pipeline", {})
    evaluation_pipeline = code_analysis.get("evaluation_pipeline", {})
    model_modules = code_analysis.get("model_modules", [])

    # 找到目标模块的详细信息
    target_class = exp.get("target_class", "")
    target_module_info = {}
    for mod in model_modules:
        if mod.get("class_name", "") == target_class or mod.get("name", "") == exp.get("target_module", ""):
            target_module_info = mod
            break

    prompt = f"""请生成一个完整的Python消融实验脚本。

**实验名称**: {exp.get('experiment_name', '')}
**目标模块**: {exp.get('target_module', '')} (类名: {target_class})
**修改方式**: {exp.get('modification', '')}
**修改详情**: {exp.get('modification_detail', '')}
**是否需要重新训练**: {exp.get('requires_retraining', True)}

**数据集加载方式**:
{json.dumps(dataset_info, ensure_ascii=False, indent=2)[:3000]}

**训练流程**:
{json.dumps(training_pipeline, ensure_ascii=False, indent=2)[:3000]}

**评估流程**:
{json.dumps(evaluation_pipeline, ensure_ascii=False, indent=2)[:3000]}

**目标模块代码信息**:
{json.dumps(target_module_info, ensure_ascii=False, indent=2)[:2000]}

请生成一个完整的Python脚本，包含：
1. 导入必要的库（sys, os, 添加项目代码路径）
2. 实现模块修改（根据modification_detail替换目标模块）
3. 数据加载（使用与原项目相同的方式）
4. 训练（如果requires_retraining=True）或直接加载预训练权重
5. 评估
6. 保存结果到JSON文件

脚本应该是可直接运行的，不要有TODO占位符。如果某些实现细节无法确定，使用合理的默认值。

直接给出Python代码，不要用markdown包裹。"""

    try:
        script = _get_call_reasoning()(prompt)
        # 清理可能的markdown标记
        script = re.sub(r'^```python\s*', '', script)
        script = re.sub(r'\s*```$', '', script)
        return script
    except Exception as e:
        logger.error(f"生成消融实验脚本失败: {e}")
        return f'# 生成失败: {e}\n# 请手动实现 {exp.get("experiment_name", "")} 消融实验\n'


def _generate_master_script(ablation_design: Dict, code_analysis: Dict):
    """生成主控运行脚本"""
    experiments = ablation_design.get("ablation_experiments", [])

    script_content = f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
消融实验主控脚本
按顺序运行所有消融实验
"""

import os
import sys
import json
import subprocess
import time

ABLATION_DIR = r"{ABLATION_CODE_DIR}"

experiments = {json.dumps([exp.get("experiment_name", "") for exp in experiments], ensure_ascii=False)}

def run_experiment(script_name):
    """运行单个消融实验"""
    script_path = os.path.join(ABLATION_DIR, script_name)
    if not os.path.exists(script_path):
        print(f"  跳过: {{script_name}} 不存在")
        return None

    print(f"  运行: {{script_name}}")
    start = time.time()
    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True, text=True, timeout=3600
        )
        duration = time.time() - start
        if result.returncode == 0:
            print(f"  完成: {{script_name}} ({{duration:.0f}}s)")
            return {{"status": "success", "duration": duration}}
        else:
            print(f"  失败: {{script_name}}")
            print(f"  错误: {{result.stderr[:500]}}")
            return {{"status": "failed", "error": result.stderr[:500]}}
    except subprocess.TimeoutExpired:
        print(f"  超时: {{script_name}}")
        return {{"status": "timeout"}}
    except Exception as e:
        print(f"  异常: {{e}}")
        return {{"status": "error", "error": str(e)}}


def main():
    print("=" * 60)
    print("  消融实验批量运行")
    print("=" * 60)

    results = {{}}
    for i, exp_name in enumerate(experiments, 1):
        print(f"\\n[{i}/{len(experiments)}] {{exp_name}}")
        safe_name = exp_name.replace("/", "_").replace("\\\\", "_")
        script_name = f"{{safe_name}}_run.py"
        results[exp_name] = run_experiment(script_name)

    # 保存运行结果
    results_path = os.path.join(ABLATION_DIR, "..", "data", "run_results.json")
    os.makedirs(os.path.dirname(results_path), exist_ok=True)
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print("\\n" + "=" * 60)
    print("  所有实验运行完毕")
    print("=" * 60)


if __name__ == "__main__":
    main()
'''
    with open(ABLATION_CODE_DIR / "run_all_ablations.py", 'w', encoding='utf-8') as f:
        f.write(script_content)


def _generate_summary_script(ablation_design: Dict):
    """生成结果汇总脚本"""
    table_format = ablation_design.get("result_table_format", {})

    script_content = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
汇总所有消融实验结果
"""

import json
import os
import glob

ABLATION_DATA_DIR = r"{data_dir}"

def collect_results():
    """收集所有消融实验结果"""
    results = {{}}
    for fpath in glob.glob(os.path.join(ABLATION_DATA_DIR, "*.json")):
        fname = os.path.basename(fpath)
        exp_name = fname.replace("_results.json", "")
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                results[exp_name] = json.load(f)
        except Exception:
            pass
    return results

def main():
    results = collect_results()
    if not results:
        print("未找到任何实验结果。请先运行消融实验。")
        return

    print("消融实验结果汇总:")
    print("-" * 60)
    for name, data in results.items():
        print(f"  {{name}}: {{json.dumps(data, ensure_ascii=False)[:200]}}")

    # 保存汇总
    summary_path = os.path.join(ABLATION_DATA_DIR, "ablation_summary.json")
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\\n汇总已保存至: {{summary_path}}")

if __name__ == "__main__":
    main()
'''.format(data_dir=str(ABLATION_DATA_DIR))

    with open(ABLATION_CODE_DIR / "summarize_ablations.py", 'w', encoding='utf-8') as f:
        f.write(script_content)


# ========== 主入口 ==========

def run_ablation_designer(project_data: Dict, ref_data: Dict) -> Dict:
    """
    主入口：运行消融实验设计器

    完整流程：
    1. 分析代码结构
    2. 分析ref_pdf消融模式
    3. 设计消融实验
    4. 生成消融实验代码

    Returns:
        Dict: 消融实验设计方案 + 代码分析结果
    """
    logger.info("=" * 60)
    logger.info("  消融实验设计器 v5.0")
    logger.info("=" * 60)

    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
    except OSError as e:
        logger.error(f"创建输出目录失败 {OUTPUT_DIR}: {e}")

    # Step 1: 分析代码结构
    logger.info("[Step 1/4] 分析项目代码结构...")
    try:
        code_analysis = analyze_code_structure(PROJECT_CODE_PATH)
    except Exception as e:
        logger.error(f"代码结构分析失败: {e}")
        code_analysis = {}

    try:
        with open(f"{OUTPUT_DIR}/code_analysis.json", 'w', encoding='utf-8') as f:
            json.dump(code_analysis, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logger.error(f"保存代码分析结果失败: {e}")

    modules_count = len(code_analysis.get("model_modules", []))
    logger.info(f"  识别到 {modules_count} 个模型模块")

    # Step 2: 分析参考论文消融模式
    logger.info("[Step 2/4] 分析参考论文消融实验模式...")
    try:
        ref_patterns = analyze_ablation_patterns_from_refs(ref_data)
    except Exception as e:
        logger.error(f"参考论文消融模式分析失败: {e}")
        ref_patterns = {"ablation_patterns": [], "recommendation": "error"}

    try:
        with open(f"{OUTPUT_DIR}/ablation_patterns_from_refs.json", 'w', encoding='utf-8') as f:
            json.dump(ref_patterns, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logger.error(f"保存消融模式结果失败: {e}")

    patterns_count = len(ref_patterns.get("ablation_patterns", []))
    logger.info(f"  从参考论文中提取到 {patterns_count} 个消融模式")

    # Step 3: 设计消融实验
    logger.info("[Step 3/4] 设计消融实验...")
    try:
        ablation_design = design_ablation_experiments(
            code_analysis, ref_patterns, project_data, ref_data
        )
    except Exception as e:
        logger.error(f"消融实验设计失败: {e}")
        ablation_design = {"design_rationale": "设计失败", "ablation_experiments": []}

    try:
        with open(f"{OUTPUT_DIR}/ablation_design.json", 'w', encoding='utf-8') as f:
            json.dump(ablation_design, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logger.error(f"保存消融实验设计失败: {e}")

    exp_count = len(ablation_design.get("ablation_experiments", []))
    logger.info(f"  设计了 {exp_count} 个消融实验")
    for exp in ablation_design.get("ablation_experiments", []):
        logger.info(f"    - {exp.get('experiment_name', 'N/A')}: {exp.get('modification', 'N/A')[:60]}")

    # Step 4: 生成消融实验代码
    logger.info("[Step 4/4] 生成消融实验代码...")
    try:
        scripts = generate_ablation_code(ablation_design, code_analysis)
        for script in scripts:
            logger.info(f"  生成: {script}")
    except Exception as e:
        logger.error(f"消融实验代码生成失败: {e}")
        scripts = []

    logger.info(f"消融实验设计完成！代码位于 {ABLATION_CODE_DIR}")
    logger.info(f"数据输出目录: {ABLATION_DATA_DIR}")
    logger.info(f"图表输出目录: {ABLATION_FIG_DIR}")

    return {
        "code_analysis": code_analysis,
        "ref_patterns": ref_patterns,
        "ablation_design": ablation_design,
        "generated_scripts": scripts,
    }
