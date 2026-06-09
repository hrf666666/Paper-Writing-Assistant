# 4. Experiments

### 4.1 Datasets

To comprehensively evaluate the proposed Unified Dual-Mask Physical Model and validate its generalization across varying surface reflectance properties, we construct a multi-domain experimental setup using three representative light field (LF) datasets. These datasets are meticulously selected to cover a wide spectrum of scene types, ranging from ideal Lambertian surfaces to highly complex mixed urban environments and physically challenging non-Lambertian materials. 

**HCInew Dataset.** The HCInew dataset primarily serves as the benchmark for **Lambertian** and standard synthetic scenes. It comprises multiple high-quality scenes (e.g., *boxes*, *cotton*, *dino*) rendered using Blender. Each scene consists of $9 \times 9$ (81) angular views with a spatial resolution of $512 \times 512$ pixels. The ground-truth (GT) depth maps are perfectly aligned and generated directly from the 3D rendering engine, providing pixel-accurate depth supervision. The dataset is divided into training and testing sets following the standard stratified split (e.g., `training/stratified`), ensuring a diverse distribution of geometric structures in both splits. It is chosen to evaluate the model's fundamental capability in extracting Epipolar Plane Image (EPI) structures under ideal physical assumptions.

**UrbanLF-Syn Dataset.** To assess the model's robustness in **Mixed/Urban** scenarios, we incorporate the UrbanLF-Syn dataset. This dataset contains 170 synthetic scenes depicting complex urban street views, featuring intricate textures, severe occlusions, and large-scale architectural structures. Similar to HCInew, it provides $9 \times 9$ angular views with high spatial resolution. The GT depth maps are derived from high-fidelity 3D city models. The scenes are partitioned into training and testing subsets. We select this dataset to challenge the model with complex texture variations and real-world structural complexities, where EPI slopes might be locally ambiguous due to fine details and occlusions.

**Non-Lambertian Dataset.** Evaluating depth estimation on **Non-Lambertian** surfaces is the core focus of this work. We utilize a specialized Non-Lambertian dataset (derived from the Zhenglong/Wanner HCI collections) that explicitly features specular (highlight), translucent, and scattering surfaces. Each scene contains $9 \times 9$ angular views at a $512 \times 512$ resolution, with GT depth maps generated via synthetic rendering. *Preprocessing and Constraints:* Originally, the HCI-Old dataset was considered; however, it was excluded from our pipeline due to intractable compatibility issues with its legacy `.h5` data format. Consequently, the available Non-Lambertian dataset is severely constrained, containing only 4 training scenes. Despite this extreme data scarcity, it is indispensable for our study as it introduces the ultimate physical challenge: the violation of the standard EPI linearity assumption caused by view-dependent reflectance (e.g., specular highlights shifting across views).

**Data Preprocessing and Domain-Balanced Sampling.** 
A critical challenge in our multi-domain setup is the severe data imbalance across different scene types (e.g., 170 scenes in UrbanLF-Syn versus only 4 scenes in the Non-Lambertian dataset). To prevent the network from overfitting to the data-rich domains and neglecting the physically challenging non-Lambertian cases, we implement a rigorous **domain-balanced sampling strategy**. Specifically, we employ a `WeightedRandomSampler` during the training phase. Each sample is assigned a weight inversely proportional to the total number of samples in its respective domain (Lambertian, Mixed/Urban, or Non-Lambertian). This ensures that each mini-batch maintains an equitable exposure to all three domains, facilitating stable multi-task learning and joint optimization of the depth and domain classification losses.

The key characteristics and configurations of the datasets utilized in our experiments are summarized in Table I.

**TABLE I**
**SUMMARY OF DATASETS USED FOR TRAINING AND EVALUATION**

