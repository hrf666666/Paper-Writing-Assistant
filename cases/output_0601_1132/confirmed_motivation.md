# Motivation Confirmation

## Auto-selected motivation (modify if needed):

**Direction**: Physical Signal Decoupling for Low-Resolution Light Fields
**Problem**: Non-Lambertian surfaces violate the Epipolar Plane Image (EPI) linearity assumption, and traditional 2D-DFT frequency domain methods fail due to feature aliasing under real-world low angular resolutions (e.g., 9x9).
**Significance**: This failure prevents accurate material identification, causing depth estimation methods that rely on EPI linear structures to produce severe errors on complex surfaces, fundamentally limiting the applicability of light field technology in real-world scenarios.
**Approach**: Proposes a three-layer angular signal physical decomposition model to decouple signals into illumination, disparity, and material residuals, and extracts geometric angular features (e.g., angular gradients) for robust pixel-level material classification via Random Forest.
**Key Claim**: Decoupling signals at the physical level and leveraging geometric features overcomes the limitations of frequency analysis in low-resolution light fields, providing an interpretable and robust material mask for depth estimation.

## All candidates:

### Candidate 1: Physical Signal Decoupling for Low-Resolution Light Fields
- Problem: Non-Lambertian surfaces violate the Epipolar Plane Image (EPI) linearity assumption, and traditional 2D-DFT frequency domain methods fail due to feature aliasing under real-world low angular resolutions (e.g., 9x9).
- Significance: This failure prevents accurate material identification, causing depth estimation methods that rely on EPI linear structures to produce severe errors on complex surfaces, fundamentally limiting the applicability of light field technology in real-world scenarios.
- Approach: Proposes a three-layer angular signal physical decomposition model to decouple signals into illumination, disparity, and material residuals, and extracts geometric angular features (e.g., angular gradients) for robust pixel-level material classification via Random Forest.
- Key Claim: Decoupling signals at the physical level and leveraging geometric features overcomes the limitations of frequency analysis in low-resolution light fields, providing an interpretable and robust material mask for depth estimation.

### Candidate 2: Dual-Branch Routing for Mixed Reflection Scenes
- Problem: Traditional single-branch EPI networks attempt to process both the linear structures of Lambertian surfaces and the X-shaped or bimodal patterns of Non-Lambertian surfaces using the same feature extraction mechanism, leading to feature conflict and depth estimation collapse.
- Significance: Real-world scenes are inherently mixed; a single model cannot simultaneously accommodate two drastically different physical imaging laws, resulting in degraded overall depth accuracy and poor generalization across diverse environments.
- Approach: Designs a GeometricDualMask architecture that uses generated material masks to adaptively route light field features into dedicated Lambertian and Non-Lambertian branches, followed by a weighted fusion module for unified depth regression.
- Key Claim: The mask-guided dual-branch routing mechanism breaks the representation bottleneck of single networks, enabling adaptive and high-precision depth estimation for surfaces with diverse reflection properties in mixed scenes.

### Candidate 3: Mitigating Data Scarcity and Pixel-Level Label Noise
- Problem: The scarcity of Non-Lambertian data in real-world datasets causes severe overfitting, and traditional scene-level binary cross-entropy (BCE) supervision introduces significant boundary noise when generating pixel-level masks.
- Significance: Data imbalance and label noise drastically reduce the robustness of material classification and subsequent depth estimation, making models unstable in complex scenes with rich material variations and limiting engineering feasibility.
- Approach: Introduces domain-balanced sampling and weighted random samplers to alleviate data scarcity, while employing pseudo-labels based on geometric features to generate pixel-level masks, replacing scene-level supervision to minimize noise.
- Key Claim: Combining domain-balanced sampling with pixel-level pseudo-labeling effectively overcomes the long-tail distribution of Non-Lambertian data and label noise, enhancing the model's generalization and engineering feasibility on complex mixed datasets.

---
To confirm: keep the content above as-is or edit it.
To select a different candidate: replace the auto-selected content with another candidate.
To stop the pipeline: delete this file or leave it empty.
