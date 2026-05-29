# Motivation Confirmation

## Auto-selected motivation (modify if needed):

**Direction**: Unified Physical Modeling of Light-Matter Interaction
**Problem**: Current light field depth estimation relies heavily on a single Lambertian assumption, lacking a unified theoretical framework to handle diverse light-matter interactions like specular reflection and scattering.
**Significance**: This fundamental limitation causes severe depth estimation failures in non-Lambertian and mixed urban scenes, as the physical root causes of Epipolar Plane Image (EPI) violations remain unaddressed.
**Approach**: The project proposes a dual-mask modulation mechanism (medium and angular masks) combined with Radiance Tensor Field (RTF) rank analysis to build a unified physical model that seamlessly accommodates diffuse, specular, and scattering scenarios.
**Key Claim**: Establishing a unified physical framework beyond the Lambertian assumption is critical for fundamentally resolving depth estimation failures in complex real-world scenes.

## All candidates:

### Candidate 1: Unified Physical Modeling of Light-Matter Interaction
- Problem: Current light field depth estimation relies heavily on a single Lambertian assumption, lacking a unified theoretical framework to handle diverse light-matter interactions like specular reflection and scattering.
- Significance: This fundamental limitation causes severe depth estimation failures in non-Lambertian and mixed urban scenes, as the physical root causes of Epipolar Plane Image (EPI) violations remain unaddressed.
- Approach: The project proposes a dual-mask modulation mechanism (medium and angular masks) combined with Radiance Tensor Field (RTF) rank analysis to build a unified physical model that seamlessly accommodates diffuse, specular, and scattering scenarios.
- Key Claim: Establishing a unified physical framework beyond the Lambertian assumption is critical for fundamentally resolving depth estimation failures in complex real-world scenes.

### Candidate 2: Efficient Material Parsing via Angular Frequency Analysis
- Problem: Extracting fine-grained material properties and BRDF parameters from sparse angular sampling (e.g., 9x9 light fields) is computationally expensive and typically relies on heavy neural networks.
- Significance: Inefficient material parsing bottlenecks real-time applications and prevents the accurate, pixel-level identification needed to guide adaptive physical models in downstream depth estimation.
- Approach: Inspired by MRI k-space encoding, the project applies 2D-DFT to pixel-level angular distributions, mapping frequency spectrum features to reflection types and enabling O(HW) real-time material classification and BRDF estimation.
- Key Claim: Cross-disciplinary frequency domain analysis enables highly efficient, network-free material parsing from sparse light fields, unlocking real-time adaptive processing.

### Candidate 3: Component-Aware Adaptive Depth Fusion
- Problem: Traditional EPI-based depth estimation methods suffer from severe texture copying artifacts and depth collapse in non-Lambertian regions due to the breakdown of angular photo-consistency.
- Significance: These localized failures drastically compromise the overall reliability and robustness of 3D reconstruction in practical environments featuring highly reflective, transparent, or mixed-material surfaces.
- Approach: The project introduces a component-aware adaptive strategy that dynamically applies tailored depth estimation models (EPI, photometric stereo, or scattering corrections) based on material weights, fused via a confidence-weighted loss function.
- Key Claim: Dynamically adapting depth estimation strategies to local material components effectively circumvents EPI consistency violations and ensures robust depth mapping across mixed-material scenes.

---
To confirm: keep the content above as-is or edit it.
To select a different candidate: replace the auto-selected content with another candidate.
To stop the pipeline: delete this file or leave it empty.
