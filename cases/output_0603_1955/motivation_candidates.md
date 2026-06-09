# Motivation Candidates

## Candidate 1: Low-Resolution Material Decoupling
- **Problem**: Traditional frequency-domain methods fail to reliably decouple and classify materials under low angular resolution (e.g., 9x9 discrete sampling) in light field imaging.
- **Significance**: Failing to separate material reflections from depth cues causes networks to blindly learn noise that violates physical assumptions, fundamentally limiting depth estimation accuracy in complex scenes.
- **Approach**: Introduces a three-layer physical decomposition model to isolate residual material signals and extracts robust geometric angular features (like angular gradient) to achieve high-precision pixel-level material classification via a Random Forest classifier.
- **Key Claim**: Geometric feature extraction overcomes the frequency-domain bottleneck to reliably decouple material and depth in low-resolution light fields.

## Candidate 2: EPI Assumption Failure on Non-Lambertian Surfaces
- **Problem**: The core Epipolar Plane Image (EPI) linearity assumption inherently breaks down on non-Lambertian surfaces due to the violation of the Angular Cone Constraint, resulting in fractured or X-shaped EPI structures.
- **Significance**: Applying a global EPI assumption across mixed-material scenes amplifies errors in reflective regions, making it impossible to achieve robust and accurate depth estimation for real-world objects.
- **Approach**: Designs a GeometricDualMask network architecture that uses physically derived masks to explicitly route Lambertian and non-Lambertian features into dedicated dual branches, adaptively fusing them to respect local physical constraints.
- **Key Claim**: Dual-mask routing explicitly isolates non-Lambertian regions to prevent the catastrophic error amplification caused by invalid global EPI assumptions.

## Candidate 3: Non-Lambertian Data Scarcity and Overfitting
- **Problem**: Deep learning models suffer from severe overfitting in non-Lambertian light field depth estimation due to the extreme scarcity of real non-Lambertian training data compared to massive synthetic Lambertian datasets.
- **Significance**: This long-tail data distribution prevents models from generalizing to real-world urban and mixed environments, rendering them impractical for deployment in complex reflective scenes.
- **Approach**: Implements a domain-balanced sampling strategy combined with a mixed training mechanism to effectively leverage large-scale synthetic data while maintaining multi-domain exposure balance and preventing overfitting.
- **Key Claim**: Domain-balanced sampling resolves the long-tail data distribution issue to unlock robust generalization in mixed and non-Lambertian light field scenes.

