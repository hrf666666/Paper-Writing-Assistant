# Motivation Confirmation

## Auto-selected motivation (modify if needed):

**Direction**: Unified Multi-Domain Depth Estimation
**Problem**: Current light field depth estimation models are typically tailored for single reflectance properties, lacking a unified baseline for mixed scenes, and suffer from severe data distribution imbalance during multi-domain joint training.
**Significance**: Real-world scenes inherently contain mixed reflectance characteristics; models failing to generalize across Lambertian, Non-Lambertian, and mixed domains severely limit the practical deployment and robustness of light field technologies.
**Approach**: The project introduces the lightweight EPINet4Dir V3 model featuring dual-mask modeling and multi-directional EPI mechanisms, coupled with a domain-balanced sampling strategy across five diverse datasets to unify multi-domain processing.
**Key Claim**: By integrating a dual-mask multi-directional EPI architecture with domain-balanced training, this project establishes a robust and lightweight unified baseline for light field depth estimation across diverse reflectance domains.

## All candidates:

### Candidate 1: Unified Multi-Domain Depth Estimation
- Problem: Current light field depth estimation models are typically tailored for single reflectance properties, lacking a unified baseline for mixed scenes, and suffer from severe data distribution imbalance during multi-domain joint training.
- Significance: Real-world scenes inherently contain mixed reflectance characteristics; models failing to generalize across Lambertian, Non-Lambertian, and mixed domains severely limit the practical deployment and robustness of light field technologies.
- Approach: The project introduces the lightweight EPINet4Dir V3 model featuring dual-mask modeling and multi-directional EPI mechanisms, coupled with a domain-balanced sampling strategy across five diverse datasets to unify multi-domain processing.
- Key Claim: By integrating a dual-mask multi-directional EPI architecture with domain-balanced training, this project establishes a robust and lightweight unified baseline for light field depth estimation across diverse reflectance domains.

### Candidate 2: Frequency-Domain Material Classification Boundaries
- Problem: The research community harbors a misconception that low angular resolution light fields (e.g., 9x9) can effectively classify materials (diffuse vs. specular) using frequency-domain features analogous to MRI k-space analysis.
- Significance: This flawed assumption misdirects research efforts toward ineffective algorithmic designs and inadequate hardware configurations, fundamentally stalling the progress of frequency-based light field material analysis.
- Approach: The project rigorously falsifies the 'MRI-like angular frequency analysis' hypothesis through four independent analytical methods and quantitatively defines the resolution boundary by comparing effective non-DC frequency points with BRDF requirements.
- Key Claim: By strictly falsifying the viability of frequency-domain material classification at 9x9 angular resolution, this work establishes clear hardware and theoretical boundaries to prevent futile research efforts in low-resolution light field analysis.

### Candidate 3: EPI Architecture Performance Ceilings
- Problem: Epipolar Plane Image (EPI) architectures exhibit a distinct performance ceiling in complex Lambertian scenes, yet the community lacks a systematic understanding of the root causes, such as edge assumption flaws and Ground Truth (GT) degradation.
- Significance: Without identifying the theoretical performance lower bounds and fundamental failure modes of EPI methods, researchers risk blindly optimizing network structures without overcoming intrinsic bottlenecks, hindering ultimate depth estimation accuracy.
- Approach: The project systematically evaluates the performance limits of EPI methods on large-scale mixed datasets, deeply analyzes root causes like view-consistency edge flaws and GT degradation, and quantitatively determines the theoretical performance bounds via resolution scaling and GT exclusion experiments.
- Key Claim: This project systematically probes and defines the performance ceiling of EPI architectures in complex Lambertian scenes, uncovering intrinsic bottlenecks to guide the design of next-generation light field depth estimation frameworks.

---
To confirm: keep the content above as-is or edit it.
To select a different candidate: replace the auto-selected content with another candidate.
To stop the pipeline: delete this file or leave it empty.
