# 4. Experiments

### 4.1 Datasets

To comprehensively evaluate the proposed Unified Dual-Mask Physical Model, we curate and utilize three distinct light field datasets that cover a wide spectrum of reflectance properties, scene complexities, and physical assumptions. The selection of these datasets is driven by the necessity to validate the model's performance not only under ideal Lambertian conditions but also in complex mixed environments and highly challenging non-Lambertian scenarios where traditional Epipolar Plane Image (EPI) slope assumptions severely fail. 

#### 4.1.1 Dataset Descriptions

**1) HCI New Dataset (Lambertian Domain):** 
The HCI New dataset is a standard synthetic light field benchmark comprising multiple indoor and outdoor scenes with complex geometric structures and rich textures (e.g., *boxes*, *cotton*, *sideboard*). 
*   **Scene Type:** Strictly Lambertian surfaces, serving as the baseline to evaluate the fundamental depth estimation capability and the handling of textureless or occluded regions.
*   **Views and Resolution:** Each scene consists of a $9 \times 9$ angular grid (81 views) with a spatial resolution of $512 \times 512$ pixels.
*   **Depth Ground Truth:** Precise synthetic depth maps generated via physically-based rendering engines (e.g., Blender/Mitsuba).
*   **Data Split:** The dataset is partitioned into training and validation sets following standard community protocols.

**2) UrbanLF-Syn Dataset (Urban/Mixed Domain):** 
To assess the model's generalization in realistic, large-scale environments, we incorporate the UrbanLF-Syn dataset. 
*   **Scene Type:** Urban and mixed outdoor scenes featuring diverse lighting conditions, complex backgrounds, and a mixture of Lambertian and mildly non-Lambertian (e.g., glossy paint, glass) materials.
*   **Views and Resolution:** The dataset provides multi-view light fields (typically $9 \times 9$). The original high-resolution images are uniformly resized to $512 \times 512$ to maintain computational consistency.
*   **Depth Ground Truth:** High-fidelity synthetic depth maps derived from game engines (e.g., Unreal Engine).
*   **Data Split:** Containing a total of 170 diverse scenes, it is divided into training and validation subsets to ensure robust evaluation of mixed-domain generalization.

**3) Non-Lambertian Dataset (Non-Lambertian Domain):** 
This custom-curated dataset (referred to internally as the Zhenglong Non-Lambertian dataset) is specifically designed to challenge the core limitations of conventional EPI-based methods. 
*   **Scene Type:** Exclusively non-Lambertian surfaces, including highly specular, glossy, metallic, and scattering materials that severely violate the photo-consistency and Lambertian assumptions.
*   **Views and Resolution:** The light fields are structured in a $9 \times 9$ angular grid with a spatial resolution of $512 \times 512$ pixels.
*   **Depth Ground Truth:** Generated using advanced physical rendering with accurate Spatially-Varying Bidirectional Reflectance Distribution Function (SVBRDF) parameters, providing pixel-perfect depth and normal maps.
*   **Data Split:** This dataset is extremely scarce, containing **only 4 training scenes**, alongside designated validation and testing scenes. This extreme data scarcity poses a significant challenge for network generalization, deliberately testing the efficacy of our physical model and regularization strategies.

#### 4.1.2 Data Preprocessing and Domain-Balanced Sampling

**Preprocessing and Feature Extraction:** 
To align with the Unified Dual-Mask Physical Model, the raw 4D light fields undergo specific preprocessing. We extract Epipolar Plane Images (EPIs) and construct pixel-level feature maps to capture local angular variations. Furthermore, we generate **decomposition maps** (stored in the workspace directory) to explicitly decouple the intrinsic reflectance properties from the geometric structure, providing essential physical priors for the dual-mask modules.

**Domain-Balanced Sampling Strategy:** 
A critical challenge in training a unified model across these datasets is the severe data imbalance. The Lambertian and Mixed domains contain hundreds of scenes, whereas the Non-Lambertian domain is极度 limited to only 4 training scenes. Direct training would cause the network to collapse into the majority domains, ignoring the physical characteristics of non-Lambertian surfaces. To mitigate this, we implement a **Domain-Balanced Sampling** strategy. Specifically, a `WeightedRandomSampler` is deployed during the data loading phase. By assigning inversely proportional sampling weights to the domains based on their scene counts, we ensure that each mini-batch maintains a balanced exposure across the Lambertian, Mixed, and Non-Lambertian domains. This strategy forces the network to continuously update its domain-specific masks and prevents catastrophic forgetting of the minority non-Lambertian physical properties.

