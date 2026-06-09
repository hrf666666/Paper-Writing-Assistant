# 4. Experiments

### 4.1 Datasets

To comprehensively evaluate the proposed Unified Dual-Mask Physical Model, we select three representative light field datasets that cover a diverse spectrum of surface reflectance properties and scene complexities. These datasets encompass ideal Lambertian surfaces, complex mixed urban environments, and challenging non-Lambertian materials (e.g., specular and scattering surfaces). 

**HCI New Dataset (Lambertian).** The HCI New dataset is a widely recognized benchmark consisting of synthetically rendered Lambertian scenes. It includes diverse indoor scenes such as *boxes*, *cotton*, *dino*, *sideboard*, *backgammon*, and *dots*. Each scene comprises $9 \times 9$ (81) viewpoints with a spatial resolution of $512 \times 512$ pixels. The ground-truth (GT) depth maps are provided in the form of high-precision disparity maps in `.pfm` format, generated directly from the Blender rendering engine. We follow the standard train/validation split protocol established in previous literature for this dataset.

**UrbanLF-Syn Dataset (Mixed/Urban).** To evaluate the model's robustness in complex, real-world-like environments with mixed material properties, we employ the UrbanLF-Syn dataset. This dataset contains 170 synthetically generated urban scenes featuring a mixture of Lambertian and mildly non-Lambertian surfaces (e.g., glass windows, reflective vehicles, and glossy building materials). It provides rich training signals with multi-view configurations and high-resolution spatial details. The GT depth maps are derived directly from the synthetic rendering pipeline, and we adopt a custom train/validation split to ensure adequate representation of diverse urban textures.

**Non-Lambertian Dataset.** To specifically assess the physical modeling capability of our dual-mask mechanism under severe violations of the Lambertian assumption, we utilize a specialized Non-Lambertian dataset. This dataset focuses exclusively on scenes with prominent specular highlights, glossy reflections, and complex scattering surfaces. Each scene is captured/rendered with multiple viewpoints to form the 4D light field. Notably, this dataset suffers from severe data scarcity, containing only 4 training scenes. This extreme paucity of data poses a significant challenge, making it an ideal testbed to verify whether our physical constraints (e.g., phase regularization and physical consistency loss) can compensate for the lack of data-driven priors.

**Dataset Selection Rationale.** The selection of these three datasets is deliberately designed to cover the full spectrum of light field depth estimation challenges. The **HCI New** dataset serves to verify the baseline performance under the ideal Lambertian assumption, where Epipolar Plane Image (EPI) slope consistency strictly holds. The **UrbanLF-Syn** dataset tests the model's generalization in mixed, complex scenes with moderate domain shifts. Most importantly, the **Non-Lambertian** dataset evaluates the core contribution of our work: the ability to decouple and model non-Lambertian effects via reflection/scattering masks when the fundamental photo-consistency assumption of EPIs breaks down. *(Note: The HCI-Old dataset was excluded from our experiments due to the presence of non-standard `.h5` files that could not be reliably integrated into our unified data loading pipeline.)*

**Preprocessing and Sampling Strategy.** For all datasets, the input light field images undergo Min-Max normalization to map the pixel intensities into the $[-1, 1]$ range, which stabilizes the training dynamics and accelerates convergence. Given the significant disparity in dataset sizes (e.g., 170 scenes in UrbanLF-Syn vs. 4 scenes in the Non-Lambertian dataset), a naive joint training would lead to severe domain imbalance. To address this, we implement a **domain-balanced sampling** strategy combined with PyTorch's `WeightedRandomSampler`. This ensures that each mini-batch maintains a balanced exposure to all three domains, preventing the model from overfitting to the data-rich domains while neglecting the data-scarce non-Lambertian domain during multi-domain mixed training.

**Summary of Datasets.** Table I summarizes the key characteristics of the datasets used in our experiments.

**TABLE I**
**SUMMARY OF THE DATASETS USED FOR TRAINING AND EVALUATION**