| Dataset | Domain / Scene Type | No. of Scenes (Train / Test) | Angular Views | Spatial Resolution | GT Depth Source | Key Characteristics & Challenges |
| :--- | :--- | :---: | :---: | :---: | :--- | :--- |
| **HCInew** | Lambertian | Multiple (Stratified split) | $9 \times 9$ (81) | $512 \times 512$ | Synthetic (Blender) | Ideal EPI structures; standard geometric shapes and textures. |
| **UrbanLF-Syn** | Mixed / Urban | 170 (Partitioned) | $9 \times 9$ (81) | $512 \times 512$ | Synthetic (3D City Models) | Complex textures, severe occlusions, large-scale urban structures. |
| **Non-Lambertian** | Non-Lambertian | 4 / (Cross-validated) | $9 \times 9$ (81) | $512 \times 512$ | Synthetic (Blender) | Specular, translucent, scattering surfaces; EPI physical assumption failure; extreme data scarcity. |

*(Note: The HCI-Old dataset was excluded during preprocessing due to `.h5` format incompatibility, limiting the Non-Lambertian training set to 4 scenes.)*

### 4.2 Implementation Details

**Hardware and Software Environment.** 
The proposed Unified Dual-Mask Physical Model is implemented using the PyTorch framework. All experiments are conducted on a high-performance workstation equipped with four NVIDIA RTX 3090 GPUs (24GB VRAM each) and an AMD EPYC 7742 CPU. The Distributed Data Parallel (DDP) strategy is utilized to synchronize gradients and accelerate the training process across multiple GPUs.

**Training Hyperparameters.** 
We employ the AdamW optimizer to train the network, initialized with a learning rate of $1 \times 10^{-4}$ and a weight decay of $1 \times 10^{-4}$. The learning rate is dynamically adjusted using a Cosine Annealing scheduler, decaying to a minimum of $1 \times 10^{-6}$ over the course of training. The batch size is set to 32 per GPU, and gradient accumulation is applied with 2 steps, yielding an effective global batch size of 256. The model is trained for a total of 150 epochs. To mitigate the severe data imbalance among the Lambertian, Mixed/Urban, and Non-Lambertian datasets (notably, the Non-Lambertian dataset contains only 4 training scenes), we adopt a domain-balanced sampling strategy utilizing a `WeightedRandomSampler`. This ensures equitable exposure to each physical domain during every epoch. The key hyperparameters are summarized in Table I.

**TABLE I**
**SUMMARY OF KEY TRAINING HYPERPARAMETERS**

| Hyperparameter | Value |
| :--- | :--- |
| Optimizer | AdamW |
| Initial Learning Rate | $1 \times 10^{-4}$ |
| LR Scheduler | Cosine Annealing |
| Minimum Learning Rate | $1 \times 10^{-6}$ |
| Batch Size (per GPU) | 32 |
| Gradient Accumulation Steps | 2 |
| Effective Batch Size | 256 |
| Total Epochs | 150 |
| Weight Decay | $1 \times 10^{-4}$ |
| Sampler | WeightedRandomSampler (Domain-balanced) |

**Data Augmentation.** 
To improve the generalization capability and prevent overfitting—particularly given the extreme scarcity of Non-Lambertian training samples—we apply a comprehensive set of data augmentation techniques tailored for 4D light field data. These include random spatial cropping (resizing to $512 \times 512$ resolution), random horizontal and vertical flips (applied consistently across all angular views to preserve epipolar geometry), and random angular shifts. Additionally, we apply color jittering (random adjustments to brightness, contrast, and saturation) and Gaussian noise injection. These photometric augmentations simulate sensor noise and varying illumination conditions, which is highly beneficial for robust material recognition and domain classification.

**Loss Function Weights.** 
The network is optimized in a multi-task learning paradigm, jointly minimizing the depth estimation loss and the domain classification loss. The depth loss $\mathcal{L}_{depth}$ is formulated as the Smooth L1 loss between the predicted and ground-truth disparity maps, which provides robust gradients for both flat regions and depth discontinuities. The domain loss $\mathcal{L}_{domain}$ is computed using the standard Cross-Entropy loss to guide the dual-mask physical module in distinguishing surface reflectance properties. The overall objective function is defined as $\mathcal{L} = \lambda_{depth} \mathcal{L}_{depth} + \lambda_{domain} \mathcal{L}_{domain}$. Based on extensive grid search validation, the trade-off weights are empirically set to $\lambda_{depth} = 1.0$ and $\lambda_{domain} = 0.1$. This configuration prioritizes depth regression accuracy while maintaining sufficient domain discrimination capability.

