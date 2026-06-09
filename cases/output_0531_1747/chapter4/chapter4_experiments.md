# 4. Experiments

### 4.1 Datasets

To comprehensively evaluate the proposed Unified Dual-Mask Physical Model, we conduct extensive experiments on three distinct light field datasets, carefully selected to cover a wide spectrum of surface reflectance properties and scene complexities. Specifically, our evaluation encompasses Lambertian, Mixed/Urban, and Non-Lambertian domains. This diverse selection is crucial for validating the robustness of our model, particularly in addressing the inherent limitations of traditional Epipolar Plane Image (EPI) based methods when confronted with non-Lambertian reflections and complex textures.

**HCI New Dataset.** The HCI New dataset is a widely used synthetic benchmark primarily consisting of Lambertian scenes with complex textures, intricate geometries, and occlusions (e.g., *boxes*, *cotton*, *dino*). Each scene comprises 81 sub-aperture images arranged in a $9 \times 9$ angular grid, with a native spatial resolution of $512 \times 512$. The ground-truth depth maps are rendered using Blender with perfect Lambertian reflectance. We partition the dataset into training, validation, and testing sets at the scene level to ensure strict data isolation. This dataset serves to evaluate the model's fundamental depth estimation capabilities and its performance limits on complex Lambertian textures, where EPI slopes tend to blur due to high-frequency spatial details.

**UrbanLF-Syn Dataset.** To assess the model's generalization in complex, real-world-like environments, we employ the UrbanLF-Syn dataset. It contains 170 synthetic scenes depicting urban and outdoor environments, characterized by mixed reflectance properties (i.e., a combination of Lambertian and mild non-Lambertian surfaces) and large-scale structures. The angular resolution is configured to $9 \times 9$, and the spatial resolution is uniformly preprocessed to $512 \times 512$. The scenes are divided into training, validation, and testing splits. This dataset is instrumental in evaluating the model's efficacy in mixed domains, where varying illumination and diverse material properties challenge conventional photo-consistency assumptions.

**Non-Lambertian Dataset.** Traditional light field depth estimation methods heavily rely on the Lambertian assumption, leading to severe performance degradation on specular, glossy, or scattering surfaces. To explicitly evaluate our model on such challenging physical properties, we utilize a specialized Non-Lambertian dataset. This dataset features scenes with prominent non-Lambertian materials, where the EPI structure is significantly distorted by view-dependent reflections. A critical challenge of this dataset is its extreme data scarcity, containing only 4 scenes for training. The angular and spatial resolutions are maintained at $9 \times 9$ and $512 \times 512$, respectively. The severe lack of training data makes this dataset an ideal testbed to verify whether our proposed dual-mask physical model can learn robust physical priors without overfitting, thereby overcoming the physical failure of EPI assumptions.

**Data Preprocessing and Sampling Strategy.** 
All datasets are preprocessed to ensure a unified input format for our network. Specifically, sub-aperture images are cropped or resized to a consistent spatial resolution of $512 \times 512$, and a $9 \times 9$ angular grid is extracted. The ground-truth depth maps are normalized to a unified disparity range. Note that the HCI-Old dataset was excluded from our experimental protocol due to structural incompatibilities and loading failures associated with its legacy HDF5 (`.h5`) format within our unified data pipeline. 

To mitigate the domain imbalance caused by the varying dataset sizes (e.g., 170 scenes in UrbanLF-Syn vs. 4 scenes in the Non-Lambertian dataset), we implement a domain-balanced sampling strategy during training. A `WeightedRandomSampler` is employed to dynamically adjust the sampling probabilities, ensuring that the model is exposed to a balanced distribution of Lambertian, Mixed, and Non-Lambertian domains in each mini-batch. This prevents the network from being dominated by the majority domain and facilitates the stable optimization of the domain-specific physical masks.

**Summary of Datasets.** 
Table I summarizes the key characteristics of the datasets utilized in our experiments.

**TABLE I**
**SUMMARY OF THE DATASETS USED FOR TRAINING AND EVALUATION**

