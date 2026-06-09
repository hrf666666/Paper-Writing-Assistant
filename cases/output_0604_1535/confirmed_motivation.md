# Motivation Confirmation

## Auto-selected motivation (modify if needed):

**Direction**: EPI Assumption Failure on Non-Lambertian Surfaces
**Problem**: Traditional light field depth estimation heavily relies on the linear structure assumption of Epipolar Plane Images (EPI), but non-Lambertian materials (e.g., specular reflection, subsurface scattering) violate the angular cone constraint, causing EPI line structures to break (e.g., forming X-patterns) and depth estimation to fail.
**Significance**: Real-world scenes are filled with complex reflective materials; the inability to handle non-Lambertian surfaces severely limits the reliability and practical application of light field depth estimation in unconstrained environments.
**Approach**: The project systematically defines the physical boundaries of EPI failure and proposes a dual-branch architecture. It uses a three-layer angular signal decomposition to extract geometric features for pixel-wise mask generation, routing Lambertian and non-Lambertian regions to specialized EPI and geometric branches respectively.
**Key Claim**: By defining the physical boundaries of EPI failure and employing a dual-branch mask-routing mechanism, this project fundamentally resolves depth estimation failures caused by non-Lambertian materials.

## All candidates:

### Candidate 1: EPI Assumption Failure on Non-Lambertian Surfaces
- Problem: Traditional light field depth estimation heavily relies on the linear structure assumption of Epipolar Plane Images (EPI), but non-Lambertian materials (e.g., specular reflection, subsurface scattering) violate the angular cone constraint, causing EPI line structures to break (e.g., forming X-patterns) and depth estimation to fail.
- Significance: Real-world scenes are filled with complex reflective materials; the inability to handle non-Lambertian surfaces severely limits the reliability and practical application of light field depth estimation in unconstrained environments.
- Approach: The project systematically defines the physical boundaries of EPI failure and proposes a dual-branch architecture. It uses a three-layer angular signal decomposition to extract geometric features for pixel-wise mask generation, routing Lambertian and non-Lambertian regions to specialized EPI and geometric branches respectively.
- Key Claim: By defining the physical boundaries of EPI failure and employing a dual-branch mask-routing mechanism, this project fundamentally resolves depth estimation failures caused by non-Lambertian materials.

### Candidate 2: Material Feature Extraction Bottleneck at Low Angular Resolution
- Problem: Existing light field material classification and feature extraction methods predominantly rely on frequency-domain analyses like 2D-DFT, which severely fail under the low angular resolution (e.g., 9x9 discrete sampling) commonly found in practical hardware.
- Significance: High angular resolution light field data is extremely costly to capture and process; if algorithms only work under ideal high-resolution conditions, it heavily restricts the deployment of light field technologies in consumer-grade devices and real-time systems.
- Approach: Abandoning ineffective frequency-domain methods, the project introduces a three-layer angular signal decomposition model that decouples signals into DC, linear, and residual components, extracting geometric features (e.g., angular gradient) to achieve highly accurate pixel-level material classification via Random Forest.
- Key Claim: By replacing traditional frequency-domain analysis with physical geometric features, this project breaks through the material recognition bottleneck under low angular resolution discrete sampling.

### Candidate 3: Model Generalization Dilemma Caused by Multi-Domain Data Imbalance
- Problem: Light field depth estimation models suffer from uneven multi-domain data distributions during training, where specific domains (especially those with scarce non-Lambertian or complex scenes) cause severe overfitting and poor generalization in mixed scenarios.
- Significance: Models lacking cross-domain generalization cannot handle the complex, variable scenes of the open world, leading to drastic performance drops when deployed on different datasets or in real-world applications.
- Approach: The project constructs a unified light field dataset loader and designs a domain-balanced sampling and mixed training strategy. By utilizing WeightedRandomSampler to dynamically maintain cross-domain exposure balance, it jointly trains a unified 4-direction EPI architecture to boost overall generalization.
- Key Claim: Through domain-balanced sampling and multi-domain joint training strategies, this project breaks down data distribution barriers to achieve robust generalization in complex mixed light field scenes.

---
To confirm: keep the content above as-is or edit it.
To select a different candidate: replace the auto-selected content with another candidate.
To stop the pipeline: delete this file or leave it empty.
