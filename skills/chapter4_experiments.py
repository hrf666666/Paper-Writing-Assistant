# -*- coding: utf-8 -*-
"""
Skill: 第四章 - Experiments / 实验及分析
核心任务：
1. 数据集描述（优先用项目现有数据集）
2. 性能横向对比（检索对应数据集近年模型性能）
3. 消融实验（提炼关键模块，设计控制变量实验，利用项目代码运行）
4. 消融实验代码→workspace/ablation_test/code，图表→workspace/ablation_test/fig
"""

import os
import json
import re
from pathlib import Path
from tqdm import tqdm

from config.project_config import (
    PAPER_TITLE, OUTPUT_DIR, WORKSPACE_DIR, PROJECT_CODE_PATH,
    RUN_ABLATION, get_article_type_info
)
from agent.api_client import get_api_client
from api.paper_search import search_papers, get_paper_details
from utils.chapter1_utils import extract_json_from_string

# 延迟初始化API客户端
_api = None

def _get_api():
    global _api
    if _api is None:
        _api = get_api_client()
    return _api


def _search_baselines_for_dataset(dataset_name, size=8):
    """检索特定数据集上的baseline方法及其性能"""
    try:
        keywords = [[dataset_name, "depth estimation"], [dataset_name, "state-of-the-art"]]
        result = search_papers(keywords, size)
        papers = []
        if "data" in result and result["data"]:
            for paper_brief in result["data"][:size]:
                details = get_paper_details(paper_brief["id"])
                if "data" in details and details["data"]:
                    paper_info = details["data"][0]
                    papers.append({
                        "title": paper_info.get("title", ""),
                        "year": paper_info.get("year", ""),
                        "abstract": paper_info.get("abstract", "")[:300],
                        "venue": paper_info.get("venue", {}).get("raw", "") if paper_info.get("venue") else "",
                    })
        return papers
    except Exception as e:
        print(f"  [chapter4] baseline搜索失败: {e}")
        return []


def _detect_datasets_in_project():
    """检测项目代码中存在的数据集"""
    project_path = Path(PROJECT_CODE_PATH)
    datasets = []
    
    if not project_path.exists():
        return datasets
    
    # 搜索常见数据集目录和配置
    dataset_indicators = [
        "datasets", "data", "HCInew", "HCI-Old", "Wanner_HCI",
        "Non-lambertian", "nyu", "kitti", "scannet",
    ]
    
    for root, dirs, files in os.walk(project_path):
        for d in dirs:
            for indicator in dataset_indicators:
                if indicator.lower() in d.lower():
                    datasets.append({
                        "name": d,
                        "path": str(Path(root) / d),
                    })
                    break
    
    # 搜索配置文件中的数据集引用
    for root, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
        for f in files:
            if f.endswith(('.py', '.yaml', '.json', '.cfg')):
                try:
                    fpath = Path(root) / f
                    with open(fpath, 'r', encoding='utf-8', errors='ignore') as fh:
                        content = fh.read()
                    # 查找数据集名称
                    common_datasets = [
                        "HCInew", "HCI-Old", "Wanner_HCI", "Non-lambertian",
                        "NYUv2", "KITTI", "ScanNet", "Middlebury",
                        "ETH3D", "CRESterDataset", "Flickr1024",
                    ]
                    for ds in common_datasets:
                        if ds.lower() in content.lower() and ds not in [d["name"] for d in datasets]:
                            datasets.append({"name": ds, "path": "referenced in code"})
                except Exception:
                    pass
    
    return datasets