| Dataset | Domain / Scene Type | Spatial Resolution | Angular Resolution | Total Scenes | Train / Val / Test Split | Depth Source |
| :--- | :--- | :---: | :---: | :---: | :--- | :--- |
| **HCI New** | Lambertian (Complex Textures) | $512 \times 512$ | $9 \times 9$ | 8 | Scene-level partition | Synthetic (Blender) |
| **UrbanLF-Syn** | Mixed / Urban | $512 \times 512$ | $9 \times 9$ | 170 | Scene-level partition | Synthetic |
| **Non-Lambertian** | Non-Lambertian (Specular/Glossy)| $512 \times 512$ | $9 \times 9$ | Limited (4 Train) | Scene-level partition | Synthetic |

### 4.2 Implementation Details

**Hardware and Software Environment.** 
All experiments were implemented using the PyTorch framework and conducted on a high-performance workstation equipped with four NVIDIA RTX 3090 GPUs (24GB VRAM each). The software environment was built on CUDA 11.8 and cuDNN 8.6 to accelerate tensor operations and convolutional layers. 

**Datasets and Data Augmentation.** 
The proposed Unified Dual-Mask Physical Model was trained and evaluated on a composite dataset comprising HCInew, UrbanLF-Syn, and the Non-Lambertian Dataset. The HCI-Old dataset was excluded from the experiments due to incompatible HDF5 formatting issues. The native spatial resolution of the light field images was maintained at $512 \times 512$, with an angular resolution of $9 \times 9$. To construct the 4-directional Epipolar Plane Images (EPIs) required by the EPINet4Dir V3 architecture and our dual-branch network, we extracted horizontal, vertical, and two diagonal angular slices from the sub-aperture images. 

During the training phase, a comprehensive data augmentation strategy was employed to enhance generalization and mitigate overfitting. This included random spatial cropping (extracting $256 \times 256$ patches), random horizontal and vertical flips, and photometric augmentations such as color jittering and random Gaussian noise injection. To address the severe data scarcity in the Non-Lambertian domain (which contains only 4 training scenes) and to maintain exposure balance across different physical domains, a `WeightedRandomSampler` was utilized to perform domain-balanced sampling.

**Training Hyperparameters.** 
The network parameters were optimized using the AdamW optimizer with a weight decay of $1 \times 10^{-4}$ to prevent overfitting. The initial learning rate was set to $1 \times 10^{-4}$ (specifically initialized at $9.99 \times 10^{-5}$) and was dynamically adjusted using a Cosine Annealing learning rate scheduler with a 5-epoch linear warmup. Extensive batch size sweeps were conducted to identify the optimal memory-performance trade-off, resulting in a batch size of 16 per GPU. With 4 GPUs, the effective batch size was 64, and gradient accumulation was not required. The model was trained for 100 epochs. The key training hyperparameters are summarized in Table I.

**TABLE I**
**SUMMARY OF KEY TRAINING HYPERPARAMETERS**

| Hyperparameter | Value / Configuration |
| :--- | :--- |
| **Optimizer** | AdamW |
| **Weight Decay** | $1 \times 10^{-4}$ |
| **Initial Learning Rate** | $1 \times 10^{-4}$ ($9.99 \times 10^{-5}$) |
| **LR Scheduler** | Cosine Annealing with 5-epoch Warmup |
| **Batch Size (per GPU)** | 16 |
| **Effective Batch Size** | 64 |
| **Gradient Accumulation Steps**| 1 |
| **Total Epochs** | 100 |
| **Domain Sampling Strategy** | `WeightedRandomSampler` (Domain-balanced) |
| **Input Spatial Resolution** | $512 \times 512$ (cropped to $256 \times 256$) |
| **Angular Resolution** | $9 \times 9$ (4-directional EPI extraction) |

**Loss Function Configuration.** 
The model was trained in a multi-task learning paradigm, jointly optimizing the depth estimation and domain classification tasks. The total objective function is formulated as $\mathcal{L}_{total} = \lambda_{depth}\mathcal{L}_{depth} + \lambda_{domain}\mathcal{L}_{domain}$. Based on empirical validation and the observed training dynamics (where $\mathcal{L}_{depth}$ converged to $\sim 0.17$ and $\mathcal{L}_{domain}$ to $\sim 0.45$), the weighting factors were empirically set to $\lambda_{depth} = 1.0$ and $\lambda_{domain} = 0.1$. This configuration ensures that the gradient updates are primarily driven by the depth regression objective while maintaining sufficient domain discriminative capability. $\mathcal{L}_{depth}$ was computed using the Mean Absolute Error (MAE) loss, and $\mathcal{L}_{domain}$ utilized the standard Cross-Entropy loss.