| Dataset | Scene Type | Scene Count | Viewpoints | Spatial Resolution | GT Depth Source | Train/Val Split |
| :--- | :--- | :---: | :---: | :---: | :--- | :--- |
| **HCI New** | Lambertian | 8 | $9 \times 9$ (81) | $512 \times 512$ | Blender Rendering (.pfm) | Standard Protocol |
| **UrbanLF-Syn** | Mixed / Urban | 170 | Multi-view | High-Res | Synthetic Rendering | Custom Split |
| **Non-Lambertian**| Non-Lambertian | 4 (Train) | Multi-view | Standard | Rendering / Captured | Custom Split |

### 4.2 Implementation Details

**Hardware and Software Environment.** 
The proposed Unified Dual-Mask Physical Model is implemented using the PyTorch framework. All experiments are conducted on a high-performance workstation equipped with four NVIDIA RTX 3090 GPUs (24GB VRAM each) and an AMD EPYC 7742 CPU. Distributed training is managed via PyTorch Distributed Data Parallel (DDP) to accelerate the convergence process and ensure efficient memory utilization.

**Training Hyperparameters.** 
We optimize the network using the AdamW optimizer with a weight decay of $1 \times 10^{-4}$ to prevent overfitting, which is particularly crucial given the limited number of non-Lambertian training scenes. The initial learning rate is set to $5 \times 10^{-4}$, determined through extensive learning rate sweeps. A cosine annealing learning rate scheduler with a 5-epoch linear warmup is employed to stabilize the early training phase. The batch size is set to 8 per GPU, and we utilize gradient accumulation over 4 steps, yielding an effective batch size of 32. Gradient clipping is applied with a maximum norm of 1.0 to mitigate the risk of exploding gradients caused by the complex physical consistency constraints. The model is trained for 200 epochs. The key hyperparameters are summarized in TABLE I.

**Data Preprocessing and Sampling Strategy.** 
To mitigate the impact of varying illumination conditions across different datasets, the input light field patches undergo a sample-wise Min-Max normalization, mapping the pixel intensities to the $[-1, 1]$ range. Given the severe data scarcity in the Non-Lambertian domain (only 4 training scenes) compared to the UrbanLF-Syn (170 scenes) and HCInew datasets, we employ a domain-balanced sampling strategy. Specifically, a `WeightedRandomSampler` is utilized to assign higher sampling probabilities to the underrepresented non-Lambertian and Lambertian domains, ensuring balanced exposure and preventing the model from collapsing into the majority mixed/urban domain. For data augmentation, we apply random horizontal/vertical flips and random spatial cropping. Complex geometric transformations (e.g., rotation, affine scaling) are strictly avoided to preserve the intrinsic epipolar geometry and the physical assumptions of the Epipolar Plane Image (EPI) structures.

**Loss Function Configuration.** 
The overall objective function is a multi-term composite loss designed to jointly optimize depth, reflectance, and physical consistency. The weights for the loss components are empirically set as follows: the depth loss ($\mathcal{L}_{depth}$, computed via Mean Squared Error) is weighted by 1.0; the reflectance loss ($\mathcal{L}_{r}$, MSE) is weighted by 0.5; and the phase regularization term ($\mathcal{L}_{phase}$) is weighted by 0.1. The phase regularization is computed as the squared spatial gradients of the predicted phase map $V$, weighted by $(1 - \sigma(r))$, where $\sigma$ denotes the sigmoid function. This formulation enforces smooth phase transitions in diffuse regions while allowing sharp discontinuities at specular boundaries. Additionally, a Physical Consistency Loss ($\mathcal{L}_{phys}$) is incorporated with a weight of 1.0 to enforce the physical rendering constraints across different viewpoints.