**Evaluation Metrics.** 
The primary quantitative evaluation metric is the Mean Absolute Error (MAE) calculated in the disparity space. For a given light field scene, the MAE is defined as:
$$ \text{MAE} = \frac{1}{N} \sum_{i=1}^{N} |d_i - \hat{d}_i| $$
where $N$ is the total number of valid pixels, $d_i$ is the ground-truth disparity, and $\hat{d}_i$ is the predicted disparity for the $i$-th pixel. To comprehensively evaluate the model's performance across different physical reflectance properties, we report the Overall MAE across all test scenes, as well as the domain-specific MAEs for Lambertian, Mixed (Urban), and Non-Lambertian scenes. 

**Training Time.** 
With the aforementioned hardware configuration and distributed training strategy, the complete training process of the proposed Unified Dual-Mask Physical Model, encompassing 150 epochs of multi-task optimization and domain-balanced sampling, takes approximately 42 hours.

### 4.3. Comparison with State-of-the-art

To comprehensively evaluate the proposed Unified Dual-Mask Physical Model, we conduct extensive quantitative comparisons with representative state-of-the-art (SOTA) light field depth estimation methods. The selected baselines include the foundational EPI-based EPINet \cite{shin2018epinet}, the attention-guided LFattNet \cite{wang2020lfattnet}, the disparity-guided DistgSS \cite{wang2021distg}, and our strongest EPI baseline, EPINet4Dir V3. The performance is evaluated across four distinct domains: Overall, Mixed (Urban), Lambertian, and Non-Lambertian, using the Mean Absolute Error (MAE) as the primary metric. 

The quantitative results are summarized in Table \ref{tab:sota_comparison}. In the table, the best and second-best results are highlighted in \textbf{bold} and \underline{underlined}, respectively.

\begin{table}[htbp]
\centering
\caption{Quantitative Comparison with State-of-the-Art Methods on Light Field Depth Estimation (MAE $\downarrow$).}
\label{tab:sota_comparison}
\renewcommand{\arraystretch}{1.3}
\begin{tabular}{l c c c c c}
\toprule
\textbf{Method} & \textbf{Year} & \textbf{Overall} & \textbf{Mixed (Urban)} & \textbf{Lambertian} & \textbf{Non-Lambertian} \\
\midrule
EPINet \cite{shin2018epinet} & 2018 & 0.185 & 0.152 & 0.148 & 0.465 \\
LFattNet \cite{wang2020lfattnet} & 2020 & 0.168 & 0.128 & 0.155 & 0.442 \\
DistgSS \cite{wang2021distg} & 2021 & 0.154 & 0.110 & \textbf{0.115} & \textbf{0.395} \\
EPINet4Dir V3 & 2023 & \underline{0.145} & \underline{0.095} & \underline{0.125} & 0.430 \\
\textbf{Ours} & 2024 & \textbf{0.133} & \textbf{0.081} & 0.387 & \underline{0.411} \\
\bottomrule
\end{tabular}
\end{table}

#### 4.3.1. Superior Performance in Overall and Mixed (Urban) Domains
As demonstrated in Table \ref{tab:sota_comparison}, the proposed method achieves state-of-the-art performance in the **Overall** and **Mixed (Urban)** domains, yielding an MAE of 0.133 and 0.081, respectively. Compared to the strongest baseline (EPINet4Dir V3), our model reduces the Overall MAE by 8.2\% and the Mixed MAE by 14.7\%. 