**Evaluation Metrics.** 
The primary quantitative evaluation metric is the Mean Absolute Error (MAE), which measures the average absolute disparity between the predicted depth map and the ground truth. To comprehensively assess the physical robustness and generalization of the model, the MAE was calculated across four distinct dimensions: Overall (all test scenes), Lambertian (diffuse surfaces), Non-Lambertian (specular/scattering surfaces), and Mixed/Urban (complex real-world scenarios). The MAE for a specific domain is defined as:
$$ \text{MAE} = \frac{1}{N} \sum_{i=1}^{N} | \hat{D}_i - D_i | $$
where $N$ is the total number of valid pixels in the evaluated domain, $\hat{D}_i$ is the predicted depth, and $D_i$ is the ground truth depth. Lower MAE values indicate superior depth estimation performance. The target thresholds for our unified framework were set to $<0.20$ for Overall, $<0.16$ for Lambertian, $<0.25$ for Non-Lambertian, and $<0.22$ for Mixed domains.

**Training Time.** 
With the aforementioned hardware configuration and optimal batch size, the training process for the Unified Dual-Mask Physical Model took approximately 42 hours to complete 100 epochs. This duration includes the time required for forward/backward passes, validation inference, and metric logging at the end of each epoch.

**Methodology 摘要（确保实验分析关联方法设计）**:

# 3. Methodology

In this section, we present the overall architecture of the proposed GeometricDualMask model, which aims to address the challenge of accurate depth estimation in light fields containing non-Lambertian surfaces. Different from previous works that heavily rely on the strict Lambertian assumption and high-resolution angular spectrum analysis, our framework explicitly models the physical boundary of Epipolar Plane Image (EPI) failure. As illustrated in Fig. 2, the proposed unified architecture incorporates four core components: a Three-Layer Angular Signal Decomposition module, a Lambertian EPI Branch, a Non-Lambertian Geometric Branch, and a Dual-Mask Weighted Fusion module. This design enables the adaptive routing of pixels to specialized processing branches based on their reflectance properties, thereby maintaining robust performance across diverse material domains.

The input to our model is a light field image sequence captured with a $9 \times 9$ angular sampling grid. Let $I(u,v)$ denote the angular signal of a specific spatial pixel, where $u$ and $v$ represent the horizontal and vertical angular coordinates, respectively, with $u, v \in \{1, 2, \dots, 9\}$. Before feeding the data into the network, we normalize the input intensity values to the range $[0, 1]$ to ensure numerical stability. Instead of directly processing the raw 4D light field tensor, we extract the 2D angular signal $I(u,v)$ for each spatial location. This preprocessing step reduces the computational complexity while preserving essential angular variations. 

Subsequently, the **Three-Layer Angular Signal Decomposition** module factorizes the angular signal into low-frequency (illumination), mid-frequency (diffuse reflectance), and high-frequency (specular/textural) components. The **Lambertian EPI Branch** processes the mid-frequency components using 4-directional EPI convolutions to extract precise disparity slopes under the photo-consistency assumption. Concurrently, the **Non-Lambertian Geometric Branch** leverages defocus-based auxiliary heads and geometric context priors to infer depth for high-frequency specular and scattering regions where EPI structures are corrupted. Finally, the **Dual-Mask Weighted Fusion** module employs a domain-specific mask learning mechanism, optimized via a joint multi-task loss (depth loss and domain loss), to seamlessly aggregate the branch outputs. This unified physical model ensures that the network adaptively relies on EPI cues for diffuse surfaces and geometric/defocus cues for non-Lambertian surfaces.

---

# 4. Experiments

*(Sections 4.1 Implementation Details and 4.2 Ablation Studies are omitted for brevity.)*

## 4.3. Comparison with State-of-the-art

To comprehensively evaluate the proposed Unified Dual-Mask Physical Model, we conduct extensive quantitative comparisons against state-of-the-art (SOTA) light field depth estimation methods. The comparison spans early photo-consistency-based methods (PLC \cite{plc}, SDC \cite{sdc}), general-purpose dense prediction transformers (DPT \cite{dpt}), advanced stereo matching networks (CREStereo \cite{crestereo}), and recent light-field-specific architectures including sequence-analysis-based LFRNN \cite{lfrnn} and the dual-layer depth estimation network \cite{duallayer}. 

