# Motivation Confirmation

## Auto-selected motivation (modify if needed):

**Direction**: Non-Lambertian Detection in Low-Resolution Light Fields
**Problem**: Traditional frequency-domain EPI methods (e.g., 2D-DFT) fail in low angular resolution light fields (e.g., 9x9), and non-Lambertian surfaces break the angular cone constraint, severely interfering with disparity calculation.
**Significance**: Real-world scenes are full of non-Lambertian materials; failing to accurately detect and decouple these regions fundamentally limits the robustness and accuracy of light field depth estimation.
**Approach**: Proposes a three-layer angular signal decomposition physical model to decouple illumination, disparity, and material residuals, extracting geometric angular features to train a Random Forest classifier for precise pixel-level non-Lambertian masking.
**Key Claim**: Decoupling physical light transport via three-layer angular signal decomposition enables robust non-Lambertian detection in low-resolution light fields where traditional frequency methods fail.

## All candidates:

### Candidate 1: Non-Lambertian Detection in Low-Resolution Light Fields
- Problem: Traditional frequency-domain EPI methods (e.g., 2D-DFT) fail in low angular resolution light fields (e.g., 9x9), and non-Lambertian surfaces break the angular cone constraint, severely interfering with disparity calculation.
- Significance: Real-world scenes are full of non-Lambertian materials; failing to accurately detect and decouple these regions fundamentally limits the robustness and accuracy of light field depth estimation.
- Approach: Proposes a three-layer angular signal decomposition physical model to decouple illumination, disparity, and material residuals, extracting geometric angular features to train a Random Forest classifier for precise pixel-level non-Lambertian masking.
- Key Claim: Decoupling physical light transport via three-layer angular signal decomposition enables robust non-Lambertian detection in low-resolution light fields where traditional frequency methods fail.

### Candidate 2: Feature Disentanglement for Mixed-Material Scenes
- Problem: Single-branch depth estimation models suffer from feature confusion when processing heterogeneous scenes containing both Lambertian and non-Lambertian regions, leading to suboptimal depth regression.
- Significance: Complex real-world environments consist of mixed materials; feature confusion causes severe depth artifacts and errors in specific reflective or texture-rich areas, degrading overall scene understanding.
- Approach: Constructs a GeometricDualMask dual-branch architecture that uses physical masks to adaptively route Lambertian EPI features and non-Lambertian geometric features, integrating them via mask-weighted fusion to isolate material-specific processing.
- Key Claim: A dual-mask guided routing mechanism within a unified architecture prevents feature confusion by adaptively isolating and processing heterogeneous material regions for accurate depth regression.

### Candidate 3: Cross-Domain Generalization via Balanced Training
- Problem: Multi-source light field datasets suffer from severe domain imbalance and scarcity of specific non-Lambertian data, causing gradient instability and poor cross-domain generalization during training.
- Significance: Without addressing data distribution disparities, models overfit to dominant domains and degrade significantly when deployed in real-world complex scenarios, limiting their practical applicability.
- Approach: Implements a domain-balanced sampling and mixed training strategy using WeightedRandomSampler to maintain exposure and gradient balance across diverse datasets, ensuring stable convergence and improved performance in mixed urban scenes.
- Key Claim: Domain-balanced sampling and mixed training strategies overcome multi-source data scarcity and distribution imbalance, significantly boosting the model's generalization to complex real-world environments.

---
To confirm: keep the content above as-is or edit it.
To select a different candidate: replace the auto-selected content with another candidate.
To stop the pipeline: delete this file or leave it empty.
