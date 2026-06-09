# Motivation Candidates

## Candidate 1: Physical Signal Decoupling under Low-Resolution Sampling
- **Problem**: Traditional spectral analysis methods (e.g., 2D-DFT) fail under the low-resolution discrete angular sampling (e.g., 9x9) typical of light field cameras, making it impossible to effectively separate illumination, depth, and material information.
- **Significance**: The inability to accurately decouple these physical components causes material reflections (e.g., specularities) to severely interfere with depth estimation, limiting the application of light field technology in complex real-world scenarios.
- **Approach**: Proposes a physics-based three-layer angular signal decomposition model that decouples signals into ambient light, parallax, and material residuals, extracting geometric angular features combined with a Random Forest classifier for high-precision material classification.
- **Key Claim**: By decoupling angular signals at the physical level, this project breaks through the spectral analysis bottleneck of low-resolution sampling, providing a reliable geometric foundation for complex material scenes.

## Candidate 2: Geometric Failure of EPI on Non-Lambertian Surfaces
- **Problem**: Traditional Epipolar Plane Image (EPI) methods rely on the Lambertian assumption and completely fail on non-Lambertian surfaces (specular/scattering) where the angular cone constraint is broken, forming X-shaped patterns instead of straight lines, which cannot be fixed by mere parameter tuning.
- **Significance**: Since the real world is full of non-Lambertian materials, the physical limitations of EPI methods cause massive depth estimation errors (e.g., 5x performance degradation) in these regions, hindering the robustness of light field depth estimation.
- **Approach**: Analyzes the geometric root causes of EPI failure and designs a dual-branch adaptive routing architecture (GeometricDualMask) that uses bimodal distributions and X-shaped patterns to route Lambertian and non-Lambertian regions to dedicated processing branches.
- **Key Claim**: By revealing the physical root causes of non-Lambertian EPI failure, this project utilizes a geometry-driven dual-branch routing mechanism to fundamentally resolve depth degradation in single-EPI architectures.

## Candidate 3: Cross-Domain Data Imbalance and Generalization Bottleneck
- **Problem**: Non-Lambertian scenes are scarce and unevenly distributed in light field datasets, leading to severe model overfitting, while existing decomposition features and models lack generalization across different datasets and domains.
- **Significance**: A lack of cross-domain generalization means models only work in specific or restricted environments and cannot be deployed in multi-source, multi-scenario real-world light field applications.
- **Approach**: Constructs a unified light field dataset loader, performs global statistical validation on decomposition features (using Cohen's d effect size), and introduces a multi-domain balanced sampling training framework to mitigate overfitting caused by data scarcity.
- **Key Claim**: Through cross-domain global statistical validation and a multi-domain balanced training framework, this project ensures the strong generalizability of physical decomposition features, breaking the limits of data imbalance on model robustness.