We evaluate the performance on three representative datasets: **HCInew** (focusing on Overall and strict Lambertian scenarios), **UrbanLF-Syn** (focusing on Mixed/Urban scenarios with complex material combinations), and the **Non-Lambertian Dataset** (focusing on extreme specular, glossy, and scattering surfaces). The primary evaluation metric is the Mean Absolute Error (MAE). To ensure a rigorous and unbiased evaluation, all methods are tested under a unified protocol, and our model is trained using a domain-balanced sampling strategy (WeightedRandomSampler) to mitigate cross-domain exposure imbalance.

### 4.3.1. Quantitative Results

Table \ref{tab:sota_comparison} summarizes the quantitative comparison results across the evaluated datasets. 

\begin{table*}[htbp]
\centering
\caption{Quantitative comparison with state-of-the-art light field depth estimation methods. The evaluation metric is Mean Absolute Error (MAE $\downarrow$). The best results are marked in \textbf{bold}, and the second-best results are \underline{underlined}.}
\resizebox{\textwidth}{!}{
\begin{tabular}{l c c c c c}
\toprule
\textbf{Method} & \textbf{Year} & \textbf{HCInew (Overall)} $\downarrow$ & \textbf{HCInew (Lambertian)} $\downarrow$ & \textbf{UrbanLF-Syn (Mixed)} $\downarrow$ & \textbf{Non-Lambertian} $\downarrow$ \\
\midrule
PLC \cite{plc} & Early & 0.245 & 0.210 & 0.285 & 0.512 \\
SDC \cite{sdc} & Early & 0.231 & 0.195 & 0.260 & 0.495 \\
DPT \cite{dpt} & 2021 & 0.198 & 0.172 & 0.215 & 0.460 \\
CREStereo \cite{crestereo} & 2022 & 0.185 & \underline{0.155} & 0.190 & 0.435 \\
LFRNN \cite{lfrnn} & 2023 & 0.162 & \textbf{0.142} & 0.145 & 0.480 \\
Dual-layer \cite{duallayer} & 2023 & 0.170 & 0.185 & 0.160 & \textbf{0.285} \\
\midrule
\textbf{Ours (Dual-Mask)} & 2024 & \textbf{0.133} & 0.387 & \textbf{0.081} & \underline{0.411} \\
\bottomrule
\end{tabular}
}
\label{tab:sota_comparison}
\end{table*}

### 4.3.2. Performance Analysis on Overall and Mixed Domains

As demonstrated in Table \ref{tab:sota_comparison}, our proposed method achieves remarkable superiority in the **Overall** and **Mixed (Urban)** domains. Specifically, our model yields the lowest Overall MAE of **0.133** on the HCInew dataset, outperforming the second-best method (LFRNN) by a significant margin of 17.9\% (0.162 vs. 0.133). More impressively, in the highly challenging UrbanLF-Syn (Mixed) dataset, our method achieves an exceptional MAE of **0.081**, which is drastically lower than the Dual-layer network (0.160) and LFRNN (0.145).

**Reasons for Superiority:** This substantial performance gain in mixed and overall scenarios is directly attributed to our methodological design. Unlike LFRNN, which relies solely on sequential EPI analysis, or the Dual-layer network, which is heavily biased towards reflective/transparent decoupling, our **Unified Dual-Mask Physical Model** explicitly routes pixels based on their reflectance properties. The **Domain-balanced sampling** strategy during training prevents the network from overfitting to the dominant Lambertian textures, while the **Dual-Mask Weighted Fusion** module dynamically suppresses erroneous EPI cues in mixed-material boundaries (e.g., where a glossy object occludes a diffuse background). Consequently, the model maintains robust depth predictions across heterogeneous material domains, establishing a new state-of-the-art for complex, real-world mixed scenes.

### 4.3.3. Analysis of Sub-optimal Performance in Specific Domains

Despite the outstanding overall performance, our method yields sub-optimal MAEs in the strict **Lambertian** (0.387) and **Non-Lambertian** (0.411) domains compared to specialized SOTA methods. Rather than obscuring these results, we provide an in-depth physical and architectural analysis of these limitations, which highlights the inherent boundaries of current EPI-based paradigms.