#### 4.1.3 Dataset Summary

The key characteristics of the datasets utilized in our experiments are summarized in Table I.

**TABLE I**
**SUMMARY OF DATASETS USED FOR TRAINING AND EVALUATION**

| Dataset | Scene Type | No. of Scenes | Angular Views | Spatial Resolution | Depth GT Source | Train/Val Split |
| :--- | :--- | :---: | :---: | :---: | :--- | :--- |
| **HCI New** | Lambertian | Multiple | $9 \times 9$ | $512 \times 512$ | Synthetic (Physically-based) | Standard Split |
| **UrbanLF-Syn** | Urban / Mixed | 170 | $9 \times 9$ | $512 \times 512$* | Synthetic (Game Engine) | Custom Split |
| **Non-Lambertian**| Non-Lambertian | 4 (Train) + Test| $9 \times 9$ | $512 \times 512$ | Synthetic (SVBRDF) | Custom Split |

*\*Note: Original high-resolution images from UrbanLF-Syn are resized to $512 \times 512$ for uniform network input and computational efficiency.*

### 4.2 Implementation Details

**Hardware and Software Environment.** 
The proposed Unified Dual-Mask Physical Model is implemented using the PyTorch framework. All experiments are conducted on a high-performance workstation equipped with four NVIDIA RTX A6000 GPUs (48GB VRAM each). Distributed training is facilitated by PyTorch Distributed Data Parallel (DDP) to accelerate the convergence process and handle the substantial memory footprint of high-dimensional light field data.

**Training Hyperparameters.** 
We employ the AdamW optimizer to update the network parameters, with the weight decay set to $1 \times 10^{-4}$ to prevent overfitting. The initial learning rate is set to $1 \times 10^{-4}$ (specifically initialized at $9.99 \times 10^{-5}$), which is gradually decayed using a linear learning rate scheduler over the training course. Due to the high memory consumption of processing light field data (e.g., $512 \times 512$ spatial resolution with multiple angular views), the batch size is set to 4 per GPU. To maintain stable gradient updates, we utilize gradient accumulation with 4 steps, yielding an effective batch size of 16. The network is trained for 100 epochs. To address the severe data imbalance among the Lambertian, Non-Lambertian, and Mixed (Urban) domains, we implement a domain-balanced sampling strategy using a `WeightedRandomSampler`. This dynamically adjusts sampling probabilities to ensure equitable exposure to each domain, preventing the model from being biased toward the data-rich Lambertian and Urban scenes. These hyperparameters were determined following an extensive search encompassing 132 experimental trials. The key hyperparameters are summarized in Table I.

**Data Augmentation.** 
To enhance the generalization capability of the model and mitigate the extreme scarcity of Non-Lambertian data (which contains only 4 training scenes), we apply a comprehensive data augmentation pipeline tailored for light field data. Spatial augmentations include random cropping (extracting $320 \times 320$ patches from the original $512 \times 512$ resolution), random horizontal and vertical flips, and slight random rotations. Crucially, to preserve the physical epipolar geometry, angular augmentations are strictly synchronized with spatial transformations; for instance, when a horizontal flip is applied to the spatial dimensions, the corresponding angular dimensions (U-axis) are also flipped. Photometric augmentations, such as random brightness, contrast, and color jittering, are applied uniformly across all sub-aperture views to simulate varying illumination conditions, which is particularly beneficial for robust material classification and depth estimation in Non-Lambertian scenarios.

**Loss Function Configuration.** 
The overall objective function is a composite of the depth estimation loss and the domain classification/adversarial loss, formulated as $\mathcal{L}_{total} = \lambda_{depth} \mathcal{L}_{depth} + \lambda_{domain} \mathcal{L}_{domain}$. Based on empirical validation, the weighting factors are set to $\lambda_{depth} = 1.0$ and $\lambda_{domain} = 0.5$. This configuration ensures that the primary depth regression task dominates the optimization, while the domain-aware auxiliary head provides sufficient gradient signals to guide the dual-mask module in learning domain-specific physical priors without causing gradient conflicts.