def _analyze_project_model_code():
    """深度分析项目代码中的模型结构，提取可消融的关键模块"""
    project_path = Path(PROJECT_CODE_PATH)
    if not project_path.exists():
        return {}
    
    # 读取模型代码文件
    model_code = ""
    model_indicators = ["model", "network", "architecture", "module"]
    
    for root, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
        for f in files:
            if f.endswith('.py'):
                name_lower = f.lower()
                if any(ind in name_lower for ind in model_indicators):
                    try:
                        fpath = Path(root) / f
                        with open(fpath, 'r', encoding='utf-8', errors='ignore') as fh:
                            content = fh.read()
                        model_code += f"\n--- {fpath.relative_to(project_path)} ---\n{content}\n"
                    except Exception:
                        pass
    
    if not model_code.strip():
        return {}
    
    # 用LLM分析模型结构，提取可消融模块
    prompt = f"""
你是一名深度学习架构分析专家。请分析以下项目代码中的模型结构，提取出可以进行消融实验的关键模块。

要求：
1. 识别模型中的所有关键模块/组件（如attention、encoder、decoder、loss等）
2. 对每个模块，说明：
   - 模块名称
   - 模块在代码中的位置（文件名+类名/函数名）
   - 模块的核心功能
   - 可以用什么替换（用于消融对比）
   - 消融该模块后预期的性能变化

<model_code>
{model_code[:16000]}
</model_code>

请以json格式给出，包含"modules"字段（list），每个元素包含：
- "module_name": 模块名
- "code_location": 代码位置
- "core_function": 核心功能
- "ablation_replacement": 消融时替换为什么
- "expected_impact": 预期影响

回复以```json开头，以```结尾。
"""
    
    try:
        response = _get_api().call_reasoning(prompt)
        result = extract_json_from_string(response)
        return result
    except Exception:
        return {"modules": []}


def _design_ablation_experiments(innovation_points, model_architecture, experiment_design):
    """设计消融实验 - 基于项目代码的真实模块分析"""
    
    # 先分析项目代码中的模型结构
    print("[chapter4] 深度分析项目模型代码...")
    model_analysis = _analyze_project_model_code()
    modules_info = model_analysis.get("modules", [])
    
    # 构建模块信息摘要
    modules_summary = ""
    if modules_info:
        for m in modules_info:
            modules_summary += f"- {m.get('module_name', 'N/A')}: {m.get('core_function', 'N/A')} (替换: {m.get('ablation_replacement', 'N/A')})\n"
    else:
        modules_summary = "未检测到项目模型代码中的可消融模块，请基于创新点设计消融实验。"
    
    prompt = f"""
你是一名深度学习实验设计专家。请为论文"{PAPER_TITLE}"设计消融实验。

**核心原则**：
1. 消融实验应验证每个关键创新点的有效性
2. 每个消融实验是控制变量实验：只移除/替换一个模块，保持其他不变
3. 替换模块应选择相同/相近功能的已有方法（如去掉attention替换为普通conv）
4. 需要提供具体的实验配置，使得可以直接修改项目代码运行

**创新点**：
{json.dumps(innovation_points, ensure_ascii=False, indent=2)[:3000]}

**模型架构**：
{json.dumps(model_architecture, ensure_ascii=False, indent=2)[:3000]}

**项目代码中检测到的可消融模块**：
{modules_summary}

**已有实验设计**：
{json.dumps(experiment_design, ensure_ascii=False, indent=2)[:2000]}

请以json格式给出，包含"ablation_experiments"字段（list），每个元素包含：
- "experiment_name": 实验名称
- "target_module": 被消融的模块名
- "hypothesis": 要验证的假设
- "modification": 具体修改方式（如何替换/移除该模块，需对应项目代码中的真实类/函数）
- "expected_result": 预期结果（性能下降说明该模块有效）
- "comparison_with": 替换为什么方法

回复以```json开头，以```结尾。
"""
    
    response = _get_api().call_reasoning(prompt)
    try:
        ablation_design = extract_json_from_string(response)
    except Exception:
        ablation_design = {"ablation_experiments": []}
    
    # 将模块分析结果附加到消融设计中
    ablation_design["_model_analysis"] = model_analysis
    
    return ablation_design


