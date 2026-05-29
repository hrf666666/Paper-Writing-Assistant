# Motivation Confirmation

## Auto-selected motivation (modify if needed):

**Direction**: Angular Frequency-Domain Material Parsing
**Problem**: Traditional light field depth estimation relies on spatial textures or simple Lambertian assumptions, failing to effectively parse Non-Lambertian reflection types, while deep learning alternatives lack physical interpretability and incur high computational costs.
**Significance**: Inaccurate identification of reflection types leads to severe depth errors in complex material regions, limiting real-world applications; furthermore, high computational complexity prevents real-time processing.
**Approach**: Analogizes 9x9 angular sampling to MRI k-space and applies 2D-DFT to the angular frequency domain. It classifies materials (diffuse, specular, scattering) based on spectral energy distribution, achieving O(HW) lightweight, physics-based parsing without heavy deep learning training.
**Key Claim**: By introducing MRI-like angular frequency analysis, the project breaks the reliance on Lambertian assumptions and heavy deep learning for material parsing with minimal computational cost and strong physical interpretability.

## All candidates:

### Candidate 1: Angular Frequency-Domain Material Parsing
- Problem: Traditional light field depth estimation relies on spatial textures or simple Lambertian assumptions, failing to effectively parse Non-Lambertian reflection types, while deep learning alternatives lack physical interpretability and incur high computational costs.
- Significance: Inaccurate identification of reflection types leads to severe depth errors in complex material regions, limiting real-world applications; furthermore, high computational complexity prevents real-time processing.
- Approach: Analogizes 9x9 angular sampling to MRI k-space and applies 2D-DFT to the angular frequency domain. It classifies materials (diffuse, specular, scattering) based on spectral energy distribution, achieving O(HW) lightweight, physics-based parsing without heavy deep learning training.
- Key Claim: By introducing MRI-like angular frequency analysis, the project breaks the reliance on Lambertian assumptions and heavy deep learning for material parsing with minimal computational cost and strong physical interpretability.

### Candidate 2: Unified Physical Modeling via Dual-Mask Modulation
- Problem: Existing light field models typically rely on a single physical assumption (e.g., pure Lambertian), causing model failure or significant accuracy degradation in mixed scenes containing diffuse, specular, and scattering materials.
- Significance: Real-world scenes are inherently mixed; the failure of single-assumption models makes light field 3D reconstruction lack robustness in practical applications and prevents the rigorous mapping of macroscopic image features to microscopic physical optical parameters.
- Approach: Proposes a dual-mask modulation mechanism combining a media mask (quantifying roughness) and an angular direction mask (representing wavevector changes). It unifies BRDF parameter estimation via least squares constrained by the dual masks, building a foundational physical framework compatible with Lambertian, Non-Lambertian, and mixed scenes.
- Key Claim: Constructing a dual-mask modulated unified physical framework bridges the gap between macroscopic image features and microscopic optical parameters, fundamentally solving the failure of single physical assumptions in complex mixed scenes.

### Candidate 3: Reflection-Aware Adaptive Depth Estimation
- Problem: Traditional Epipolar Plane Image (EPI) based depth estimation strongly assumes global view consistency, leading to complete failure and texture-copying degradation in Non-Lambertian regions (e.g., specular reflections) where this assumption is violated.
- Significance: Depth estimation failure in Non-Lambertian regions is a long-standing industry pain point that directly causes severe artifacts in high-precision 3D reconstruction under complex lighting, hindering the realization of unified all-scene depth estimation.
- Approach: Abandons the global Lambertian assumption by employing differentiated depth estimation strategies based on parsed material weights (EPI for diffuse, photometric stereo for specular, scattering models for scattering), seamlessly integrated via a pixel-level confidence-weighted fusion mechanism.
- Key Claim: Through reflection-aware adaptive strategies and confidence fusion, the project completely resolves the depth estimation degradation caused by violated view consistency in Non-Lambertian regions, advancing unified high-precision depth estimation for all scenes.

---
To confirm: keep the content above as-is or edit it.
To select a different candidate: replace the auto-selected content with another candidate.
To stop the pipeline: delete this file or leave it empty.
