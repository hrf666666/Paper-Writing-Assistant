# Motivation Candidates

## Candidate 1: Physical Signal Decoupling under Discrete Sampling
- **Problem**: Current light field analysis relies heavily on spectral methods (e.g., 2D-DFT) requiring continuous angular resolution, which fails on discrete hardware (e.g., 9x9 sampling) and struggles to decouple entangled illumination, depth, and material properties.
- **Significance**: The inability to extract material-specific features under practical discrete sampling limits the theoretical foundation and accuracy of depth estimation, especially for non-Lambertian surfaces where physical assumptions break down.
- **Approach**: Proposes a physics-based three-layer angular signal decomposition model that separates signals into DC (illumination), linear (depth/parallax), and residual (material) components, replacing spectral analysis with robust geometric angular features (e.g., angular gradients) tailored for discrete resolution.
- **Key Claim**: Decoupling illumination, depth, and material via physics-based three-layer decomposition and geometric features enables robust material identification under practical discrete angular sampling.

## Candidate 2: Epipolar Structure Breakdown on Non-Lambertian Surfaces
- **Problem**: Traditional light field depth estimation relies on the Lambertian assumption, but non-Lambertian surfaces (e.g., specular or glossy materials) violate this by destroying the linear Epipolar Plane Image (EPI) structures, causing severe depth estimation failures.
- **Significance**: Real-world scenes are inherently mixed with both Lambertian and non-Lambertian regions; relying on a single EPI model leads to significant artifacts and depth errors, restricting the reliability of light field 3D reconstruction in complex environments.
- **Approach**: Designs an adaptive geometric dual-mask routing architecture that generates spatial-angular masks from geometric features to route pixels into specialized Lambertian and non-Lambertian processing branches, handling distinct EPI patterns (e.g., X-shapes or bimodal distributions) adaptively.
- **Key Claim**: Overcoming the single Lambertian assumption bottleneck via adaptive dual-mask routing and specialized dual-branch processing ensures highly accurate and robust depth estimation in complex mixed-material scenes.

## Candidate 3: Domain Imbalance in Complex Mixed Scenes
- **Problem**: In real-world mixed or urban scenes, Lambertian regions typically dominate while non-Lambertian regions (e.g., glass, metal reflections) are sparse, creating a severe domain and class imbalance during model training.
- **Significance**: This data imbalance causes models to overfit to majority Lambertian features while neglecting the distinct geometric patterns of minority non-Lambertian regions, severely degrading cross-domain generalization and overall depth estimation stability.
- **Approach**: Integrates domain-balanced sampling and a WeightedRandomSampler into the dual-branch training pipeline to optimize sample distribution, ensuring stable learning and enhanced generalization across diverse and imbalanced real-world scenarios.
- **Key Claim**: Mitigating severe domain imbalance through domain-balanced sampling and weighted optimization guarantees stable training and superior cross-domain generalization for depth estimation in complex real-world scenes.