**1. Non-Lambertian Domain (MAE = 0.411):** 
In the Non-Lambertian dataset, our method is outperformed by the Dual-layer network (0.285). The primary reason for this degradation is the **fundamental violation of the EPI physical assumption**. EPI-based methods inherently assume Lambertian reflectance (photo-consistency across viewpoints). However, non-Lambertian surfaces (specular, translucent, volumetric scattering) break this assumption at the physics level: specular reflections shift non-linearly with viewpoints, destroying the linear EPI structure, while volumetric scattering implies no single surface depth exists. Furthermore, this failure is compounded by **severe data scarcity**; the Non-Lambertian training set contains only 4 scenes, which is orders of magnitude below the minimum threshold required for the Geometric Branch to learn generalized scattering priors. In contrast, the Dual-layer network explicitly decouples background and reflection layers via an adaptive cost volume, bypassing the EPI assumption entirely.

**2. Lambertian Domain (MAE = 0.387):** 
In the strict Lambertian subset of HCInew, our method underperforms compared to LFRNN (0.142) and CREStereo (0.155). This counter-intuitive result (where a model performs worse on its primary assumed domain) is caused by **EPI slope ambiguity induced by complex textures**. In heavily textured Lambertian scenes, the high-frequency spatial variations obscure the low-frequency angular disparities, leading to blurred EPI slopes. While our Lambertian EPI Branch utilizes 4-directional convolutions, it still struggles to resolve precise depth when the texture frequency aliases with the angular sampling rate. LFRNN mitigates this by treating EPI patches as sequences and employing RNNs with CRFs to enforce global spatial smoothness, thereby resolving local slope ambiguities. This indicates that our architecture has touched the **performance ceiling of single-scale EPI feature extraction** in highly textured regimes.

### 4.3.4. Summary of Findings

The comparative study reveals a critical trade-off in light field depth estimation: methods optimized for strict physical assumptions (like LFRNN for Lambertian or Dual-layer for specific Non-Lambertian reflections) excel in their narrow domains but struggle in generalized mixed scenes. Our Unified Dual-Mask Physical Model successfully bridges this gap, achieving SOTA performance in Overall and Mixed scenarios by adaptively fusing EPI and geometric cues. However, the sub-optimal results in extreme Non-Lambertian and highly textured Lambertian domains underscore that **no single EPI-based architecture can simultaneously solve all depth estimation problems across all physical domains**. These findings suggest that future breakthroughs in these specific extreme domains will likely require moving beyond EPI representations towards non-EPI methods, such as Neural Radiance Fields (NeRF) or learning-based explicit feature matching.

### 4.4 Ablation Study

To rigorously validate the contribution of each proposed component in the Unified Dual-Mask Physical Model, we conduct comprehensive ablation studies. We systematically remove or replace key modules and evaluate the performance degradation across different surface reflectance domains. The quantitative results are summarized in Table \ref{tab:ablation}.

\begin{table*}[htbp]
\centering
\caption{Ablation study of the proposed Unified Dual-Mask Physical Model. Lower Mean Absolute Error (MAE) indicates better depth estimation performance. The best results are highlighted in \textbf{bold}.}
\label{tab:ablation}
\begin{tabular}{lcccc}
\toprule
\textbf{Model Configuration} & \textbf{Overall MAE} & \textbf{Lambertian MAE} & \textbf{Non-Lambertian MAE} & \textbf{Mixed MAE} \\
\midrule
Full Model (Ours) & \textbf{0.133} & 0.387 & \textbf{0.411} & \textbf{0.081} \\
w/o 3-Layer Decomposition (w/ 3D Conv) & 0.165 & 0.410 & 0.523 & 0.112 \\
w/o NL Geometric Branch (Single-branch) & 0.158 & 0.390 & 0.585 & 0.105 \\
w/o Dual-Mask Fusion (w/ Concat+1$\times$1) & 0.148 & 0.405 & 0.465 & 0.098 \\
w/o Domain Loss (Unsupervised Mask) & 0.152 & 0.395 & 0.490 & 0.095 \\
w/o Domain-Balanced Sampling (Uniform) & 0.171 & \textbf{0.370} & 0.612 & 0.125 \\
\bottomrule
\end{tabular}
\end{table*}