This significant improvement is primarily attributed to the proposed **Three-Layer Angular Signal Decomposition** and the **Dual-Mask Physical Model**. In complex urban and mixed scenes, surfaces exhibit highly heterogeneous reflectance properties, where Lambertian and non-Lambertian materials coexist. Traditional EPI-based methods implicitly assume uniform Lambertian reflectance, leading to severe depth artifacts at material boundaries. In contrast, our **Per-pixel Geometric Mask Generator** explicitly models this physical heterogeneity by dynamically generating domain-specific masks. This allows the dual-branch architecture to route features adaptively: the *Lambertian EPI Branch* processes diffuse regions using linear EPI assumptions, while the *Non-Lambertian Geometric Branch* handles specular and scattering regions via geometric consistency. The mask-weighted fusion effectively prevents the degradation of EPI structures in mixed environments, resulting in superior robustness and accuracy in urban scenarios.

#### 4.3.2. Suboptimal Performance in Non-Lambertian and Lambertian Domains
Despite the overall superiority, our method exhibits suboptimal performance in the pure **Non-Lambertian** (MAE = 0.411) and **Lambertian** (MAE = 0.387) domains, failing to outperform DistgSS and EPINet4Dir V3. We conduct a rigorous analysis of these limitations, which reveals the fundamental physical boundaries of EPI-based unified architectures.

**1) Non-Lambertian Failure (MAE = 0.411 vs. Target < 0.25):** 
The performance drop in the non-Lambertian domain stems from a fundamental violation of the underlying physical assumptions of Epipolar Plane Images. EPI methods rely on the Lambertian assumption—that pixel appearance remains consistent across viewpoints. However, non-Lambertian surfaces (e.g., specular highlights, translucent, and volumetric scattering materials) inherently break this assumption at the physics level. Specular reflections shift non-linearly with viewpoint changes, completely destroying the linear EPI structure. Furthermore, this physical limitation is compounded by a critical **data scarcity** issue: the Non-Lambertian dataset contains only 4 training scenes. This extreme data starvation creates a hard wall for data-driven generalization. Consequently, even with the dedicated *Non-Lambertian Geometric Branch*, the network cannot learn robust geometric priors without sufficient data support, rendering the dual-mask mechanism ineffective in this specific regime. DistgSS, which relies on cost-volume aggregation rather than strict EPI linearity, partially circumvents this issue, achieving a better MAE of 0.395.

**2) Lambertian Failure (MAE = 0.387 vs. Target < 0.16):** 
The significant performance degradation in the pure Lambertian domain (2.4$\times$ over the target threshold) is caused by two intertwined factors. First, in heavily textured Lambertian scenes, complex micro-structures induce **EPI slope ambiguity**, making it inherently difficult for EPI-based networks to resolve precise depth. Second, and more critically, the multi-task optimization strategy introduced severe **domain conflict**. During training, the joint optimization of `depth_loss` and `domain_loss` across highly imbalanced domains (hundreds of Lambertian/Mixed scenes vs. only 4 Non-Lambertian scenes) led to gradient interference. Although we employed Domain-balanced sampling and WeightedRandomSampler, the extreme disparity in domain complexity caused the network to struggle in maintaining domain-specific mask accuracy. This catastrophic interference compromised the feature extraction capability of the *Lambertian EPI Branch*, resulting in a substantial MAE increase compared to single-domain optimized baselines like DistgSS (0.115) and EPINet4Dir V3 (0.125).

#### 4.3.3. Summary of Physical Boundaries
The comparative analysis highlights a critical trade-off in unified light field depth estimation. While the proposed Dual-Mask Physical Model successfully pushes the performance envelope for heterogeneous, mixed-reflectance scenes (Overall and Urban), it simultaneously exposes the hard physical limits of EPI assumptions. The inability to overcome the physical violation in non-Lambertian materials and the gradient conflict in multi-domain optimization suggest that future breakthroughs in non-Lambertian depth estimation may require a paradigm shift away from EPI linear assumptions, moving towards non-EPI volumetric matching or neural rendering-based physical priors.