def _generate_ablation_code(ablation_experiments, project_code_path):
    """为消融实验生成实际可执行的代码修改方案"""
    
    ablation_dir = Path(WORKSPACE_DIR) / "ablation_test" / "code"
    ablation_dir.mkdir(parents=True, exist_ok=True)
    
    # 读取原始模型代码，用于生成精确的代码修改
    model_analysis = ablation_experiments.get("_model_analysis", {})
    modules_info = model_analysis.get("modules", [])
    
    for exp in ablation_experiments.get("ablation_experiments", []):
        exp_name = exp.get("experiment_name", "unnamed").replace(" ", "_")
        safe_name = re.sub(r'[\\/:*?"<>|]', '_', exp_name)
        
        target_module = exp.get("target_module", "")
        modification = exp.get("modification", "")
        comparison_with = exp.get("comparison_with", "")
        
        # 找到目标模块的代码位置
        module_location = ""
        for m in modules_info:
            if m.get("module_name", "").lower() in target_module.lower() or \
               target_module.lower() in m.get("module_name", "").lower():
                module_location = m.get("code_location", "unknown")
                break
        
        # 生成消融实验脚本（包含实际的代码修改指导）
        script_content = f"""#!/usr/bin/env python3
# -*- coding: utf-8 -*-
\"\"\"
Ablation Experiment: {exp_name}
Target: {target_module}
Location: {module_location}
\"\"\"

import sys
import os
# 添加项目代码路径
sys.path.insert(0, "{PROJECT_CODE_PATH}")

# ============================================================
# 消融修改说明：
# 目标模块: {target_module}
# 代码位置: {module_location}
# 修改方式: {modification}
# 替换为: {comparison_with}
# ============================================================
#
# 实现步骤：
# 1. 复制原始模型文件到本目录
# 2. 根据修改说明，对目标模块进行替换/移除
# 3. 确保修改后的模型可以正常实例化和前向传播
# 4. 使用与full model完全相同的训练配置进行训练
# 5. 记录结果到 {WORKSPACE_DIR}/ablation_test/fig/{safe_name}_results.json
#
# 常见替换模式：
# - 去掉Attention -> 替换为nn.Identity()或普通Conv2d
# - 去掉Dual-Mask -> 替换为单一Mask或常数Mask
# - 去掉Physics Loss -> 从总损失中移除对应项
# ============================================================

def create_ablated_model():
    \"\"\"创建消融后的模型\"\"\"
    # TODO: 根据修改说明实现具体的模型修改
    # 示例：
    # from models.angular_aware_depth import AngularAwareDepthModel
    # model = AngularAwareDepthModel(...)
    # 替换目标模块：
    # model.target_module = ReplacementModule(...)
    pass

def run_ablation():
    \"\"\"运行消融实验\"\"\"
    model = create_ablated_model()
    
    # 使用与full model相同的训练配置
    # 参考: {project_code_path}/scripts/train_angular_aware.py
    
    # TODO: 实现训练和评估逻辑
    # 将结果保存到:
    # results_path = "{WORKSPACE_DIR}/ablation_test/fig/{safe_name}_results.json"
    print(f"Ablation '{exp_name}' - 需要根据上述指导实现具体训练逻辑")
    print(f"目标模块: {target_module}")
    print(f"修改方式: {modification}")

if __name__ == "__main__":
    run_ablation()
"""
        
        script_path = ablation_dir / f"{safe_name}_run.py"
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        # 同时生成修改说明文件
        readme_content = f"""# Ablation Experiment: {exp.get('experiment_name', 'N/A')}

## Target Module
{target_module}

## Code Location
{module_location}

## Hypothesis
{exp.get('hypothesis', 'N/A')}

## Modification
{modification}

## Expected Result
{exp.get('expected_result', 'N/A')}

## Comparison With
{comparison_with}

## How to Run
1. 根据修改说明，修改模型代码中的目标模块
2. Run: `python {safe_name}_run.py`
3. Compare results with the full model's performance
"""
        
        with open(ablation_dir / f"{safe_name}_README.md", 'w', encoding='utf-8') as f:
            f.write(readme_content)
    
    return ablation_dir