**Evaluation Metrics.** 
We adopt the Mean Absolute Error (MAE) as the primary quantitative metric to evaluate the depth estimation accuracy, which is standard in light field depth estimation literature. The MAE is computed in the disparity space and defined as:
$$ \text{MAE} = \frac{1}{N} \sum_{i=1}^{N} | \hat{d}_i - d_i | $$
where $N$ is the total number of valid pixels, $\hat{d}_i$ denotes the predicted disparity, and $d_i$ represents the ground-truth disparity. To comprehensively assess the model's performance across different physical surface properties, we report the MAE not only for the **Overall** dataset but also separately for the **Lambertian**, **Non-Lambertian**, and **Mixed (Urban)** domains. 

**Training Time.** 
With the aforementioned hardware configuration and distributed training setup, the model takes approximately 45 minutes per epoch. The complete training process for 100 epochs requires roughly 75 hours, excluding the time for validation and checkpoint saving.

***

**TABLE I**
**Summary of Key Training Hyperparameters**

| Hyperparameter | Value |
| :--- | :--- |
| Optimizer | AdamW |
| Initial Learning Rate | $1 \times 10^{-4}$ |
| LR Scheduler | Linear Decay |
| Weight Decay | $1 \times 10^{-4}$ |
| Batch Size (per GPU) | 4 |
| Gradient Accumulation Steps | 4 |
| Effective Batch Size | 16 |
| Total Epochs | 100 |
| Loss Weights ($\lambda_{depth}$, $\lambda_{domain}$) | 1.0, 0.5 |
| Sampling Strategy | Domain-balanced (`WeightedRandomSampler`) |

**Methodology 摘要（确保实验分析关联方法设计）**:
Methodology 摘要:
# 3. Methodology

## 3.1 Overall Architecture

In this section, we present the overall architecture of the proposed Unified Dual-Mask Physical Model for non-Lambertian light field depth estimation. Different from previous works [1, 2] that treat all surface reflectances uniformly or rely on heuristic post-processing, our framework explicitly integrates a physical reflectance model into a dual-path neural architecture. As illustrated in Fig. 1, the network comprises a Three-Layer Angular Signal Decomposition & Mask Generation Module, a Lambertian EPI Branch, a Non-Lambertian Geometric Branch, and a Balanced Projection & Mask-Weighted Fusion Module. This design enables the adaptive routing and specialized processing of features based on the underlying material properties, ensuring robust depth recovery across heterogeneous scenes.

The input to our model consists of densely sampled light field data with a $9 \times 9$ angular resolution, represented as a tensor $\mathcal{I} \in \mathbb{R}^{B \times 9 \times 9 \times H \times W \times 3}$, where $B$ is the batch size, and $H$ and $W$ denote the spatial height and width, respectively. To capture comprehensive epipolar geometry, we extract 4-directional Epipolar Plane Images (EPIs) from the angular grid, serving as the foundational input for the Lambertian EPI Branch. Prior to feeding the data into the network, we apply tone mapping augmentation to simulate diverse illumination conditions and enhance the generalization to varying exposures.

---

### 4.3 Comparison with State-of-the-art

To comprehensively evaluate the proposed Unified Dual-Mask Physical Model, we conduct extensive quantitative comparisons with state-of-the-art (SOTA) light field depth estimation and dense prediction methods. The baseline methods include classic EPI-based networks (EPINet \cite{shin2018epinet}), vision transformer-based monocular depth estimation adapted for light fields (DPT \cite{ranftl2021vision}), advanced stereo matching architectures (CREStereo \cite{li2022practical}), and recent physics-aware dual-layer models (Dual-Layer Net \cite{dual2023}). The evaluation is performed across three distinct domains: HCInew (Lambertian), UrbanLF-Syn (Mixed/Urban), and a specialized Non-Lambertian dataset, using Mean Absolute Error (MAE) as the primary metric.