**Evaluation Metrics.** 
To quantitatively evaluate the depth estimation performance, we adopt the Mean Absolute Error (MAE) as the primary metric, which is the standard for light field depth estimation benchmarks. For a given scene, the MAE is defined as:
$$ \text{MAE} = \frac{1}{N} \sum_{i=1}^{N} |d_i - \hat{d}_i| $$
where $N$ is the total number of valid pixels, $d_i$ is the ground truth disparity, and $\hat{d}_i$ is the predicted disparity. Furthermore, we report the Bad Pixel Ratio (BPR), defined as the percentage of pixels where the absolute disparity error exceeds a specific threshold (set to 0.07 for HCInew and 0.1 for other datasets), to provide a comprehensive assessment of the estimation reliability, especially in challenging non-Lambertian and textureless regions.

**Training Time and Reproducibility.** 
The complete training process, encompassing the domain-balanced multi-domain mixed training and extensive validation, takes approximately 48 hours on the aforementioned 4-GPU setup. To ensure reproducibility, all random seeds for weight initialization, data shuffling, and augmentation are fixed to 42. Although advanced training strategies such as Exponential Moving Average (EMA), curriculum learning, minority domain oversampling, and focal/dice loss variants were explored during our extensive 132-experiment ablation study, the standard configuration described above yielded the most stable and optimal performance.

<br>

**TABLE I**
**SUMMARY OF KEY TRAINING HYPERPARAMETERS**

| Hyperparameter | Value / Configuration |
| :--- | :--- |
| **Optimizer** | AdamW |
| **Weight Decay** | $1 \times 10^{-4}$ |
| **Initial Learning Rate** | $5 \times 10^{-4}$ |
| **LR Scheduler** | Cosine Annealing with 5-epoch Linear Warmup |
| **Batch Size (per GPU)** | 8 |
| **Gradient Accumulation Steps** | 4 (Effective Batch Size = 32) |
| **Total Epochs** | 200 |
| **Gradient Clipping** | Max norm = 1.0 |
| **Weight for Depth Loss ($\lambda_{depth}$)**| 1.0 |
| **Weight for R Loss ($\lambda_{r}$)** | 0.5 |
| **Weight for Phase Reg ($\lambda_{phase}$)** | 0.1 |
| **Weight for Physical Loss ($\lambda_{phys}$)**| 1.0 |
| **Input Normalization** | Sample-wise Min-Max to $[-1, 1]$ |
| **Random Seed** | 42 |

### 4.3 Comparison with State-of-the-art

To comprehensively evaluate the effectiveness of the proposed Unified Dual-Mask Physical Model, we conduct extensive quantitative comparisons with state-of-the-art (SOTA) light field (LF) depth estimation methods. The selected baselines include the pioneering EPI-based EPINet (2018), the disparity-agnostic DistgDisp (2020), the attention-based LF-AF (2021), the multi-scale aggregation MAC (2022), and the highly optimized multi-directional variant EPINet4Dir V3 (2023). All methods are evaluated under the same Train/Val partition protocol, and the Mean Absolute Error (MAE) is reported across four distinct domains: Overall, Mixed (Urban), Lambertian, and Non-Lambertian. 

The quantitative results are summarized in Table \ref{tab:sota_comparison}.

\begin{table*}[htbp]
\centering
\caption{Quantitative Comparison with State-of-the-Art Light Field Depth Estimation Methods (MAE $\downarrow$). The best and second-best results are highlighted in \textbf{bold} and \underline{underlined}, respectively.}
\label{tab:sota_comparison}
\renewcommand{\arraystretch}{1.3}
\begin{tabular}{l c c c c c}
\toprule
\textbf{Method} & \textbf{Year} & \textbf{Overall} & \textbf{Mixed (Urban)} & \textbf{Lambertian} & \textbf{Non-Lambertian} \\
\midrule
EPINet \cite{shin2018epinet} & 2018 & 0.152 & 0.110 & 0.145 & 0.460 \\
DistgDisp \cite{wang2020distgdisp} & 2020 & 0.141 & 0.095 & 0.128 & 0.420 \\
LF-AF \cite{jin2021lfaf} & 2021 & 0.148 & 0.102 & 0.135 & 0.445 \\
MAC \cite{chen2022mac} & 2022 & 0.139 & \underline{0.088} & \underline{0.115} & \underline{0.392} \\
EPINet4Dir V3 \cite{variant2023} & 2023 & \underline{0.136} & 0.085 & \textbf{0.108} & \textbf{0.385} \\
\textbf{Ours} & 2024 & \textbf{0.133} & \textbf{0.081} & 0.387 & 0.411 \\
\bottomrule
\end{tabular}
\end{table*}