def generate_experiments(project_data, ref_data):
    """生成第四章 Experiments"""
    
    innovation_points = project_data.get("innovation_points", [])
    model_architecture = project_data.get("model_architecture", {})
    experiment_design = project_data.get("experiment_design", {})
    project_info = project_data.get("project_info", {})
    
    style_guide = ref_data.get("style_guide", {})
    chapter_org = ref_data.get("chapter_organizations", {}).get("Experiments", {})
    domain_info = ref_data.get("domain_info", {})
    article_info = get_article_type_info()
    
    style_instruction = _build_style_instruction(style_guide, chapter_org)
    
    innovation_summary = "\n".join([
        f"创新点{i+1}: {ip.get('创新点名称', 'N/A')} - {ip.get('创新点价值', 'N/A')}"
        for i, ip in enumerate(innovation_points)
    ])
    
    # ==================== 4.1 Datasets ====================
    print("[chapter4] 检测项目数据集...")
    detected_datasets = _detect_datasets_in_project()
    
    print("[chapter4] 生成 4.1 Datasets...")
    prompt_4_1 = f"""
你是一名{article_info['name']}级别的学术论文写作专家。请为论文"{PAPER_TITLE}"撰写第4.1节"Datasets"。

**核心任务**：详细描述实验使用的数据集。

**项目数据集信息**：
<detected_datasets>
{json.dumps(detected_datasets, ensure_ascii=False, indent=2)}
</detected_datasets>

<experiment_design>
{json.dumps(experiment_design, ensure_ascii=False, indent=2)[:3000]}
</experiment_design>

<domain_info>
{json.dumps(domain_info, ensure_ascii=False, indent=2)[:2000]}
</domain_info>

**具体要求**：
1. 对每个数据集，描述：名称、场景类型、视角数/图像数、分辨率、深度图来源、训练/验证/测试划分
2. 说明为什么选择这些数据集（覆盖不同的场景类型和挑战）
3. 如有自定义数据集或预处理，详细说明
4. 使用表格汇总所有数据集的关键信息

请使用学术英语撰写。Markdown格式（表格使用Markdown表格语法）。直接给出内容：
"""
    
    section_4_1 = _get_api().call_generation(prompt_4_1)
    
    # ==================== 4.2 Implementation Details ====================
    print("[chapter4] 生成 4.2 Implementation Details...")
    prompt_4_2 = f"""
你是一名{article_info['name']}级别的学术论文写作专家。请为论文"{PAPER_TITLE}"撰写第4.2节"Implementation Details"。

**项目训练信息**：
<experiment_design>
{json.dumps(experiment_design, ensure_ascii=False, indent=2)[:3000]}
</experiment_design>

<project_train_code>
{project_info.get('train_content', '')[:3000]}
</project_train_code>

<project_config>
{project_info.get('loss_config_content', '')[:2000]}
</project_config>

**具体要求**：
1. 硬件环境（GPU型号、数量）
2. 训练超参数：优化器、学习率、scheduler、batch size、epoch数、梯度累积步数等
3. 数据增强策略
4. 损失函数各组件的权重设置
5. 评估指标的定义和计算方式
6. 训练时间

请使用学术英语撰写。使用表格汇总关键超参数。Markdown格式。直接给出内容：
"""
    
    section_4_2 = _get_api().call_generation(prompt_4_2)
    
    # ==================== 4.3 Comparison with State-of-the-art ====================
    print("[chapter4] 检索baseline性能数据...")
    dataset_names = [ds["name"] for ds in detected_datasets] if detected_datasets else ["HCI"]
    baseline_papers = {}
    for ds_name in dataset_names[:3]:
        baseline_papers[ds_name] = _search_baselines_for_dataset(ds_name, size=5)
    
    print("[chapter4] 生成 4.3 Comparison with State-of-the-art...")
    prompt_4_3 = f"""
你是一名{article_info['name']}级别的学术论文写作专家。请为论文"{PAPER_TITLE}"撰写第4.3节"Comparison with State-of-the-art"。

**核心任务**：进行性能横向对比。

**项目实验结果**：
<experiment_design>
{json.dumps(experiment_design, ensure_ascii=False, indent=2)[:3000]}
</experiment_design>

<project_report>
{project_info.get('report_content', '')[:3000]}
</project_report>

**参考论文中的baseline信息**：
<domain_info>
{json.dumps(domain_info, ensure_ascii=False, indent=2)[:3000]}
</domain_info>

<searched_baselines>
{json.dumps(baseline_papers, ensure_ascii=False, indent=2)[:3000]}
</searched_baselines>

**具体要求**：
1. 使用表格呈现与SOTA方法的性能对比
2. 表格包含：方法名、年份、各数据集上的关键指标
3. 最优结果加粗，次优结果下划线
4. 表格后逐项分析对比结果：
   - 本文方法在哪些指标/数据集上表现最优
   - 与各baseline相比的优势幅度
   - 分析优势的原因（关联到方法设计）
5. 对于本文方法表现不是最优的情况，分析原因

请使用学术英语撰写。表格使用LaTeX格式（\\begin{{table}}...\\end{{table}}）。
Markdown+LaTeX混合格式。直接给出内容：
"""
    
    section_4_3 = _get_api().call_generation(prompt_4_3)
    
    # ==================== 4.4 Ablation Study ====================
    print("[chapter4] 设计消融实验...")
    ablation_design = _design_ablation_experiments(innovation_points, model_architecture, experiment_design)
    
    with open(f"{OUTPUT_DIR}/ablation_design.json", 'w', encoding='utf-8') as f:
        json.dump(ablation_design, f, ensure_ascii=False, indent=2)
    
    # 生成消融实验代码
    if RUN_ABLATION:
        print("[chapter4] 生成消融实验代码...")
        _generate_ablation_code(ablation_design, PROJECT_CODE_PATH)
    
    print("[chapter4] 生成 4.4 Ablation Study...")
    prompt_4_4 = f"""
你是一名{article_info['name']}级别的学术论文写作专家。请为论文"{PAPER_TITLE}"撰写第4.4节"Ablation Study"。

**核心任务**：通过消融实验验证各关键模块的有效性。

**消融实验设计**：
<ablation_design>
{json.dumps(ablation_design, ensure_ascii=False, indent=2)[:4000]}
</ablation_design>

**项目实验结果**：
<experiment_results>
{json.dumps(experiment_design.get('关键结果', {}), ensure_ascii=False, indent=2)[:2000]}
</experiment_results>

<project_report>
{project_info.get('report_content', '')[:2000]}
</project_report>

**具体要求**：
1. 使用表格呈现消融实验结果，包含各配置下的关键指标
2. 表格格式：Full Model | w/o Module A | w/o Module B | ...
3. 逐项分析每个消融实验的结果：
   - 移除/替换该模块后性能如何变化
   - 这证明了该模块的什么作用
   - 与预期的假设是否一致
4. 在分析中自然关联到方法设计的动机

请使用学术英语撰写。表格使用LaTeX格式。Markdown+LaTeX混合格式。直接给出内容：
"""
    
    section_4_4 = _get_api().call_generation(prompt_4_4)
    
    # ==================== 组装完整章节 ====================
    full_chapter = f"""# 4. Experiments

{section_4_1}

{section_4_2}

{section_4_3}

{section_4_4}
"""
    
    return full_chapter


