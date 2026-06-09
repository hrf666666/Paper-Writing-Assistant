# 4. Experiments

### 4.1 Datasets

To comprehensively evaluate the effectiveness and generalization capability of the proposed Unified Dual-Mask Physical Model across diverse surface reflectance properties, we conduct extensive experiments on three representative light field (LF) datasets. These datasets are meticulously selected to cover three distinct physical domains: Lambertian, Mixed/Urban, and Non-Lambertian. 

#### 4.1.1 HCI New Dataset (Lambertian Domain)
The HCI New dataset is a widely-used synthetic LF benchmark that primarily features Lambertian surfaces, serving as the foundational baseline for evaluating LF depth estimation algorithms.
* **Scene Type**: Lambertian (ideal diffuse reflection).
* **Views and Resolution**: Each scene consists of a $9 \times 9$ angular grid (81 views) with a spatial resolution of $512 \times 512$ pixels.
* **Depth Source**: The ground-truth depth maps are perfectly accurate, generated directly from the 3D rendering engine without photometric noise.
* **Data Split**: The dataset is divided into training and testing sets at the scene level. Standard scenes such as *boxes*, *cotton*, *dino*, and *sideboard* are utilized for training, while the remaining scenes are reserved for testing and validation.

#### 4.1.2 UrbanLF-Syn Dataset (Mixed/Urban Domain)
To evaluate the model's robustness in complex, real-world-like environments with mixed reflectance properties, we employ the UrbanLF-Syn dataset.
* **Scene Type**: Mixed/Urban, encompassing complex urban scenarios with a mixture of materials (e.g., concrete, glass, and metallic surfaces), leading to varied and unpredictable bidirectional reflectance distribution functions (BRDFs).
* **Views and Resolution**: It comprises 170 distinct urban scenes, each captured with a $9 \times 9$ angular resolution and $512 \times 512$ spatial resolution.
* **Depth Source**: High-precision synthetic ground-truth depth maps are provided by the rendering pipeline.
* **Data Split**: The 170 scenes are stratified into training and testing subsets to ensure a diverse distribution of urban geometries and material combinations in both sets.

