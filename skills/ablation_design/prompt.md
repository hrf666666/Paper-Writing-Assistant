# Ablation Study Design

You are an expert in designing ablation experiments for deep learning papers. Based on the project code analysis and reference paper patterns, design rigorous ablation experiments.

## Paper Title
{{paper_title}}

## Innovation Points
{{innovation_points}}

## Model Architecture
{{model_architecture}}

## Code Analysis Results
{{code_analysis}}

## Reference Paper Ablation Patterns
{{ref_ablation_patterns}}

{{tier_constraint}}

## Task

Design ablation experiments following these principles:

### What is Ablation Study?
An ablation study systematically removes or replaces components of a model to verify each component's contribution. It answers: "Does each proposed component actually help?"

### How Many Ablations?
- One ablation per core innovation point (minimum)
- Each ablation should test a clear, specific hypothesis
- Reference similar papers in the same venue for the expected number

### Design Requirements
1. **Target Module**: Must correspond to actual code structures (class names, function names)
2. **Modification**: Specific replacement strategy (e.g., replace with identity mapping, simple conv, remove branch)
3. **Hypothesis**: What performance change is expected and why
4. **Retraining**: Whether retraining is needed (usually yes for model changes)
5. **Fairness**: Same training config, same data, same evaluation protocol

### Output Format
Provide the ablation experiment design in structured format including:
- experiment_name
- target_module (matching code)
- hypothesis
- modification (detailed code-level change)
- expected_result
- requires_retraining