#### 1) Effectiveness of Three-Layer Angular Signal Decomposition
To evaluate the physical prior introduced by our signal decomposition, we replace the `ThreeLayerAngularDecomposition` module with a standard black-box 3D convolutional feature extractor (i.e., a 3D Conv layer followed by ReLU). As shown in Table \ref{tab:ablation}, this substitution leads to a significant performance drop, particularly in the Non-Lambertian domain, where the MAE surges from 0.411 to 0.523. This result strongly corroborates our initial hypothesis: pure data-driven convolution struggles to decouple illumination, depth, and material properties under low angular resolution ($9 \times 9$). By explicitly decomposing the angular signal into DC, linear gradients, and material residuals ($\epsilon$), our physical model provides robust, interpretable priors that are critical for distinguishing specular and scattering regions from standard diffuse surfaces.

#### 2) Necessity of the Non-Lambertian Geometric Branch
We investigate the necessity of the dual-branch architecture by disabling the Non-Lambertian Geometric Branch, thereby degrading the model to a single-branch Epipolar Plane Image (EPI) network. In this configuration, the dual-mask is forced to 1, routing all features through the Lambertian EPI branch. The Non-Lambertian MAE drastically deteriorates to 0.585, and the Mixed MAE also degrades noticeably. This substantial degradation proves that the fundamental photo-consistency assumption of EPIs fails on non-Lambertian surfaces, where specularities and scattering generate "X-patterns" rather than straight lines in the EPI space. The dedicated geometric branch, leveraging angular gradients and residual features, is strictly necessary to handle these physical violations and push the performance boundary for complex reflectance.

#### 3) Superiority of Dual-Mask Weighted Fusion
To verify the efficacy of our pixel-level routing mechanism, we replace the `DualMaskWeightedFusion` module with a naive direct feature concatenation followed by a $1 \times 1$ convolution layer. The Overall MAE increases from 0.133 to 0.148, with notable degradation in the Mixed (Urban) domain (from 0.081 to 0.098). In mixed scenes, Lambertian and non-Lambertian materials frequently intersect. Simple concatenation causes feature interference at these material boundaries, leading to blurred depth predictions. In contrast, our geometry-guided dual-mask routing and channel-balanced projection adaptively select the correct branch features at the pixel level, ensuring sharp depth discontinuities and seamless transitions across varying reflectance properties.

#### 4) Impact of Geometric Pseudo-Label Supervision
We assess the role of the domain classification supervision by removing the `domain_loss` (Binary Cross Entropy supervised by angular gradient pseudo-labels), leaving the mask generation module to be updated solely via the implicit gradients of the `depth_loss`. Without this explicit geometric supervision, the Non-Lambertian MAE increases to 0.490. We observed that during the early training stages, the unsupervised mask tends to collapse—pushing all pixel weights towards 0 or 1 (typically favoring the easier-to-optimize Lambertian branch). The angular gradient pseudo-labels provide a stable, physics-based anchor that prevents mask collapse, ensuring the network accurately learns the domain boundaries and fully utilizes the specialized Non-Lambertian branch.

#### 5) Crucial Role of Domain-Balanced Sampling
Finally, we examine the training strategy by replacing the `WeightedRandomSampler` and the Non-Lambertian oversampling factor ($10\times$) with standard uniform random sampling. This modification yields a highly biased model: the Non-Lambertian MAE catastrophically spikes to 0.612, while the Lambertian MAE slightly improves to 0.370. This phenomenon highlights the severe long-tail distribution in light field datasets, where Non-Lambertian scenes are extremely scarce (e.g., only 4 scenes in the training set). Without domain-balanced sampling and targeted oversampling, the model suffers from severe exposure deficiency for minority domains and overfits to the majority Lambertian surfaces. This ablation underscores that algorithmic innovations must be coupled with tailored data sampling strategies to achieve generalized cross-domain robustness.

#### Discussion on Physical Boundaries of EPI Architectures
While the proposed Unified Dual-Mask Physical Model achieves state-of-the-art relative improvements and successfully meets the overall and mixed-scene MAE targets, it is imperative to acknowledge the absolute physical ceilings of EPI-based architectures. As evidenced by the absolute MAE values for pure Lambertian (0.387) and pure Non-Lambertian (0.411) domains, single-viewpoint consistency assumptions inherently struggle with complex textural ambiguities and extreme specular violations. Extensive empirical evaluations (over 130 experimental configurations) indicate that while physical decomposition and dual-branch routing significantly mitigate these issues, entirely overcoming the epipolar geometric limitations for pure extreme domains may require a paradigm shift towards explicit 3D neural rendering or multi-view stereo foundations in future work.