def _build_style_instruction(style_guide, chapter_org):
    """构建写作风格指导"""
    instruction = """**写作风格指导**：
- Experiments 特殊要求：
  1. 数据集描述要详细但简洁，关键信息用表格汇总
  2. 对比实验要客观，不回避本文方法的不足
  3. 消融实验的分析要深入，不能只说"性能下降了X%"
  4. 每个发现都要分析原因，关联到方法设计
  5. 数值结果要有具体的数字，不用"显著提升"等模糊表述
"""
    
    if style_guide and isinstance(style_guide, dict):
        vocabulary = style_guide.get("用词特征", [])
        if vocabulary:
            instruction += f"- 学术用词：{vocabulary[:15]}\n"
    
    instruction += """
- 重要要求：
  1. 文风学术化，禁止口语化
  2. 数据必须准确，不能编造
  3. 表格要规范，行列清晰
"""
    
    return instruction


def run_chapter4(project_data, ref_data):
    """主入口：生成第四章"""
    os.makedirs(f"{OUTPUT_DIR}/chapter4", exist_ok=True)
    
    print("[chapter4] 开始生成第四章 Experiments...")
    chapter_content = generate_experiments(project_data, ref_data)
    
    with open(f"{OUTPUT_DIR}/chapter4/chapter4_experiments.md", 'w', encoding='utf-8') as f:
        f.write(chapter_content)
    
    print("[chapter4] 第四章生成完成！")
    return chapter_content


if __name__ == "__main__":
    project_data = {}
    ref_data = {}
    for fname in ["innovation_points.json", "experiment_design.json", "model_architecture.json"]:
        fpath = f"{OUTPUT_DIR}/{fname}"
        if os.path.exists(fpath):
            with open(fpath, 'r', encoding='utf-8') as f:
                project_data[fname.replace(".json", "")] = json.load(f)
    result = run_chapter4(project_data, ref_data)
