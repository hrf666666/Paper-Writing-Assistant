# Motivation Candidates

## Candidate 1: Angular Frequency-Domain Material Perception
- **Problem**: Traditional light field processing relies heavily on spatial textures or Epipolar Plane Image (EPI) slope features, which fail in Non-Lambertian scenes due to complex reflection properties, lacking effective representation of the physical essence of material reflection.
- **Significance**: Inaccurate material perception leads to severe artifacts and errors in downstream tasks like depth estimation and novel view synthesis under complex lighting, limiting the deployment of light field technologies in real-world mixed-material environments.
- **Approach**: Proposes an MRI-inspired angle-frequency domain analysis mechanism that treats 9x9 angular sampling as k-space encoding. It applies 2D-FFT to extract angular spectrum energy features, establishing a physical mapping between frequency spectrums and material types (diffuse, specular, scatter) for lightweight, interpretable pixel-level classification.
- **Key Claim**: By introducing angular frequency domain analysis to reveal the physical essence of material reflection, this approach breaks through the limitations of traditional spatial features in Non-Lambertian scenes.

## Candidate 2: Physically Interpretable BRDF Parameter Parsing
- **Problem**: Existing deep learning-based light field models act as black boxes lacking explicit physical meaning, making it difficult to effectively quantify and separate complex optical interactions of multiple overlapping materials within mixed pixels.
- **Significance**: Black-box models without physical constraints suffer from poor generalization under complex lighting and unseen materials, and cannot provide physically meaningful parameters, hindering downstream applications in physical rendering, relighting, and reverse engineering.
- **Approach**: Constructs a dual-mask physical modulation and BRDF parameter parsing model. It designs a medium mask and an angular direction mask, combining constrained least squares optimization with 81-view equations and reverse wave-vector parsing to solve for diffuse, specular, and scattering BRDF weights, transitioning from coarse classification to complete physical modeling.
- **Key Claim**: Transforming black-box deep learning into physically meaningful BRDF parameter estimation significantly enhances the physical interpretability and generalization of models in complex mixed-material scenes.

## Candidate 3: Component-Aware Unified Depth Estimation
- **Problem**: Traditional light field depth estimation methods strictly rely on the Lambertian view-consistency assumption, which is fundamentally violated in Non-Lambertian regions like specular reflections or scattering, causing the depth estimation to completely collapse.
- **Significance**: Real-world scenes almost always contain mixed materials. A single-strategy approach cannot handle these diverse regions simultaneously, resulting in large-area holes and severe errors in depth maps, which fails to meet the requirements of high-precision 3D reconstruction.
- **Approach**: Designs a component-aware and confidence-weighted unified depth estimation strategy. It dynamically adjusts depth estimation branches based on material classification (EPI for diffuse, photometric stereo for specular, and scattering models for scatter) and fuses the component depths via pixel-level confidence weighting, achieving unified processing across Lambertian, Non-Lambertian, and mixed scenes.
- **Key Claim**: By dynamically adapting to the physical properties of different reflection components and weighting their fusion, this strategy fundamentally resolves the depth collapse caused by EPI assumption failures, achieving truly unified high-precision light field depth estimation.