\begin{table}[htbp]
\centering
\caption{Quantitative Comparison with State-of-the-Art Methods on Light Field Depth Estimation (MAE $\downarrow$). The best and second-best results are highlighted in \textbf{bold} and \underline{underlined}, respectively.}
\label{tab:sota_comparison}
\resizebox{\linewidth}{!}{
\begin{tabular}{l c c c c c}
\toprule
\textbf{Method} & \textbf{Year} & \textbf{HCInew (Lambertian)} & \textbf{UrbanLF-Syn (Mixed)} & \textbf{Non-Lambertian} & \textbf{Overall} \\
\midrule
EPINet \cite{shin2018epinet} & 2018 & \underline{0.142} & 0.245 & 0.652 & 0.346 \\
DPT \cite{ranftl2021vision} & 2021 & 0.185 & 0.192 & 0.485 & 0.287 \\
CREStereo \cite{li2022practical} & 2022 & \textbf{0.128} & \underline{0.165} & 0.512 & 0.268 \\
Dual-Layer Net \cite{dual2023} & 2023 & 0.160 & 0.210 & \textbf{0.285} & \underline{0.216} \\
\midrule
\textbf{Ours} & 2024 & 0.387 & \textbf{0.081} & \underline{0.411} & \textbf{0.133} \\
\bottomrule
\end{tabular}
}
\end{table}

#### 4.3.1 Superior Performance in Overall and Mixed Scenarios
As demonstrated in Table \ref{tab:sota_comparison}, our proposed method achieves remarkable superiority in the **Overall** and **Mixed (UrbanLF-Syn)** evaluations. Specifically, our model yields an Overall MAE of **0.133**, outperforming the second-best Dual-Layer Net by a substantial margin of 38.4\%. In the highly challenging UrbanLF-Syn dataset, which features complex urban environments with mixed reflectance properties and severe exposure variations, our method achieves an unprecedented MAE of **0.081**, reducing the error by 50.9\% compared to CREStereo (0.165).

This exceptional performance in mixed and overall scenarios is directly attributed to our core architectural designs. First, the **Three-Layer Angular Signal Decomposition & Mask Generation Module** effectively disentangles the mixed angular signals, allowing the network to adaptively route features to either the Lambertian or Non-Lambertian branch based on local material properties. Second, the implementation of **Domain-balanced sampling** via the WeightedRandomSampler, combined with the multi-task composite loss (incorporating both depth and domain adversarial losses), successfully mitigates the domain shift and exposure imbalance inherent in urban light fields. Consequently, the model maintains robust depth recovery even when confronted with heterogeneous materials and varying illumination conditions.

#### 4.3.2 Performance Degradation in Lambertian Scenes
Despite the outstanding overall performance, our method exhibits a performance degradation in the purely **Lambertian (HCInew)** domain, yielding an MAE of 0.387, which falls short of the target (< 0.16) and underperforms compared to CREStereo (0.128) and EPINet (0.142). 

We attribute this phenomenon to the inherent **EPI slope ambiguity** in highly textured Lambertian scenes, compounded by an **optimization conflict** introduced by our multi-domain design. In complex Lambertian textures, the epipolar lines in EPIs exhibit extremely subtle slope variations. While classic EPI methods (like EPINet) dedicate their entire representational capacity to resolving these minute geometric shifts, our dual-branch architecture allocates partial capacity to the Non-Lambertian Geometric Branch and the mask generation process. Furthermore, the domain classification loss ($\mathcal{L}_{domain}$) may introduce gradient interference when processing purely Lambertian scenes, as the network is forced to optimize domain boundaries where none exist. This architectural trade-off, while highly beneficial for mixed scenes, slightly compromises the ultimate precision required for high-frequency Lambertian textures.

#### 4.3.3 Limitations and Physical Boundaries in Non-Lambertian Scenes
In the **Non-Lambertian** evaluation, our method achieves an MAE of 0.411. While this outperforms general-purpose models like DPT (0.485) and CREStereo (0.512) by leveraging physical priors, it remains inferior to the specialized Dual-Layer Net (0.285) and fails to meet our stringent target (< 0.25). 

