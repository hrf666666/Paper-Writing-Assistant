# Motivation Candidates

## Candidate 1: Adaptive Depth Estimation for Non-Lambertian Scenes
- **Problem**: Traditional light field depth estimation methods, such as EPI-based approaches, heavily rely on the global Lambertian assumption and view consistency, which are severely violated by specular or scattering materials, leading to complete depth prediction failures like texture copying.
- **Significance**: Real-world scenes inherently contain complex mixed materials and extreme non-Lambertian reflections; failure in these regions critically limits the robustness and reliability of light field technologies in practical applications like autonomous driving and 3D reconstruction.
- **Approach**: The project proposes a component-aware adaptive depth estimation strategy that abandons the global Lambertian assumption, dynamically scheduling different depth estimation branches (e.g., EPI for diffuse, photometric stereo for specular) based on continuous material weights and fusing them via component weighting.
- **Key Claim**: By adaptively scheduling depth estimation branches according to reflection types, this project overcomes the view consistency failure caused by non-Lambertian materials, achieving robust depth estimation in complex mixed scenes.

## Candidate 2: Physics-Driven Interpretability and Generalization
- **Problem**: Current mainstream light field depth estimation models are predominantly data-driven black-box neural networks lacking physical modeling of light-matter interactions, resulting in poor generalization when encountering out-of-distribution complex mixed materials or extreme non-Lambertian scenes.
- **Significance**: The absence of physical constraints and interpretability causes models to produce unreliable predictions in unforeseen real-world scenarios, hindering their deployment in safety-critical and high-precision fields like scientific computing and industrial inspection.
- **Approach**: The project constructs a dual-mask physical model and a three-layer inverse wavevector analysis framework, utilizing the rank properties of the Radiance Tensor Field (RTF) as physical constraints to unify the imaging models of Lambertian and non-Lambertian scenes from a physical optics perspective.
- **Key Claim**: By integrating dual-mask physical modeling and inverse wavevector analysis, this project deeply embeds physical optics priors into neural networks, endowing light field depth estimation with theoretical guarantees and strong generalization in complex material scenarios.

## Candidate 3: Efficient Material Classification via Frequency Analysis
- **Problem**: Accurate pixel-level reflection type classification is a prerequisite for separating non-Lambertian components, but traditional learning-based classifiers suffer from extremely low accuracy (e.g., 24.6%) under small local receptive fields (9x9 patches), while enlarging the receptive field incurs prohibitive computational costs.
- **Significance**: The inability to efficiently and accurately identify material types at the pixel level prevents the provision of reliable prior masks for non-Lambertian depth estimation, creating a bottleneck that disables subsequent adaptive depth scheduling and degrades overall system performance.
- **Approach**: The project introduces an MRI-like angular frequency analysis mechanism, analogizing 9x9 angular sampling to k-space frequency analysis, extracting angular spectrum energy distribution via 2D-DFT, and establishing a physical mapping with reflection types to achieve real-time classification with O(HW) complexity.
- **Key Claim**: By transforming light field angular sampling into frequency domain analysis and establishing physical mappings, this project achieves high-precision pixel-level material classification at a minimal computational cost under small receptive fields, providing reliable physical priors for depth estimation.

