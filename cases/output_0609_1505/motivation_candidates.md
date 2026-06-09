# Motivation Candidates

## Candidate 1: Non-Lambertian Interference
- **Problem**: Current light field depth estimation heavily relies on the Epipolar Plane Image (EPI) linearity assumption, which is fundamentally broken by Non-Lambertian surfaces (e.g., specular highlights, scattering), causing severe depth artifacts and estimation failures.
- **Significance**: Non-Lambertian materials are ubiquitous in real-world environments; failing to handle their complex reflections restricts the robustness and practical deployment of depth estimation models in autonomous driving, robotics, and other complex physical scenarios.
- **Approach**: The project introduces a three-layer angular signal decomposition physical model to decouple light fields into ambient, depth, and material residual components, and employs a Geometric Dual-Mask network to adaptively route features based on identified material properties.
- **Key Claim**: Decoupling angular signals via physical priors and dual-mask routing fundamentally resolves depth estimation failures caused by Non-Lambertian surface reflections.

## Candidate 2: Cross-Domain Generalization Bottleneck
- **Problem**: Existing models are typically trained on single-domain datasets and suffer from long-tail distributions and class imbalance across multi-domain data, leading to severe performance degradation when applied to diverse, real-world mixed scenes.
- **Significance**: Real-world applications require models to generalize seamlessly across varying environments (e.g., synthetic to real, indoor to urban); poor cross-domain generalization prevents the standardization and scalable deployment of light field technologies.
- **Approach**: It constructs a Unified LF Dataset Loader compatible with multiple ground-truth formats and introduces a domain-balanced sampling and mixed training strategy (using WeightedRandomSampler) to maintain cross-domain exposure and class balance during joint training.
- **Key Claim**: Overcoming single-dataset limitations through domain-balanced mixed training and unified data paradigms significantly maximizes the generalization capability in complex real-world scenarios.

## Candidate 3: Incomplete EPI Utilization and Black-Box Modeling
- **Problem**: Traditional methods often underutilize the multi-directional geometric structures of light fields by relying on limited EPI directions, while purely data-driven deep learning models lack physical interpretability to reliably handle complex optical phenomena.
- **Significance**: Incomplete feature extraction limits the theoretical performance ceiling of EPI-based methods, and the lack of physical interpretability makes models fragile and unpredictable when facing out-of-distribution lighting or material conditions.
- **Approach**: The project develops the EPINet4Dir V3 architecture to comprehensively extract horizontal, vertical, and dual-diagonal EPI slope features, while integrating the physically interpretable angular signal decomposition to guide and constrain the depth regression process.
- **Key Claim**: Maximizing multi-directional EPI structural extraction while embedding physically interpretable priors bridges the gap between data-driven performance and optical physical consistency.

