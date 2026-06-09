# Motivation Confirmation

## Auto-selected motivation (modify if needed):

**Direction**: Physics-Based Geometric Feature Extraction
**Problem**: Current light field depth estimation heavily relies on frequency-domain analysis, which fails under discrete, low-resolution angular sampling (e.g., 9x9) and is severely disrupted when non-Lambertian surfaces break the Epipolar Plane Image (EPI) linearity assumption.
**Significance**: Without robust feature extraction under limited angular resolution, material-induced reflections cause massive depth estimation errors, making it impossible to reliably perceive and reconstruct complex real-world scenes.
**Approach**: The project proposes a three-layer angular signal decomposition model that decouples illumination, parallax, and material residuals, replacing failing frequency-domain features with robust geometric and statistical features (like angular gradients) to accurately classify Lambertian and non-Lambertian pixels.
**Key Claim**: Overcoming the resolution limits of frequency-domain analysis requires shifting to physics-based geometric signal decomposition for reliable material-aware depth estimation.

## All candidates:

### Candidate 1: Physics-Based Geometric Feature Extraction
- Problem: Current light field depth estimation heavily relies on frequency-domain analysis, which fails under discrete, low-resolution angular sampling (e.g., 9x9) and is severely disrupted when non-Lambertian surfaces break the Epipolar Plane Image (EPI) linearity assumption.
- Significance: Without robust feature extraction under limited angular resolution, material-induced reflections cause massive depth estimation errors, making it impossible to reliably perceive and reconstruct complex real-world scenes.
- Approach: The project proposes a three-layer angular signal decomposition model that decouples illumination, parallax, and material residuals, replacing failing frequency-domain features with robust geometric and statistical features (like angular gradients) to accurately classify Lambertian and non-Lambertian pixels.
- Key Claim: Overcoming the resolution limits of frequency-domain analysis requires shifting to physics-based geometric signal decomposition for reliable material-aware depth estimation.

### Candidate 2: Domain-Balanced Training for Data Scarcity
- Problem: There is an extreme scarcity of non-Lambertian light field data and significant domain shifts between synthetic and mixed datasets, which severely hinders the training and generalization of deep depth estimation models.
- Significance: Data imbalance and domain gaps cause models to overfit to ideal Lambertian synthetic data, resulting in catastrophic performance drops when deployed in complex, mixed urban environments with diverse reflective materials.
- Approach: The project introduces a domain-balanced mixed training strategy utilizing a WeightedRandomSampler and a unified dataset interface to maximize the utilization of limited synthetic data while maintaining exposure and feature balance across different domains.
- Key Claim: Strategic domain-balanced sampling and unified mixed training are essential to bridge the data scarcity gap and ensure robust generalization in material-diverse environments.

### Candidate 3: Dual-Mask Routing for Assumption Decoupling
- Problem: Unified depth estimation networks struggle to simultaneously process Lambertian and non-Lambertian regions because the fundamental physical assumptions (EPI linearity vs. complex reflection geometry) inherently conflict within a single processing pathway.
- Significance: Forcing a single network branch to learn conflicting physical priors leads to compromised feature representations and severe depth artifacts at material boundaries and highly reflective surfaces.
- Approach: The project designs a GeometricDualMask architecture that uses material classification masks to route decoupled regions into specialized branches (Lambertian EPI branch and non-Lambertian geometric branch), followed by mask-weighted fusion to output a unified depth map.
- Key Claim: Resolving inherent physical assumption conflicts in light field depth estimation necessitates a dual-mask routing architecture that explicitly decouples and specializes processing for distinct material properties.

---
To confirm: keep the content above as-is or edit it.
To select a different candidate: replace the auto-selected content with another candidate.
To stop the pipeline: delete this file or leave it empty.