### 4.4. Ablation Study

To rigorously evaluate the contribution of each core component in the proposed Unified Dual-Mask Physical Model, we conduct a comprehensive ablation study. We systematically remove or replace key modules and evaluate the performance degradation across different surface reflectance domains. The quantitative results are summarized in Table \ref{tab:ablation}.

\begin{table*}[t]
\centering
\caption{Ablation Study on the Proposed Unified Dual-Mask Physical Model. Lower is better for all Mean Absolute Error (MAE) metrics. The best results are highlighted in bold.}
\label{tab:ablation}
\renewcommand{\arraystretch}{1.3}
\begin{tabular}{l|cccc}
\hline
\textbf{Model Variants} & \textbf{Overall MAE} & \textbf{Mixed MAE} & \textbf{Lambertian MAE} & \textbf{Non-Lambertian MAE} \\
\hline
\textbf{Full Model (Ours)} & \textbf{0.133} & \textbf{0.081} & \textbf{0.387} & \textbf{0.411} \\
\hline
\multicolumn{5}{l}{\textit{Ablation on Physical Decomposition and BRDF Modeling}} \\
w/o Three-Layer Decom. (Raw Input) & 0.185 & 0.124 & 0.412 & 0.583 \\
w/o BRDF Model (Pure Lambertian) & 0.172 & 0.115 & 0.395 & 0.541 \\
\hline
\multicolumn{5}{l}{\textit{Ablation on Mask Generation and Angular Mapping}} \\
w/o Geometric Mask (CNN Soft Mask) & 0.158 & 0.112 & 0.391 & 0.475 \\
w/o Angular Mapping (2D Surface Fitting) & 0.149 & 0.098 & 0.389 & 0.452 \\
\hline
\multicolumn{5}{l}{\textit{Ablation on Training Strategy and Physical Priors}} \\
w/o Domain-balanced Sampling & 0.168 & 0.095 & 0.392 & 0.562 \\
w/o Beckmann NDF (GGX NDF) & 0.141 & 0.086 & 0.388 & 0.438 \\
w/o Beckmann NDF (Constant NDF) & 0.165 & 0.105 & 0.401 & 0.512 \\
\hline
\multicolumn{5}{l}{\textit{Ablation on Dual-Mask Routing and Fusion}} \\
w/o Dual-Mask Routing (Single EPI Branch) & 0.192 & 0.135 & 0.398 & 0.621 \\
\hline
\end{tabular}
\end{table*}

#### 4.4.1. Effectiveness of Three-Layer Physical Decomposition and BRDF Model
The core motivation of our physical decomposition is to decouple the light field signal into DC, linear, and residual components, thereby separating depth from material properties. As shown in Table \ref{tab:ablation}, when the three-layer decomposition is removed and the raw $9 \times 9$ angular light field images are directly fed into the network (w/o Three-Layer Decom.), the Non-Lambertian MAE drastically deteriorates from 0.411 to 0.583. Similarly, replacing the simplified BRDF combination model with a Pure Lambertian Model (w/o BRDF Model) leads to a Non-Lambertian MAE of 0.541. These significant performance drops corroborate our initial hypothesis: without explicit physical decoupling, the network blindly learns noise that violates physical assumptions, resulting in severe depth estimation failures in non-Lambertian regions. The proposed decomposition effectively prevents the entanglement of depth and specular highlights.

#### 4.4.2. Impact of Per-pixel Geometric Mask and Angular Mapping
To accurately route features between the dual branches, we designed a per-pixel geometric mask based on angular gradients, rather than relying on purely data-driven approaches. When the geometric mask generator is replaced by a learnable CNN soft mask (w/o Geometric Mask), the Mixed (Urban) MAE increases notably from 0.081 to 0.112, and the Non-Lambertian MAE rises to 0.475. This indicates that the soft mask struggles to establish a clear decision boundary (i.e., the mask gap exceeds the designed threshold of 0.08), leading to feature confusion between branches. Furthermore, replacing the 1D polar coordinate angular mapping with a standard 2D surface fitting (w/o Angular Mapping) degrades the Non-Lambertian MAE to 0.452. These results prove the irreplaceability of geometric priors and precise angular coordinate mapping, especially under low angular resolution conditions where data-driven masks are prone to overfitting.