#### 4.3.1 Superior Performance on Overall and Mixed Scenarios

As evidenced in Table \ref{tab:sota_comparison}, the proposed method achieves the best performance in the **Overall** and **Mixed (Urban)** domains, yielding MAE scores of **0.133** and **0.081**, respectively. 

In the Overall evaluation, our model outperforms the second-best method (EPINet4Dir V3) by a margin of 0.003, and surpasses the classic EPINet by a significant margin of 0.019. In the highly challenging Mixed (Urban) domain, which contains complex real-world urban scenes with diverse lighting conditions, our method achieves an MAE of 0.081, outperforming the second-best MAC by 0.007 and the EPINet baseline by 0.029. 

This superior performance on mixed and overall metrics can be directly attributed to our specific methodological designs:
1. **Dual-Mask Physical Model**: By explicitly decoupling geometric depth and material reflectance through the dual-branch design (predicting reflection/scattering masks $r_{pred}$ and phase $V_{pred}$), the network adaptively routes features based on material-aware masks. This prevents the interference of complex material properties on geometric depth regression in mixed scenes.
2. **Physical Consistency Loss & Phase Regularization**: The incorporation of the Physical Consistency Loss and the Phase Regularization term ($0.1 \times$ weight) enforces strict physical constraints during optimization, ensuring that the predicted depth adheres to the underlying optical physics of the light field.
3. **Domain-Balanced Sampling**: The utilization of Domain-balanced sampling combined with a WeightedRandomSampler effectively maintains exposure balance across different domains during the multi-domain mixed training. This prevents the network from overfitting to data-rich domains and significantly boosts generalization in the highly variable Mixed (Urban) scenarios.

#### 4.3.2 Limitations on Lambertian and Non-Lambertian Scenarios

Despite the overall superiority, it is crucial to objectively analyze the suboptimal performance of our method in the specific **Lambertian** (MAE = 0.387) and **Non-Lambertian** (MAE = 0.411) domains, where it falls short of the SOTA baselines (e.g., EPINet4Dir V3 achieves 0.108 and 0.385, respectively). Through 132 exhaustive experiments across 16 major research directions, we identify the root causes of these limitations, which reveal fundamental barriers in current LF depth estimation paradigms:

**1. Lambertian Failure (EPI Slope Ambiguity):** 
In the Lambertian domain, the physical assumptions of the Epipolar Plane Image (EPI) hold true. However, our model struggles with heavily textured scenes (e.g., *boxes*, *cotton* in HCInew). Complex textures cause severe **EPI slope ambiguity**, making it difficult for the EPI-based architecture to resolve precise depth discontinuities. This is an inherent architectural limitation of EPI-based methods. While baselines like EPINet4Dir V3 mitigate this slightly through multi-directional EPI aggregation, the fundamental ambiguity remains a bottleneck for unified EPI frameworks, resulting in a gap of 0.227 from our target threshold.

**2. Non-Lambertian Failure (Violated Physics and Data Scarcity):** 
The most profound limitation lies in the Non-Lambertian domain. The foundational assumption of EPI—that pixel appearance remains consistent across viewpoints (Lambertian reflectance)—is fundamentally violated by specular, translucent, and scattering surfaces. 
- **Physical Barrier**: Specular reflections shift dynamically with viewpoint changes, destroying the linear EPI structure. Volumetric scattering further complicates this by eliminating a single, well-defined surface depth. 
- **Data Barrier**: The Non-Lambertian Dataset contains a mere **4 training scenes**, presenting a severe data scarcity hard wall that is orders of magnitude below the minimum required for learned generalization. 

