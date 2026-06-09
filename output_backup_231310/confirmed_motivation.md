# Motivation Confirmation

## Auto-selected motivation (modify if needed):

**Direction**: Physical Signal Decoupling
**Problem**: Current light field depth estimation methods rely on 2D-DFT frequency analysis which fails at low angular resolutions, making it impossible to effectively decouple depth from material properties and causing non-Lambertian reflections to corrupt Epipolar Plane Image (EPI) slope calculations.
**Significance**: The coupling of material and depth is the root cause of EPI assumption failure on non-Lambertian surfaces; without accurate material priors, the upper bound and robustness of depth estimation networks are severely limited.
**Approach**: Proposes a three-layer angular signal decomposition physical model to decouple signals into ambient light, parallax, and material residuals, replacing frequency features with geometric angular features to train a classifier for pixel-level material perception.
**Key Claim**: Decoupling angular signals via physical modeling and geometric features overcomes low angular resolution limits to provide reliable material priors for light field depth estimation.

## All candidates:

### Candidate 1: Physical Signal Decoupling
- Problem: Current light field depth estimation methods rely on 2D-DFT frequency analysis which fails at low angular resolutions, making it impossible to effectively decouple depth from material properties and causing non-Lambertian reflections to corrupt Epipolar Plane Image (EPI) slope calculations.
- Significance: The coupling of material and depth is the root cause of EPI assumption failure on non-Lambertian surfaces; without accurate material priors, the upper bound and robustness of depth estimation networks are severely limited.
- Approach: Proposes a three-layer angular signal decomposition physical model to decouple signals into ambient light, parallax, and material residuals, replacing frequency features with geometric angular features to train a classifier for pixel-level material perception.
- Key Claim: Decoupling angular signals via physical modeling and geometric features overcomes low angular resolution limits to provide reliable material priors for light field depth estimation.

### Candidate 2: EPI Assumption Conflict Resolution
- Problem: Traditional single-branch EPI architectures face severe assumption conflicts in mixed scenes, as the EPI slope consistency designed for Lambertian surfaces completely fails in non-Lambertian and complex texture regions due to structural destruction and slope blurring.
- Significance: Real-world scenes are inherently mixed; a single network branch cannot simultaneously accommodate the distinct physical properties of Lambertian and non-Lambertian surfaces, leading to drastic accuracy drops in complex areas.
- Approach: Constructs a GeometricDualMask architecture that uses material-aware dual masks to route and process Lambertian and non-Lambertian regions through separate branches, integrating 4-directional EPI feature extraction and physical consistency constraints for targeted fusion.
- Key Claim: Introducing a dual-mask routing mechanism resolves the assumption conflicts of single EPI architectures, enabling adaptive processing of complex mixed Lambertian and non-Lambertian light field scenes.

### Candidate 3: Data Scarcity and Domain Generalization
- Problem: Light field depth estimation models suffer from severe domain imbalance during training, particularly due to the extreme scarcity of real non-Lambertian light field scene data, causing models to easily overfit to minority domains and lose generalization.
- Significance: The long-tail effect of data distribution and domain shift prevent models trained on synthetic or simple datasets from being applied to real urban or mixed scenes with rich materials and lighting variations, hindering practical deployment.
- Approach: Designs and implements a domain-balanced sampling and weighted random sampler strategy to dynamically adjust sampling weights across different data domains, jointly training with multi-domain datasets to maximize generalization under hard data constraints.
- Key Claim: Overcoming the bottleneck of extreme non-Lambertian data scarcity through domain-balanced sampling significantly enhances the generalization performance of unified light field depth estimation frameworks in complex mixed scenes.

---
To confirm: keep the content above as-is or edit it.
To select a different candidate: replace the auto-selected content with another candidate.
To stop the pipeline: delete this file or leave it empty.