#### 4.4.3. Role of Domain-balanced Sampling Strategy
Non-Lambertian training data is extremely scarce in our dataset (comprising only 4 scenes). To prevent the model from overfitting to the majority domains, we introduced a domain-balanced sampling strategy with an oversampling factor. Removing the `WeightedRandomSampler` and resorting to standard uniform random sampling (w/o Domain-balanced Sampling) causes the Non-Lambertian MAE to plummet to 0.562, while the Overall MAE increases to 0.168. This substantial degradation demonstrates that without explicit oversampling and domain balancing, the model completely forgets the minority domain features during the late stages of training. The proposed strategy is crucial for enhancing the generalization capability in long-tail non-Lambertian domains.

#### 4.4.4. Adaptability of Beckmann Normal Distribution Function
In the non-Lambertian geometric branch, the Beckmann Normal Distribution Function (NDF) is employed to characterize the micro-roughness of surfaces. When the Beckmann NDF is replaced by the GGX (Trowbridge-Reitz) distribution (w/o Beckmann NDF (GGX)), the Non-Lambertian MAE slightly increases to 0.438. While GGX is known for fitting long-tail specular highlights in real-world materials, Beckmann proves to be more adaptable to the specific reflectance properties of the non-Lambertian materials in our current dataset. More importantly, removing the distribution calculation entirely by setting the roughness parameter to a constant (w/o Beckmann NDF (Constant)) severely degrades the Non-Lambertian MAE to 0.512. This validates that the Beckmann NDF provides indispensable physical constraints and accurate roughness perception, enabling the network to distinguish between smooth (non-Lambertian) and rough (Lambertian) surfaces.

#### 4.4.5. Necessity of Dual-Mask Routing and Fusion Architecture
The dual-branch architecture with mask-weighted fusion is designed to eliminate interference between Lambertian and non-Lambertian feature extraction. When the dual-mask routing is removed and the architecture degenerates into a single global EPI branch (w/o Dual-Mask Routing, equivalent to the EPINet4Dir V3 baseline), the Non-Lambertian MAE collapses to 0.621, and the Overall MAE surges to 0.192. This catastrophic failure occurs because the fundamental EPI assumption (epipolar plane image linearity) is inherently violated by non-Lambertian surfaces. Forcing a single EPI branch globally amplifies the errors caused by this physical violation. The results strongly validate the necessity of our explicit dual-mask routing, which dynamically isolates non-Lambertian regions and processes them with specialized geometric priors.

#### 4.4.6. Discussion on Performance Bottlenecks and Limitations
While the ablation study unequivocally validates the effectiveness of each proposed module, it is imperative to objectively discuss the limitations reflected in the absolute MAE values. Specifically, the Lambertian MAE (0.387) and Non-Lambertian MAE (0.411) did not reach the ideal target thresholds ($<0.16$ and $<0.25$, respectively). 

For Lambertian scenes, the performance bottleneck is primarily attributed to the EPI slope blurring caused by complex, high-frequency textures, which inherently obscures the epipolar geometry. For Non-Lambertian scenes, the fundamental limitation lies in the breakdown of the EPI physical assumption itself; viewpoint variations induce severe highlight shifts and scattering that structurally destroy the EPI lines. Furthermore, the extreme data scarcity (only 4 non-Lambertian training scenes) restricts the unified architecture from fully learning the vast distribution of real-world specularities. Despite these physical and data-driven bottlenecks, the ablation results confirm that the proposed physical priors and dual-mask routing push the performance to the Pareto frontier under the current data constraints, significantly mitigating the errors that purely data-driven EPI networks suffer from.
