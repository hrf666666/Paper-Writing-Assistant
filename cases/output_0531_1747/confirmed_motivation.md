# Motivation Confirmation

## Auto-selected motivation (modify if needed):

**Direction**: Physics-Based Signal Decoupling for Low-Resolution Light Fields
**Problem**: Current light field depth estimation methods heavily rely on high-resolution angular frequency spectrums (e.g., 2D-DFT), which fail and become ineffective under low angular resolution conditions (e.g., 9x9 sampling).
**Significance**: Low angular resolution is standard in practical, consumer-grade light field cameras. The inability to extract reliable material and depth features under these conditions severely limits the real-world applicability and robustness of depth estimation models.
**Approach**: The project introduces a three-layer angular signal decomposition physical model that decouples the signal into illumination (DC), depth (linear), and material (residual) components. It extracts geometric features like angular gradients from the residual to train a Random Forest classifier, achieving high-accuracy material classification without relying on high-resolution spectrums.
**Key Claim**: Decoupling light field signals via a physics-based three-layer model enables robust material and depth feature extraction even under low angular resolution constraints.

## All candidates:

### Candidate 1: Physics-Based Signal Decoupling for Low-Resolution Light Fields
- Problem: Current light field depth estimation methods heavily rely on high-resolution angular frequency spectrums (e.g., 2D-DFT), which fail and become ineffective under low angular resolution conditions (e.g., 9x9 sampling).
- Significance: Low angular resolution is standard in practical, consumer-grade light field cameras. The inability to extract reliable material and depth features under these conditions severely limits the real-world applicability and robustness of depth estimation models.
- Approach: The project introduces a three-layer angular signal decomposition physical model that decouples the signal into illumination (DC), depth (linear), and material (residual) components. It extracts geometric features like angular gradients from the residual to train a Random Forest classifier, achieving high-accuracy material classification without relying on high-resolution spectrums.
- Key Claim: Decoupling light field signals via a physics-based three-layer model enables robust material and depth feature extraction even under low angular resolution constraints.

### Candidate 2: Unified Dual-Branch Routing for Mixed Reflectance Surfaces
- Problem: Existing Epipolar Plane Image (EPI) based networks are fundamentally bottlenecked by the strict Lambertian assumption, making them incapable of simultaneously handling both Lambertian and non-Lambertian (e.g., specular, glossy) surfaces within a single unified model.
- Significance: Real-world scenes are inherently composed of mixed materials. Failing to accurately estimate depth for non-Lambertian regions leads to significant artifacts and severe performance degradation in complex, mixed urban or indoor environments.
- Approach: The project develops the GeometricDualMask architecture, utilizing physics-based material priors to generate dual masks. These masks route Lambertian and non-Lambertian pixels to specialized processing branches with tailored physical constraints, fusing them adaptively to achieve high-precision depth estimation across mixed domains.
- Key Claim: A dual-mask routing architecture driven by geometric material priors overcomes the Lambertian bottleneck, enabling unified and accurate depth estimation for complex mixed-reflectance scenes.

### Candidate 3: Quantifying the Physical Boundaries and Root Causes of EPI Failures
- Problem: The fundamental physical mechanisms and theoretical performance boundaries of why EPI assumptions fail on non-Lambertian surfaces and complex textures remain poorly understood, leading to blind optimization of network structures and hyperparameters.
- Significance: Without knowing the physical limits of EPI-based methods, researchers waste massive computational resources on ineffective architectural tweaks, stalling progress in light field depth estimation and delaying the transition to more suitable paradigms.
- Approach: The project conducts an exhaustive quantitative analysis through 132 experiments, systematically proving that non-Lambertian surfaces break angular cone constraints (creating X-patterns) and complex textures blur EPI slopes. This identifies physical assumption violations and data scarcity as the true root causes of performance bottlenecks rather than network design flaws.
- Key Claim: Systematically quantifying the physical failure mechanisms of EPI assumptions establishes clear theoretical boundaries, redirecting future research away from futile network tuning toward fundamentally new paradigms.

---
To confirm: keep the content above as-is or edit it.
To select a different candidate: replace the auto-selected content with another candidate.
To stop the pipeline: delete this file or leave it empty.
