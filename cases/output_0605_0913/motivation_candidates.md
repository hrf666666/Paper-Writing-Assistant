# Motivation Candidates

## Candidate 1: Physical Signal Decoupling for Non-Lambertian Surfaces
- **Problem**: Traditional light field depth estimation heavily relies on the linear assumption of Epipolar Plane Images (EPI), which is fundamentally broken by non-Lambertian surfaces (e.g., specular reflections), causing severe depth artifacts.
- **Significance**: Real-world scenes are filled with complex reflective materials; failing to handle non-Lambertian regions renders depth estimation unreliable for practical applications like robotics and 3D reconstruction.
- **Approach**: The project introduces a three-layer physical angular signal decomposition model to decouple signals into ambient light, parallax, and material residuals, utilizing a dual-mask mechanism to adaptively route features for Lambertian and non-Lambertian regions.
- **Key Claim**: By physically decoupling angular signals and applying dual-mask routing, the project fundamentally resolves the EPI linearity breakdown caused by complex material reflections.

## Candidate 2: Geometric Feature Extraction under Low Angular Resolution
- **Problem**: Existing material classification methods rely on high-resolution angular frequency spectrums, which become blurred and ineffective when applied to practical, low angular resolution light field data (e.g., 9x9).
- **Significance**: Hardware constraints and bandwidth limitations make high angular resolution data rare; algorithms dependent on such ideal data are impractical for real-world deployment and edge computing.
- **Approach**: Instead of frequency spectrum features, the project extracts geometric angular features (e.g., angular gradients, correlation, coefficient of variation) and employs a Random Forest classifier to achieve robust material classification under low angular resolution.
- **Key Claim**: Replacing frequency spectrum analysis with geometric angular features enables highly accurate material classification and physical prior extraction even under strict low-resolution hardware constraints.

## Candidate 3: Domain-Balanced Unified Architecture for Mixed Scenes
- **Problem**: Single-model depth estimation architectures suffer from drastic performance degradation and overfitting when trained on multi-domain mixed scenes due to severe data distribution imbalances and feature conflicts.
- **Significance**: Deploying models in dynamic, heterogeneous environments requires strong cross-domain generalization; domain-specific overfitting severely limits the scalability and robustness of unified depth estimation systems.
- **Approach**: The project designs a unified dual-mask architecture incorporating domain-balanced sampling and weighted random samplers to dynamically adjust sample weights, combined with a multi-domain mixed training strategy.
- **Key Claim**: Through domain-balanced sampling and a unified dual-path architecture, the project overcomes multi-domain data imbalance to achieve robust, generalized depth estimation across heterogeneous scenes.