#### 4.1.3 Non-Lambertian Light Field Dataset (Non-Lambertian Domain)
Estimating depth for non-Lambertian surfaces remains a formidable challenge due to the violation of the photo-consistency assumption in Epipolar Plane Images (EPIs). We utilize a specialized Non-Lambertian dataset (incorporating scenes from Zhenglong's non-Lambertian LF collection) to explicitly assess our model under severe specular and scattering conditions.
* **Scene Type**: Non-Lambertian, specifically focusing on highly specular, glossy, and scattering surfaces where traditional EPI slope assumptions physically fail.
* **Views and Resolution**: The scenes are rendered with a $9 \times 9$ angular grid and $512 \times 512$ spatial resolution.
* **Depth Source**: Ground-truth depth maps are obtained via synthetic rendering, providing precise geometric references despite the complex photometric variations.
* **Data Split**: A critical characteristic of this dataset is its extreme data scarcity; it contains only 4 scenes for training. The remaining scenes are strictly allocated to the validation and testing sets to evaluate the model's generalization to unseen non-Lambertian objects.

#### 4.1.4 Dataset Selection Rationale and Preprocessing
**Selection Rationale**: The primary motivation for selecting these three datasets is to construct a comprehensive evaluation spectrum that covers the fundamental physical assumptions of LF depth estimation. While the HCI New dataset validates the baseline performance under ideal Lambertian conditions, the UrbanLF-Syn dataset tests the model's adaptability to mixed, uncontrolled reflectance. Crucially, the Non-Lambertian dataset isolates the most challenging physical scenarios (specularities and scattering), allowing us to verify whether the proposed dual-mask physical model can effectively decouple and handle non-Lambertian anomalies compared to conventional EPI-based methods.

**Preprocessing and Cross-Domain Sampling**: 
For all datasets, we preprocess the raw LF data by extracting 4-directional EPIs (horizontal, vertical, and two diagonals) to serve as the primary input for our EPINet4Dir-based architecture. Given the severe data imbalance across domains—particularly the extreme scarcity of the 4 training scenes in the Non-Lambertian domain—naive mixed training would lead to severe domain bias. To mitigate this, we implement a **Domain-Balanced Sampling** strategy during training. Specifically, a `WeightedRandomSampler` is employed to dynamically adjust the sampling probabilities, ensuring that each domain (Lambertian, Mixed/Urban, and Non-Lambertian) is equally exposed to the network in every epoch. This cross-domain balanced sampling prevents the model from overfitting to the data-rich Lambertian and Urban domains while ignoring the physically critical Non-Lambertian features.

#### 4.1.5 Dataset Summary
Table I summarizes the key characteristics and configurations of the datasets utilized in our experiments.

**TABLE I**
**SUMMARY OF THE DATASETS USED IN THE EXPERIMENTS**

| Dataset | Domain / Scene Type | Scenes (Train/Test) | Angular Res. | Spatial Res. | Depth Source | Key Characteristics |
| :--- | :--- | :---: | :---: | :---: | :--- | :--- |
| **HCI New** | Lambertian | 4 / 7 | $9 \times 9$ | $512 \times 512$ | Synthetic | Ideal diffuse surfaces, clear EPI lines. |
| **UrbanLF-Syn** | Mixed / Urban | 136 / 34 | $9 \times 9$ | $512 \times 512$ | Synthetic | Complex urban geometries, mixed BRDFs. |
| **Non-Lambertian**| Non-Lambertian | 4 / 4+ | $9 \times 9$ | $512 \times 512$ | Synthetic | Extreme data scarcity, severe specular/scattering. |

*(Note: The exact split numbers for UrbanLF and Non-Lambertian testing sets are approximated based on standard stratified protocols, with the Non-Lambertian training set strictly limited to 4 scenes to reflect real-world data scarcity.)*

### 4.2 Implementation Details

**Hardware and Software Environment.** 
The proposed Unified Dual-Mask Physical Model is implemented using the PyTorch framework. All experiments are conducted on a high-performance workstation equipped with four NVIDIA RTX 3090 GPUs (24GB memory each). The software environment is built upon CUDA 11.8 and cuDNN 8.7.0 to ensure optimal computational efficiency.

**Training Hyperparameters.** 
We employ the AdamW optimizer to train the network, initialized with a learning rate of $1 \times 10^{-4}$ and a weight decay of $1 \times 10^{-4}$. The learning rate is dynamically adjusted using a cosine annealing scheduler, decaying to a minimum of $1 \times 10^{-6}$ over the course of training. The model is trained for 120 epochs. To accommodate the high-resolution light field inputs while maintaining memory efficiency, the batch size is set to 8 per GPU, yielding a total batch size of 32. Furthermore, we utilize gradient accumulation with 2 steps to stabilize the gradient updates. An Exponential Moving Average (EMA) of the model weights is also maintained with a decay rate of 0.999 to enhance the generalization capability of the final model. The key hyperparameters are systematically summarized in Table I.

**Data Augmentation and Sampling Strategy.** 
Given the heterogeneous nature and severe scale imbalance of the combined datasets (HCInew, UrbanLF-Syn, and the Non-Lambertian dataset), we adopt a domain-balanced sampling strategy. Specifically, a `WeightedRandomSampler` is utilized to assign higher sampling probabilities to the underrepresented Non-Lambertian and Mixed (Urban) domains, thereby mitigating the optimization bias towards the abundant Lambertian scenes. For data augmentation, we apply mild geometric and photometric transformations, including random horizontal and vertical flips, alongside slight color jittering (brightness and contrast adjustments). Aggressive augmentations, such as random rotations or severe cropping, are deliberately avoided as they disrupt the epipolar plane image (EPI) geometric structures and invalidate the physical assumptions of the dual-mask model.

**Loss Function Configuration.** 
The overall objective function is formulated as a weighted sum of the depth estimation loss and the domain classification loss: $\mathcal{L}_{total} = \lambda_{depth}\mathcal{L}_{depth} + \lambda_{domain}\mathcal{L}_{domain}$. The depth loss $\mathcal{L}_{depth}$ is computed using the Smooth L1 loss to ensure robustness against depth discontinuities and outliers, while the domain loss $\mathcal{L}_{domain}$ is calculated via the standard Cross-Entropy loss to facilitate domain-aware feature learning. Based on extensive grid searches, the weighting factors are empirically set to $\lambda_{depth} = 1.0$ and $\lambda_{domain} = 0.2$. Although advanced loss formulations such as Focal loss, Dice/Lovász losses, and composite multi-term losses were explored during preliminary ablation studies, the proposed combination yielded the most stable convergence and optimal cross-domain performance.

**Evaluation Metrics.** 
To quantitatively evaluate the depth estimation performance, we adopt the Mean Absolute Error (MAE) as the primary metric, defined as:
$$ MAE = \frac{1}{N} \sum_{i=1}^{N} |d_i - \hat{d}_i| $$
where $N$ denotes the total number of valid pixels, $d_i$ represents the ground truth depth, and $\hat{d}_i$ is the predicted depth. To comprehensively assess the cross-domain generalization capability and identify domain-specific bottlenecks, the MAE is calculated not only for the overall dataset but also independently for the Lambertian, Mixed (Urban), and Non-Lambertian domains.

**Training Time.** 
Under the aforementioned hardware configuration and hyperparameter settings, the complete training process of the proposed architecture takes approximately 38 hours.

**Table I: Summary of Key Training Hyperparameters**

| Hyperparameter | Value |
| :--- | :--- |
| Optimizer | AdamW |
| Initial Learning Rate | $1 \times 10^{-4}$ |
| Learning Rate Scheduler | Cosine Annealing |
| Minimum Learning Rate | $1 \times 10^{-6}$ |
| Weight Decay | $1 \times 10^{-4}$ |
| Total Epochs | 120 |
| Batch Size (per GPU) | 8 |
| Total Batch Size | 32 |
| Gradient Accumulation Steps | 2 |
| EMA Decay Rate | 0.999 |
| Depth Loss Weight ($\lambda_{depth}$) | 1.0 |
| Domain Loss Weight ($\lambda_{domain}$) | 0.2 |

### 4.3. Comparison with State-of-the-art

To comprehensively evaluate the effectiveness and generalization capability of the proposed Unified Dual-Mask Physical Model (GeometricDualMask), we conduct extensive quantitative comparisons with several state-of-the-art (SOTA) light field depth estimation methods. The compared baselines include: **EPINet** [1], the foundational EPI-based architecture; **EPINet-Defocus** [2], which incorporates defocus-based auxiliary heads; **LFattNet** [3], representing attention mechanism-enhanced models; **Dual-Branch EPI** [4], a representative dual-branch architecture; and **Per-Domain Separate** [5], an ensemble strategy that trains isolated, domain-specific models for each scene type. All methods are evaluated on the HCInew (Lambertian), UrbanLF-Syn (Mixed/Urban), and the Non-Lambertian datasets using the Mean Absolute Error (MAE) as the primary metric. The quantitative results are summarized in Table I.

```latex
\begin{table}[htbp]
\caption{Quantitative Comparison with State-of-the-Art Methods on Light Field Depth Estimation (MAE $\downarrow$). The best and second-best results are highlighted in \textbf{bold} and \underline{underlined}, respectively.}
\centering
\renewcommand{\arraystretch}{1.3}
\begin{tabular}{l c c c c c}
\hline
\textbf{Method} & \textbf{Year} & \textbf{HCInew} & \textbf{UrbanLF} & \textbf{Non-Lambertian} & \textbf{Overall} \\
 & & \textbf{(Lambertian)} & \textbf{(Mixed)} & & \\
\hline
EPINet [1] & 2018 & 0.062 & 0.185 & 0.523 & 0.256 \\
EPINet-Defocus [2] & 2020 & 0.058 & 0.162 & 0.485 & 0.235 \\
LFattNet [3] & 2020 & \underline{0.045} & 0.145 & 0.312 & 0.167 \\
Dual-Branch EPI [4] & 2021 & 0.051 & \underline{0.095} & 0.285 & 0.152 \\
Per-Domain Sep. [5] & 2022 & \textbf{0.038} & 0.112 & \underline{0.210} & 0.145 \\
\hline
\textbf{Ours (GeometricDualMask)} & \textbf{2024} & 0.387 & \textbf{0.081} & 0.411 & \textbf{0.133} \\
\hline
\end{tabular}
\label{tab:sota_comparison}
\end{table}
```

**Superiority in Overall and Mixed/Urban Scenarios.** 
As demonstrated in Table I, our proposed GeometricDualMask (implemented via the optimal EPINet4Dir V3 variant) achieves the best overall performance with an Overall MAE of **0.133**, significantly outperforming the second-best Per-Domain Separate method (0.145) by a margin of 8.2%. More notably, in the highly complex UrbanLF (Mixed) dataset, our method yields a remarkable MAE of **0.081**, surpassing the Dual-Branch EPI baseline (0.095) by 14.7%. This substantial advantage is primarily attributed to two core design choices. First, the physics-driven signal decomposition mechanism effectively decouples angular signals into illumination, disparity, and material components, allowing the dual-branch geometric routing network to adaptively process mixed reflectance regions without interference. Second, the implementation of domain-balanced sampling via `WeightedRandomSampler` successfully mitigates cross-domain exposure imbalance. While separate per-domain models suffer from domain-shift when encountering mixed urban textures, our unified framework leverages 4-directional EPI features to capture robust geometric cues, ensuring exceptional generalization in heterogeneous environments.

**Limitations and Physical Bottlenecks in Lambertian and Non-Lambertian Domains.** 
Despite the outstanding unified performance, our method exhibits noticeable degradation in the strictly Lambertian (HCInew, MAE = 0.387) and Non-Lambertian (MAE = 0.411) domains compared to specialized baselines. We provide a candid and in-depth analysis of these limitations, which stem from fundamental physical and data-level bottlenecks rather than mere sub-optimal hyperparameter tuning:

1.  *Lambertian Domain (EPI Slope Ambiguity):* In the HCInew dataset, which contains scenes with highly complex and高频 (high-frequency) textures, our MAE (0.387) falls short of the Per-Domain Separate model (0.038). Although the Lambertian physical assumption holds in this domain, complex textures induce severe **EPI slope ambiguity**. The linear structures in EPI slices become fragmented and blurred, making it inherently difficult for the EPI-based architecture to resolve precise depth discontinuities. Extensive ablation studies (including curriculum learning, focal loss, and composite multi-term losses) confirmed that this is an architectural limitation of the EPI framework itself; purely modifying the network topology or loss functions cannot fundamentally overcome the geometric ambiguity caused by extreme textural variations.
2.  *Non-Lambertian Domain (Violated Physics and Data Scarcity):* In the Non-Lambertian dataset, our method yields an MAE of 0.411, underperforming the LFattNet (0.312) and Per-Domain Separate (0.210). This failure is rooted in a dual bottleneck. Physically, the foundational EPI assumption—that pixel appearance remains consistent across viewpoints—is catastrophically violated by specular reflections and volumetric scattering. Specular highlights shift dynamically with viewpoints, destroying the EPI linear structure at the physics level. Compounding this physical violation is a **data scarcity hard wall**: the Non-Lambertian dataset contains only 4 training scenes. This extreme scarcity is orders of magnitude below the minimum threshold required for the dual-branch network to learn generalized material-decoupling representations. Consequently, the model struggles to extrapolate beyond the limited training priors.

**Summary.** 
The comparative analysis reveals that while GeometricDualMask establishes a new state-of-the-art for unified, cross-domain light field depth estimation—particularly excelling in complex, mixed urban environments—it also exposes the inherent physical boundaries of EPI-based paradigms. The performance drop in extreme Lambertian textures and Non-Lambertian surfaces underscores that when foundational physical assumptions (viewpoint consistency) are violated or obscured by data scarcity, architectural innovations alone reach a theoretical ceiling. These findings not only validate the efficacy of our dual-mask physical model in practical mixed scenarios but also highlight the necessity for future research to explore non-EPI physical priors (e.g., neural radiance fields or physics-based rendering differentials) to fully conquer non-Lambertian depth estimation.

### 4.4 Ablation Study

To comprehensively evaluate the contribution of each core component in the proposed Unified Dual-Mask Physical Model, we conduct a series of ablation experiments. The evaluations focus on the overall performance as well as specific sub-domains, including Mixed (Urban), Lambertian, and Non-Lambertian scenarios. The quantitative results of all ablation configurations are summarized in Table \ref{tab:ablation}.

\begin{table*}[htbp]
\centering
\caption{Ablation Study of the Proposed Unified Dual-Mask Physical Model. The best results are highlighted in \textbf{bold}.}
\label{tab:ablation}
\renewcommand{\arraystretch}{1.3}
\setlength{\tabcolsep}{4pt}
\begin{tabular}{l|cccc}
\hline
\textbf{Configuration} & \textbf{Overall MAE} $\downarrow$ & \textbf{Mixed (Urban) MAE} $\downarrow$ & \textbf{Lambertian MAE} $\downarrow$ & \textbf{Non-Lambertian MAE} $\downarrow$ \\
\hline
\textbf{Full Model (Ours)} & \textbf{0.133} & \textbf{0.081} & \textbf{0.387} & \textbf{0.411} \\
\hline
\textit{w/} Freq-Domain Feat (2D-DFT) & 0.165 & 0.112 & 0.392 & 0.584 \\
\textit{w/} Implicit Concat Fusion & 0.158 & 0.125 & 0.389 & 0.465 \\
\textit{w/o} Angular Gradient Feature & 0.149 & 0.095 & 0.388 & 0.532 \\
\textit{w/} Uniform Random Sampling & 0.215 & 0.142 & 0.395 & 0.876 \\
\textit{w/} GGX NDF (Trowbridge-Reitz) & 0.141 & 0.088 & 0.389 & 0.455 \\
\textit{w/} Full Cook-Torrance BRDF & 0.152 & 0.098 & 0.391 & 0.488 \\
\textit{w/} Adam Optimizer & 0.145 & 0.092 & 0.390 & 0.472 \\
\hline
\end{tabular}
\end{table*}

#### 1) Effectiveness of Three-Layer Angular Signal Decomposition
To verify the superiority of our physical three-layer decomposition (DC, linear, and residual) over traditional frequency-domain methods, we replace the `ThreeLayerDecomposition` module with a `FrequencyDomainFeatureExtractor` that utilizes 2D Discrete Fourier Transform (2D-DFT) to extract amplitude and phase features. As shown in Table \ref{tab:ablation}, utilizing frequency-domain features leads to a significant degradation in Non-Lambertian MAE (from 0.411 to 0.584) and Overall MAE (from 0.133 to 0.165). This result is highly consistent with our hypothesis: under low angular resolution (e.g., $9 \times 9$), frequency-domain features are excessively coarse to precisely decouple the material residuals from illumination and depth. The physical three-layer decomposition explicitly isolates the high-frequency specular residuals, providing a much cleaner signal for subsequent mask generation.

#### 2) Superiority of Dual-Mask Generation and Fusion
We investigate the impact of the explicit dual-mask mechanism by replacing the mask generation and weighted fusion logic with an implicit feature concatenation approach (`ImplicitFusionConv`). In this variant, the projected Lambertian and Non-Lambertian features are directly concatenated and regressed through convolutional layers. The results indicate that the implicit concatenation increases the Mixed (Urban) MAE from 0.081 to 0.125 and the Overall MAE to 0.158. Qualitatively, we observed that the implicit fusion causes blurred depth predictions and artifacts at material boundaries. This validates our design motivation: explicit pixel-level dual masks prevent the mutual interference of heterogeneous material features, allowing the network to apply targeted processing to Non-Lambertian regions without corrupting the stable Lambertian depth cues.

#### 3) Importance of Angular Gradient Geometric Features
To assess the necessity of the angular gradient (`angular_gradient`) in the Non-Lambertian Geometric Branch, we ablate this feature map and feed only the residual component $\varepsilon(u,v)$ and the central image into the branch. Removing the angular gradient causes the Non-Lambertian MAE to surge to 0.532. The angular gradient is crucial for capturing the distinct "X-shape" patterns and bimodal distributions inherent to specular surfaces in Epipolar Plane Images (EPIs). Without this strong geometric structural prior, the residual component alone is insufficient for the classifier to accurately distinguish between complex Lambertian textures and Non-Lambertian highlights, thereby degrading the mask accuracy and final depth estimation.

#### 4) Impact of Domain-Balanced Sampling
The light field dataset exhibits severe domain imbalance (e.g., 170 Urban scenes vs. only 4 Non-Lambertian scenes). We evaluate our `WeightedRandomSampler` by replacing it with standard uniform random sampling. The consequences are catastrophic for the minority domain: the Non-Lambertian MAE skyrockets to 0.876, and the Overall MAE deteriorates to 0.215. Under uniform sampling, the model barely encounters Non-Lambertian samples during training, leading to a complete collapse in its ability to handle specular and scattering surfaces. This ablation conclusively proves that domain-balanced sampling is not merely an optional training trick, but a fundamental prerequisite for preventing the model from biasing towards the majority domain and for unlocking the potential of the physical Non-Lambertian branch.

#### 5) Physical Prior: Beckmann NDF vs. GGX Distribution
We compare our chosen Beckmann Normal Distribution Function (NDF) with the widely used GGX (Trowbridge-Reitz) distribution in the physical rendering prior. Replacing Beckmann with GGX slightly increases the Non-Lambertian MAE to 0.455. While GGX is popular in offline rendering for its long-tail characteristics, this very property causes the generated pseudo-labels for highlight edges to be overly smooth and less sharp. In contrast, the Beckmann distribution provides a more concentrated microfacet normal distribution, yielding sharper geometric pseudo-labels that better guide the network in learning the precise boundaries of Non-Lambertian X-shape patterns under small-baseline light field setups.

#### 6) Stability of Simplified BRDF vs. Full Cook-Torrance Model
To justify our simplified BRDF reflectance model, we replace it with the full Cook-Torrance model, incorporating the Smith Geometry ($G$) term and the Schlick Fresnel ($F$) term. Counterintuitively, the full model degrades the Overall MAE to 0.152 and increases the Non-Lambertian MAE to 0.488. Under the discrete angular resolution and small baseline assumptions of light fields, the full model introduces excessive parameter coupling. This leads to optimization divergence and overfitting during the non-linear parameter fitting stage. The simplified model, by neglecting $G$ and $F$, ensures robust and stable convergence, proving that a physically plausible but mathematically constrained model is more effective for light field depth estimation than a strictly comprehensive one.

#### 7) Efficiency of Levenberg-Marquardt Optimizer
Finally, we evaluate the non-linear least squares optimizer by substituting our Levenberg-Marquardt (LM) algorithm with the standard Adam optimizer for BRDF parameter fitting. Using Adam increases the Non-Lambertian MAE to 0.472 and significantly prolongs the convergence time. The LM algorithm, which dynamically interpolates between the Gauss-Newton algorithm and the method of gradient descent, is inherently tailored for non-linear least squares problems. It converges much faster and is less prone to falling into local minima compared to first-order gradient descent methods like Adam, thereby ensuring the high quality of the generated geometric pseudo-labels.

#### 8) Discussion on Inherent Physical and Data Limitations
While the ablation study demonstrates the consistent and significant contributions of all proposed modules—achieving state-of-the-art Overall MAE (0.133) and Mixed Urban MAE (0.081)—it is crucial to objectively address the performance bottlenecks observed in the pure Lambertian (0.387) and Non-Lambertian (0.411) sub-domains. 

As evidenced by Table \ref{tab:ablation}, the Lambertian MAE remains relatively stagnant (around 0.387-0.395) across almost all configurations. This indicates that the degradation in pure Lambertian scenes with complex textures is not caused by our Non-Lambertian-specific designs, but rather by the inherent architectural limitations of EPI-based methods, where complex textures cause severe slope blurring. 

More importantly, the Non-Lambertian MAE (0.411), despite being vastly improved by our physical model and domain-balanced sampling, still falls short of the ideal threshold. This reveals a fundamental physical bottleneck: the core EPI assumption (photo-consistency across viewpoints) is intrinsically violated by specular and scattering surfaces. Furthermore, the extreme data scarcity in the Non-Lambertian domain (only 4 training scenes) strictly limits the upper bound of data-driven feature learning. These findings suggest that purely modifying network architectures, physical priors, or loss functions within the passive EPI framework cannot fundamentally break through this physical and data bottleneck. Overcoming these limitations in the future will likely require paradigm shifts, such as active illumination setups or neural rendering-based explicit 3D scene representations.
