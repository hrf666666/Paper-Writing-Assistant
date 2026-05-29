# Motivation Confirmation

## Auto-selected motivation (modify if needed):

**Direction**: Angular Frequency Physical Representation
**Problem**: Traditional light field depth estimation relies solely on spatial textures or EPI slopes, lacking the ability to decouple and distinguish Lambertian from non-Lambertian reflections.
**Significance**: The inability to accurately identify reflection types causes severe depth estimation failures in complex, real-world mixed scenes, limiting the robustness and applicability of light field technologies.
**Approach**: It introduces MRI-like k-space frequency domain analysis to the angular sampling matrix, establishing a physical mapping between reflection types and angular spectra, and uses a dual-mask mechanism to decouple light-matter interactions.
**Key Claim**: By leveraging angular frequency analysis and dual-masking, this project overcomes spatial-domain limitations to achieve precise, pixel-level physical material representation.

## All candidates:

### Candidate 1: Angular Frequency Physical Representation
- Problem: Traditional light field depth estimation relies solely on spatial textures or EPI slopes, lacking the ability to decouple and distinguish Lambertian from non-Lambertian reflections.
- Significance: The inability to accurately identify reflection types causes severe depth estimation failures in complex, real-world mixed scenes, limiting the robustness and applicability of light field technologies.
- Approach: It introduces MRI-like k-space frequency domain analysis to the angular sampling matrix, establishing a physical mapping between reflection types and angular spectra, and uses a dual-mask mechanism to decouple light-matter interactions.
- Key Claim: By leveraging angular frequency analysis and dual-masking, this project overcomes spatial-domain limitations to achieve precise, pixel-level physical material representation.

### Candidate 2: Lightweight Physics-Based BRDF Estimation
- Problem: Current BRDF parameter estimation for non-Lambertian scenes heavily relies on massive neural networks and large-scale annotated datasets, leading to severe overfitting when data is scarce.
- Significance: Acquiring multi-angle light field data with precise physical material annotations is prohibitively expensive, making data-hungry models impractical for real-world physical rendering and material analysis.
- Approach: It designs a progressive inverse wavevector analysis mechanism that formulates a constrained least-squares model using inherent multi-angle sampling, ensuring physical consistency with Maxwell's equations without heavy networks.
- Key Claim: It eliminates the reliance on massive annotated data by exploiting inherent light field physical constraints for lightweight, overfitting-resistant BRDF parameter estimation.

### Candidate 3: Component-Aware Adaptive Depth Estimation
- Problem: Traditional EPI-based depth estimation methods enforce a strict global Lambertian assumption, which completely fails in non-Lambertian regions where view-consistency is violated.
- Significance: Real-world scenes are inherently composed of mixed Lambertian and non-Lambertian materials; single-strategy depth networks suffer from poor generalization and severe artifacts in such complex environments.
- Approach: It proposes a component-aware adaptive fusion architecture that dynamically adjusts depth estimation strategies based on material weights and optimizes the final depth map via confidence-weighted fusion.
- Key Claim: Breaking the global Lambertian assumption, it achieves unified, high-precision depth estimation in complex mixed scenes through component-aware, multi-strategy adaptive fusion.

---
To confirm: keep the content above as-is or edit it.
To select a different candidate: replace the auto-selected content with another candidate.
To stop the pipeline: delete this file or leave it empty.