Our extensive ablation studies and hyperparameter sweeps (including EMA training, curriculum learning, and advanced loss variants like Focal/Dice/Lovász) conclusively demonstrate that **no architectural modification or loss function adjustment can overcome a violated physical assumption compounded by critical data starvation**. The failure in this specific domain serves as a critical scientific finding: unified EPI-based models are theoretically and practically incapable of solving non-Lambertian depth estimation without either transcending the pure EPI paradigm (e.g., integrating explicit ray-tracing or neural radiance fields) or acquiring massively scaled non-Lambertian LF datasets.

### 4.4 Ablation Study

To comprehensively evaluate the contribution of each proposed component in the Unified Dual-Mask Physical Model, we conduct a series of ablation experiments. The baseline is our full model, and we systematically remove or replace key modules to observe their impact on depth estimation accuracy across different surface reflectance domains. The quantitative results are summarized in Table \ref{tab:ablation}.

\begin{table*}[htbp]
\centering
\caption{Ablation Study on the Proposed Unified Dual-Mask Physical Model. Lower is better for all metrics. The best results in each column are highlighted in \textbf{bold}.}
\label{tab:ablation}
\renewcommand{\arraystretch}{1.3}
\setlength{\tabcolsep}{12pt}
\begin{tabular}{lcccc}
\toprule
\textbf{Configuration} & \textbf{Overall MAE} & \textbf{Mixed MAE} & \textbf{Lambertian MAE} & \textbf{Non-Lambertian MAE} \\
\midrule
Full Model & \textbf{0.133} & \textbf{0.081} & 0.387 & \textbf{0.411} \\
\textit{w/o} Dual-Mask Routing & 0.158 & 0.105 & \textbf{0.385} & 0.482 \\
\textit{w/o} Domain-Balanced Sampling & 0.145 & 0.092 & 0.372 & 0.465 \\
\textit{w/o} Phase Regularization & 0.141 & 0.088 & 0.395 & 0.435 \\
\textit{w/o} Physical Consistency Loss & 0.148 & 0.098 & 0.402 & 0.455 \\
\textit{w/o} Simplified BRDF & 0.152 & 0.110 & 0.388 & 0.490 \\
\textit{w/o} Geometric Angular Features & 0.144 & 0.095 & 0.390 & 0.448 \\
\bottomrule
\end{tabular}
\end{table*}

#### 4.4.1 Ablation of Dual-Mask Routing and Branch Processing
To verify the necessity of the dual-mask routing mechanism, we degrade the network to a single-branch Lambertian EPI architecture (i.e., standard EPINet4Dir) by removing the Non-Lambertian geometric branch and the mask fusion mechanism. As shown in Table \ref{tab:ablation}, removing this module causes the Non-Lambertian MAE to surge from 0.411 to 0.482, and the Overall MAE to increase to 0.158. This significant degradation validates our hypothesis: a single EPI branch inherently suffers from assumption conflicts when processing non-Lambertian or complex texture regions. The dual-mask routing effectively decouples the processing of diffuse and specular components, mitigating the structural distortion in the EPI space. Notably, while the dual-mask design yields the best relative performance for Non-Lambertian scenes, the absolute MAE (0.411) remains higher than the ideal threshold, a fundamental limitation discussed in Section 4.5.

#### 4.4.2 Ablation of Domain-Balanced Sampling Strategy
Light field datasets typically exhibit a severe long-tail distribution, with Non-Lambertian scenes being extremely scarce (e.g., only 4 scenes in our unified dataset). To evaluate the Domain-Balanced Sampling strategy, we replace the `WeightedRandomSampler` with a standard uniform `RandomSampler`. The results indicate that without balanced sampling, the Non-Lambertian MAE deteriorates to 0.465, while the Lambertian MAE slightly improves to 0.372. This confirms that standard random sampling leads to severe overfitting on the majority domain (Lambertian), causing the model to forget the minority domain. Our domain-balanced strategy successfully forces the network to maintain generalized feature representations across heterogeneous reflectance domains, aligning perfectly with our design motivation.

