# Motivation Candidates

## Candidate 1: Physical Angular Signal Decomposition
- **Problem**: Current light field methods struggle to separate illumination, depth, and material properties, especially under low angular resolution where frequency-domain features become too coarse to capture material variations.
- **Significance**: Failure to decouple material reflectance from geometric disparity causes severe depth estimation errors in non-Lambertian regions, limiting the applicability of light field technologies in real-world scenarios.
- **Approach**: Introduces a three-layer angular signal decomposition model that physically decouples signals into DC (illumination), linear (disparity), and residual (material) components, utilizing geometric features like angular gradients for high-precision material classification.
- **Key Claim**: Physically decomposing angular signals into illumination, disparity, and material components overcomes low-resolution limitations and enables robust material-aware depth estimation.

## Candidate 2: Adaptive Routing for Mixed-Material Scenes
- **Problem**: Traditional single-branch EPI networks assume pure Lambertian surfaces and suffer significant performance degradation when processing complex, mixed-material scenes containing both Lambertian and non-Lambertian regions.
- **Significance**: Real-world environments are inherently mixed-material; a unified processing pathway cannot simultaneously exploit EPI slope advantages and handle non-Lambertian anomalies, leading to massive errors at material boundaries.
- **Approach**: Designs a GeometricDualMask architecture that generates pixel-level material masks to adaptively route features into specialized Lambertian EPI and Non-Lambertian geometric branches, supported by domain-balanced sampling.
- **Key Claim**: A dual-branch architecture with geometric mask routing dynamically adapts to mixed-material scenes, preserving EPI advantages while explicitly handling non-Lambertian anomalies.

## Candidate 3: Physics-Guided EPI Boundary Definition
- **Problem**: The light field depth estimation field heavily relies on EPI line-structure assumptions but lacks a systematic theoretical definition and physical boundary analysis of why and where EPI methods fundamentally fail.
- **Significance**: Blindly tweaking network architectures without understanding the physical roots of EPI failure (e.g., non-Lambertian surfaces violating angular cone constraints) leads to wasted computational resources and stalls theoretical breakthroughs.
- **Approach**: Conducts systematic experiments across multiple research directions to rigorously prove the physical limitations of EPI methods, defining their failure boundaries and using these insights to guide the physics-based dual-mask model design.
- **Key Claim**: Systematically defining the physical boundaries and failure roots of EPI assumptions shifts the paradigm from blind empirical tuning to physics-guided architectural design.