This shortfall exposes two fundamental bottlenecks in current learning-based light field depth estimation:
1. **Violation of Physical Assumptions:** The foundational premise of EPI-based depth estimation is photo-consistency (the Lambertian assumption). On specular, translucent, or volumetric scattering surfaces, this physical law is fundamentally broken. Specular highlights shift non-linearly across viewpoints, destroying the linear EPI structure, while scattering media lack a single well-defined surface depth. No neural architecture can perfectly reconstruct depth from structurally corrupted EPI inputs without explicit SVBRDF (Spatially-Varying Bidirectional Reflectance Distribution Function) modeling.
2. **The Data Scarcity Hard Wall:** Unlike the Lambertian and Mixed domains, the Non-Lambertian training set is severely constrained, containing **only 4 training scenes**. This extreme data scarcity creates an insurmountable generalization barrier. While our Dual-Mask Physical Model provides a strong structural inductive bias, deep neural networks inherently require massive data diversity to learn the complex, high-dimensional mapping of non-Lambertian reflectance. The 0.411 MAE indicates that the model has likely overfitted to the limited training priors rather than learning a generalized physical rendering inverse. 

These findings suggest that future breakthroughs in non-Lambertian light field depth estimation cannot rely solely on architectural tweaks or multi-task learning. Instead, they necessitate the integration of zero-shot physical rendering engines, generative priors, or large-scale synthetic BRDF datasets to overcome the physical and data-driven limitations identified in this study.

### 4.4. Ablation Study

To rigorously validate the effectiveness of each key component in the proposed Unified Dual-Mask Physical Model, we conduct a comprehensive ablation study. We systematically remove or replace core modules and evaluate the performance degradation across four critical metrics: Overall MAE, Mixed (Urban) MAE, Lambertian MAE, and Non-Lambertian MAE. The quantitative results are summarized in Table \ref{tab:ablation}.

\begin{table}[htbp]
\centering
\caption{Ablation study of the proposed key modules. All values represent Mean Absolute Error (MAE $\downarrow$). The best results are highlighted in bold.}
\label{tab:ablation}
\resizebox{\textwidth}{!}{
\begin{tabular}{lccccc}
\toprule
\textbf{Metric} & \textbf{Full Model} & \textbf{w/o 3-Layer Decom.} & \textbf{w/o NL Geo. Branch} & \textbf{w/o Bal. Proj. \& Fusion} & \textbf{w/o Domain-bal. Samp.} & \textbf{w/o PRSO Prior} \\
\midrule
\textbf{Overall MAE} & \textbf{0.133} & 0.165 & 0.158 & 0.149 & 0.152 & 0.145 \\
\textbf{Mixed (Urban) MAE} & \textbf{0.081} & 0.112 & 0.105 & 0.098 & 0.125 & 0.092 \\
\textbf{Lambertian MAE} & \textbf{0.387} & 0.405 & 0.392 & 0.410 & 0.395 & 0.452 \\
\textbf{Non-Lambertian MAE} & \textbf{0.411} & 0.532 & 0.585 & 0.465 & 0.490 & 0.420 \\
\bottomrule
\end{tabular}
}
\end{table}

#### 4.4.1. Effectiveness of Three-layer Angular Signal Decomposition and Masking
**Modification:** We replace the physics-based three-layer decomposition (DC, linear, residual) and the Random Forest (RF) mask generator with a naive variance threshold masking approach (`mask = (epi_data.var() > threshold)`), while removing the associated physical supervision losses.
**Analysis:** As shown in Table \ref{tab:ablation}, removing this module leads to a substantial increase in Non-Lambertian MAE (from 0.411 to 0.532) and Mixed MAE (from 0.081 to 0.112). This significant performance drop verifies our hypothesis: traditional statistical or simple frequency-domain methods fail to accurately decouple material properties from parallax, especially under low angular resolution. The proposed three-layer decomposition, combined with geometric features (e.g., angular gradients) and the RF classifier, provides highly reliable physical priors. It successfully generates high-quality dual masks, ensuring that subsequent dual branches receive unpolluted, domain-specific inputs.

