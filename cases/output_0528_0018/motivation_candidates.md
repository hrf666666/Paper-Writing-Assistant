# Motivation Candidates

## Candidate 1: Unified Depth Estimation for Mixed Reflectance
- **Problem**: Traditional light field depth estimation models struggle to simultaneously handle Lambertian and Non-Lambertian scenes, leading to significant performance drops in complex mixed environments, while existing unified models are often computationally heavy.
- **Significance**: Real-world scenes predominantly consist of mixed materials; lacking cross-reflectance generalization severely limits practical deployment, and high computational overhead hinders edge-device applications.
- **Approach**: Designs a dual-mask modeling mechanism combining medium and angular direction masks, constructs a multi-directional EPI network, and integrates pure defocus and angular frequency branches to achieve end-to-end unified processing across multiple domains with only 754K parameters.
- **Key Claim**: Breaks the barrier of reflectance properties through a dual-mask physical model and multi-directional EPI architecture, achieving lightweight and efficient unified light field depth estimation for mixed scenes.

## Candidate 2: Physical Limits of Angular Frequency Material Classification
- **Problem**: The academic community widely assumes that materials can be distinguished via angular frequency features (e.g., 2D-FFT), leading to blind exploration of frequency-domain material classification under mainstream low angular resolutions (e.g., 9x9).
- **Significance**: If this assumption is invalid under current hardware conditions, it will result in a massive waste of research resources and severely misguide the design of light field sensors and the evolution of underlying algorithms.
- **Approach**: Proposes an MRI-like angular frequency analysis hypothesis, rigorously validates it using four independent frequency-domain analysis methods and sampling theorems, falsifies its feasibility at 9x9 resolution, and defines the physical baseline requiring at least 17x17 sampling.
- **Key Claim**: Strictly falsifies the feasibility of frequency-domain material classification at low angular resolutions, defining the hardware physical baseline to provide a theoretical compass that prevents blind exploration in future research.

## Candidate 3: Long-Tail Domain Imbalance and Architectural Limit Diagnosis
- **Problem**: Extreme imbalance in scene quantities across different domains in light field datasets causes minority domains to be overwhelmed by dominant gradients during joint training, while current research lacks clear cognition of the performance ceiling of EPI architectures in complex textures.
- **Significance**: Long-tail data distribution restricts model generalization in scarce domains, and the ambiguity of architectural limits causes researchers to waste effort on ineffective architectural fine-tuning, hindering technological breakthroughs.
- **Approach**: Introduces domain-balanced sampling and resolution scaling strategies to optimize multi-domain joint training, while conducting root-cause analysis on the performance bottleneck of the Lambertian domain to explicitly define the theoretical limits of EPI methods and future evolutionary directions.
- **Key Claim**: Resolves the multi-domain long-tail training dilemma through domain-balanced strategies and precisely diagnoses the performance ceiling of EPI architectures, pointing out the direction for engineering optimization and architectural leaps in light field algorithms.

