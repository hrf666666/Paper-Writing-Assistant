# Motivation Confirmation

## Auto-selected motivation (modify if needed):

**Direction**: Breaking the Lambertian Assumption Bottleneck
**Problem**: Current light field depth estimation heavily relies on the Lambertian assumption, lacking a unified physical and mathematical model to handle diffuse, specular, and scattering reflections.
**Significance**: Real-world scenes are dominated by non-Lambertian materials; the failure to model them physically leads to severe depth recovery errors in complex urban and mixed environments.
**Approach**: Introduces an MRI-like k-space angular frequency analysis, applying 2D-DFT to angular sampling to build a dual-mask physical model that unifies Lambertian and non-Lambertian reflection representations based on spectral energy distribution.
**Key Claim**: Mapping angular frequency spectra to physical reflection types establishes a unified optical foundation for non-Lambertian depth recovery.

## All candidates:

### Candidate 1: Breaking the Lambertian Assumption Bottleneck
- Problem: Current light field depth estimation heavily relies on the Lambertian assumption, lacking a unified physical and mathematical model to handle diffuse, specular, and scattering reflections.
- Significance: Real-world scenes are dominated by non-Lambertian materials; the failure to model them physically leads to severe depth recovery errors in complex urban and mixed environments.
- Approach: Introduces an MRI-like k-space angular frequency analysis, applying 2D-DFT to angular sampling to build a dual-mask physical model that unifies Lambertian and non-Lambertian reflection representations based on spectral energy distribution.
- Key Claim: Mapping angular frequency spectra to physical reflection types establishes a unified optical foundation for non-Lambertian depth recovery.

### Candidate 2: Mitigating EPI Texture Copying Artifacts
- Problem: Traditional Epipolar Plane Image (EPI) methods fail in non-Lambertian regions due to the violation of angular consistency assumptions, resulting in severe 'texture copying' artifacts.
- Significance: Texture copying destroys geometric structures in reflective or scattering areas, preventing single models from achieving robust depth estimation in complex, mixed-material scenes.
- Approach: Employs a pixel-wise component-aware adaptive strategy that dynamically matches specific depth estimation methods based on continuous material weights from dual masks, fused via confidence weighting and diffuse component enhancement.
- Key Claim: Dynamic, mask-guided strategy matching and confidence fusion effectively eliminate texture copying failures in non-Lambertian regions.

### Candidate 3: Reconciling Physical Rigor with Computational Efficiency
- Problem: Under limited angular sampling (e.g., 9x9), rigorous BRDF modeling and wave-vector parsing are computationally prohibitive, while pure data-driven methods overfit on small non-Lambertian datasets.
- Significance: The inability to balance physical strictness with computational cost prevents complex optical models from being deployed in practical, real-time depth estimation networks.
- Approach: Constructs a three-tier progressive inverse wave-vector parsing algorithm that combines O(HW) real-time material classification, constrained least-squares BRDF solving, and continuous weight estimation to handle mixed boundaries efficiently.
- Key Claim: A three-tier progressive parsing architecture enables real-time, physically rigorous BRDF estimation without overfitting under limited angular resolution.

---
To confirm: keep the content above as-is or edit it.
To select a different candidate: replace the auto-selected content with another candidate.
To stop the pipeline: delete this file or leave it empty.