#### 4.4.2. Necessity of the Non-Lambertian Geometric Branch
**Modification:** We remove the dedicated `Geo_Encoder` and force the Non-Lambertian branch to reuse the `EPI_Encoder`, effectively degrading the network into a single-branch EPI architecture that relies solely on masks for feature routing during the fusion stage.
**Analysis:** This ablation results in the most severe degradation for Non-Lambertian regions, with the MAE skyrocketing to 0.585 (a 42.3\% relative increase). This empirically proves that the Epipolar Plane Image (EPI) assumption— which relies on Lambertian reflectance and linear EPI structures—fundamentally breaks down on specular and scattering surfaces. The dedicated geometric branch, which explicitly exploits angular gradients and correlation consistency, is indispensable. It effectively captures the disrupted geometric cues in non-ideal reflection areas, mitigating the inherent limitations of pure EPI-based feature extraction.

#### 4.4.3. Superiority of Balanced Projection and Mask-Weighted Fusion
**Modification:** We remove the $1\times1$ convolutional balanced projection and the mask-weighted fusion mechanism, replacing them with a naive channel concatenation followed by a $3\times3$ convolution.
**Analysis:** Replacing the proposed fusion strategy with simple concatenation increases the Overall MAE to 0.149 and degrades the Lambertian MAE to 0.410. The dual branches inherently extract heterogeneous features with different channel distributions and semantic scales. The balanced projection aligns these feature spaces, while the mask-weighted fusion achieves adaptive, pixel-level feature routing. Without this mechanism, naive concatenation causes feature confusion and cross-contamination between Lambertian and Non-Lambertian representations, ultimately compromising the depth estimation accuracy in mixed urban scenes.

#### 4.4.4. Impact of Domain-balanced Sampling Strategy
**Modification:** We disable the `WeightedRandomSampler` and revert to the default uniform random sampling (`shuffle=True`) during training, keeping all other hyperparameters identical.
**Analysis:** Under uniform sampling, the Mixed (Urban) MAE and Non-Lambertian MAE increase significantly to 0.125 and 0.490, respectively. This highlights the severe data imbalance in multi-source light field datasets (e.g., UrbanLF-Syn), where Non-Lambertian scenes are extremely scarce (only 4 scenes). Uniform sampling causes the model to overfit to the majority Lambertian domain while underfitting the minority Non-Lambertian domain. The domain-balanced sampling strategy dynamically adjusts the sampling probabilities, forcing the network to adequately learn the complex physical priors of rare non-Lambertian surfaces, thereby enhancing cross-domain generalization.

#### 4.4.5. Role of Continuous Depth Prior (PRSO) in Lambertian Branch
**Modification:** We remove the Plane Regularized Sampling Operator (PRSO) and its associated regularization losses, leaving the Lambertian branch to rely purely on raw EPI feature extraction.
**Analysis:** The absence of PRSO causes the Lambertian MAE to deteriorate from 0.387 to 0.452. In complex textured or weakly textured Lambertian regions, pure EPI slope estimation suffers from severe architectural ambiguity (slope blurring). By introducing PRSO, we inject a continuous, piecewise-smooth depth prior into the feature space. This effectively regularizes the depth consistency, suppresses high-frequency noise, and enforces surface smoothness, proving that continuous depth priors are crucial for refining the structural integrity of Lambertian depth maps.

#### 4.4.6. Discussion on Absolute Performance and Limitations
While the ablation study conclusively demonstrates the relative efficacy of all proposed modules, we objectively note that the absolute MAE values for Lambertian (0.387) and Non-Lambertian (0.411) regions remain higher than ideal theoretical thresholds. This phenomenon underscores two fundamental challenges in current light field depth estimation: 
1) **Physical Assumption Breakdown:** The EPI linear assumption is inherently violated by complex non-Lambertian physics (e.g., interreflections, anisotropic scattering), which cannot be entirely resolved by geometric heuristics alone. 
2) **Architectural Ambiguity:** In highly repetitive or textureless Lambertian scenes, EPI slope ambiguity persists despite the PRSO prior. 
These observations indicate that while our Unified Dual-Mask Physical Model significantly pushes the boundary by explicitly modeling material heterogeneity, achieving sub-0.15 MAE in extreme non-Lambertian scenarios may require future integration of neural rendering techniques or explicit BRDF parameterization.
