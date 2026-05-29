# Motivation Candidates

## Candidate 1: Non-Lambertian Depth Estimation Failure
- **Problem**: Traditional light field depth estimation methods, such as Epipolar Plane Image (EPI) analysis, rely heavily on the photo-consistency assumption, which fatally fails in non-Lambertian (specular and scattering) regions, causing depth predictions to degenerate into mere texture copying.
- **Significance**: Real-world environments are predominantly composed of non-Lambertian and mixed materials. The inability to accurately estimate depth in these regions severely compromises the reliability of 3D reconstruction and downstream vision tasks in practical applications.
- **Approach**: The project introduces a component-aware adaptive depth estimation fusion strategy that decouples the depth estimation task based on material weights. It applies specialized strategies for diffuse (EPI), specular (photometric stereo/neighborhood propagation), and scattering regions, followed by a weighted fusion to generate a unified depth map.
- **Key Claim**: By decoupling reflection components and applying tailored estimation strategies, this approach completely resolves the fatal depth estimation failure caused by the violation of photo-consistency in non-Lambertian regions.

## Candidate 2: Lack of Physical Interpretability in Data-Driven Models
- **Problem**: Existing deep learning-based light field models are largely black-box and data-driven, lacking explicit physical modeling of light-matter interactions, which makes it difficult to uniformly and robustly handle Lambertian, non-Lambertian, and mixed material scenes.
- **Significance**: Without physical constraints, these models exhibit poor generalization under unseen complex lighting and mixed materials, and fail to provide physically meaningful intermediate representations, limiting their deployment in rigorous physical and geometric vision tasks.
- **Approach**: It constructs a Dual-Mask Physical Modeling framework based on the physical assumption of the Radiance Tensor Field (RTF) rank. By generating a media mask for surface roughness and an angular mask for wavevector deflection, it estimates BRDF parameters via constrained least squares to unify the modeling of all reflection types.
- **Key Claim**: Integrating dual-mask physical modeling transforms black-box networks into a unified, physically interpretable framework capable of adaptively processing mixed materials and complex illumination conditions.

## Candidate 3: Reflection Parsing Bottleneck under Limited Angular Sampling
- **Problem**: Light field cameras typically capture limited angular sampling (e.g., 9x9 views), creating a severe bottleneck for traditional methods attempting to distinguish complex material reflection types (diffuse, specular, scattering) from such sparse angular data.
- **Significance**: Accurate, pixel-level material classification is a critical prerequisite for depth estimation and illumination separation in non-Lambertian scenes. Misclassification directly propagates into severe errors in subsequent geometric and physical parameter estimations.
- **Approach**: The project proposes an MRI-inspired angular frequency analysis method that applies 2D-DFT to the 9x9 angular samples, transforming them into the angular frequency domain. It leverages spectral energy distribution characteristics (low-frequency for diffuse, high-frequency for specular, mid-frequency for scattering) to achieve lightweight, real-time material classification with O(HW) complexity.
- **Key Claim**: By adapting MRI-inspired frequency domain analysis to sparse angular samples, this method breaks through traditional limitations to achieve highly efficient, physically grounded pixel-level classification of complex reflection types.