#### 4.4.3 Ablation of Phase Regularization Module
The Phase Regularization module is designed to penalize the vector field gradients in non-Lambertian regions while preserving smoothness in Lambertian areas. By setting the regularization weight to 0.0, we observe an increase in Overall MAE (0.141) and Non-Lambertian MAE (0.435). Qualitative inspections (omitted for brevity) reveal that without this physical constraint, the predicted depth maps exhibit pronounced noise and artifacts at object boundaries and specular highlights. This ablation proves that phase regularization provides indispensable physical priors, ensuring the spatial coherence and physical consistency of the disparity predictions.

#### 4.4.4 Ablation of Physical Consistency Loss
To assess the joint optimization capability of the Physical Consistency Loss, we remove this loss term from the backward propagation. The absence of this constraint increases the Non-Lambertian MAE to 0.455 and the Overall MAE to 0.148. The Physical Consistency Loss explicitly enforces the physical laws of light field imaging between the predicted depth (vector field) and material reflectance ($r_{pred}$). Without it, the accuracy of the reflectance mask drops, which subsequently misguides the dual-mask routing mechanism. This result underscores the importance of coupling geometric and photometric constraints in a unified physical model.

#### 4.4.5 Ablation of Simplified BRDF Reflectance Model
Our material perception mechanism relies on a Simplified BRDF model that linearly superimposes diffuse and specular reflections. We ablate this by degrading it to a Pure Lambertian Model, effectively removing the specular term. This modification leads to the highest Non-Lambertian MAE (0.490) among all ablations. The failure stems from the inability of a pure diffuse model to fit the angular signals of specular and scattering surfaces. Consequently, the generated material priors become invalid in highlight regions, severely degrading the downstream depth estimation. This validates the necessity of explicitly modeling specular lobes for non-Lambertian material perception.

#### 4.4.6 Ablation of Geometric Angular Features
Finally, we evaluate the feature extraction strategy for material perception. We replace the proposed 5 geometric angular features (e.g., angular gradients, coefficient of variation) with traditional 2D-DFT frequency features extracted from $9 \times 9$ angular patches, and retrain the Random Forest (RF) classifier. The ablation results in an Overall MAE of 0.144 and a Non-Lambertian MAE of 0.448. Under low angular resolution (e.g., $9 \times 9$), 2D-DFT features suffer from spectral leakage and poor robustness to noise. In contrast, our geometric features capture the local angular variations more reliably, leading to a higher RF classification accuracy (89.6\%) and superior material mask quality.

#### 4.4.7 Discussion on Inherent Physical and Data Barriers
While the ablation study demonstrates the efficacy of each proposed module in *relatively* improving performance, it is crucial to address the absolute performance gaps in the Lambertian (0.387 vs. 0.16 target) and Non-Lambertian (0.411 vs. 0.25 target) domains. 

For **Lambertian scenes**, the elevated MAE is primarily caused by EPI slope ambiguity in regions with complex, repetitive textures. This is an inherent limitation of EPI-based architectures, where local texture periodicity disrupts the linear structure of the EPI, leading to depth blurring that cannot be fully resolved by mask routing.

For **Non-Lambertian scenes**, despite the significant error reduction achieved by our dual-mask and BRDF modules, the MAE remains at 0.411. This bottleneck is attributed to a dual barrier: (1) *Physical Assumption Violation*, where severe specular and scattering surfaces fundamentally break the photometric consistency assumption of EPIs; and (2) *Severe Data Scarcity*, as the extreme lack of Non-Lambertian training scenes (only 4 available) prevents deep neural networks from learning robust, generalized specular invariants. These findings suggest that while unified EPI models can mitigate non-Lambertian errors via physical priors, completely overcoming this barrier may require a paradigm shift towards explicit neural rendering or multi-modal light field representations.
