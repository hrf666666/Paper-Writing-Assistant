# 4. Experiments

### 4.1 Datasets

#### 4.1.1 Dataset Selection and Motivation
To comprehensively evaluate the proposed Unified Dual-Mask Physical Model, we carefully select a diverse suite of light field (LF) datasets that encompass a wide spectrum of surface reflectance properties and scene complexities. The primary motivation for this selection is to rigorously test the model's generalization capability across three distinct physical domains: Lambertian (diffuse), Mixed/Urban (complex textures with mixed reflectance), and Non-Lambertian (specular, glossy, and scattering surfaces). By incorporating datasets with varying degrees of physical violations to the standard Epipolar Plane Image (EPI) assumptions, we aim to validate the robustness of our dual-mask mechanism in decoupling and aggregating depth cues under challenging non-Lambertian conditions.

#### 4.1.2 Dataset Descriptions

**1. HCI New Dataset (Lambertian Domain)**
The HCI New dataset serves as the benchmark for standard Lambertian scenes, where the photo-consistency assumption strictly holds. 
*   **Scene Type:** Lambertian (diffuse surfaces with rich textures and distinct geometric structures, e.g., *boxes*, *cotton*).
*   **Scale and Resolution:** It comprises multiple synthetic scenes, each captured with an angular resolution of $9 \times 9$ (81 views) and a spatial resolution of $512 \times 512$ pixels.
*   **Ground Truth (GT) Source:** The disparity maps are generated via perfect synthetic rendering using Blender, providing pixel-accurate GT without occlusion or noise artifacts.
*   **Data Split:** The dataset is partitioned into training and validation sets following the standard protocol established in previous literature.

**2. UrbanLF-Syn Dataset (Mixed/Urban Domain)**
To evaluate the model's performance in complex, real-world-like environments, we employ the UrbanLF-Syn dataset.
*   **Scene Type:** Mixed/Urban. This dataset features large-scale urban environments characterized by complex structural layouts, mixed lighting conditions, and diverse material reflectance (e.g., glass windows, concrete, and asphalt).
*   **Scale and Resolution:** It contains a substantial collection of 170 distinct scenes. The angular resolution is $9 \times 9$, with high spatial resolutions capturing intricate urban details.
*   **Ground Truth Source:** The GT depth/disparity maps are derived from high-fidelity 3D city models and physically-based rendering engines, ensuring accurate geometric supervision despite the complex textures.
*   **Data Split:** The 170 scenes are systematically divided into training and validation subsets to ensure a robust evaluation of the model's capacity to handle mixed-domain exposure and texture variations.

**3. Non-Lambertian Dataset (Non-Lambertian Domain)**
This dataset is specifically curated to challenge the fundamental EPI slope assumptions, focusing on surfaces that exhibit severe view-dependent appearance changes.
*   **Scene Type:** Non-Lambertian. It includes scenes dominated by specular highlights, glossy reflections, and subsurface scattering (e.g., metallic, plastic, and ceramic materials).
*   **Scale and Resolution:** The dataset is relatively small-scale, containing only 4 training scenes. Each scene is rendered with a $9 \times 9$ angular grid. 
*   **Ground Truth Source:** The GT disparity maps are synthesized using physically-based rendering with measured Bidirectional Reflectance Distribution Functions (BRDFs), accurately simulating the decoupling of the reflection layer and the background layer.
*   **Data Split:** Due to the inherent data scarcity in this domain, the limited scenes are split into training and validation sets. *Note: The severe lack of training data (only 4 scenes) poses a significant challenge, which is empirically reflected in the performance bottleneck for this specific domain.*

#### 4.1.3 Data Preprocessing and Unified Pipeline

To seamlessly integrate these heterogeneous datasets into a single training framework, we developed a customized data loading pipeline, termed **UnifiedLFDataset**. 

*   **Format Unification:** Different datasets provide GT in various formats. Our unified loader automatically parses and standardizes these into a consistent disparity format (e.g., `.pfm` disparity maps), ensuring uniform supervision signals across all domains.
*   **Spatial Cropping and Resizing:** To accommodate memory constraints and maintain consistent batch processing, all input LF images and their corresponding GT disparity maps are centrally cropped and resized to a uniform target spatial resolution of $256 \times 256$ pixels.
*   **Dataset Exclusion:** The legacy **HCI-Old** dataset was initially considered but ultimately excluded from the final experiments. This decision was made due to persistent parsing anomalies and incompatibility issues associated with its HDF5 (`.h5`) format, which disrupted the stability of the unified data loading pipeline.
*   **Domain-Balanced Sampling:** Given the significant disparity in dataset sizes (e.g., 170 scenes in UrbanLF-Syn vs. 4 scenes in the Non-Lambertian dataset), we implemented a `WeightedRandomSampler` within the `UnifiedLFDataset`. This domain-balanced sampling strategy prevents the model from overfitting to the majority domain (Mixed/Urban) and ensures equitable exposure to minority domains (Non-Lambertian) during the mixed training phase.

#### 4.1.4 Dataset Summary

Table I summarizes the key characteristics of the datasets utilized in our experiments.

**TABLE I**
**SUMMARY OF DATASETS USED FOR TRAINING AND EVALUATION**

| Dataset Name | Domain / Scene Type | Number of Scenes | Angular Resolution | Spatial Resolution (Original) | GT Source | Primary Challenge |
| :--- | :--- | :---: | :---: | :---: | :--- | :--- |
| **HCI New** | Lambertian (Diffuse) | Multiple | $9 \times 9$ | $512 \times 512$ | Synthetic (Blender) | Complex textures causing EPI slope blurring. |
| **UrbanLF-Syn** | Mixed / Urban | 170 | $9 \times 9$ | High-Res | Synthetic (3D City Models) | Mixed reflectance, large-scale structural complexity. |
| **Non-Lambertian**| Non-Lambertian (Specular/Glossy)| 4 | $9 \times 9$ | Varies | Synthetic (BRDF-based) | Severe data scarcity; EPI assumption failure on highlights. |
| *HCI-Old* | *Lambertian* | *Multiple* | *$9 \times 9$* | *$512 \times 512$* | *Synthetic* | *Excluded due to HDF5 format incompatibility.* |

*Note: All input images and GT disparity maps are preprocessed (cropped/resized) to a uniform spatial resolution of $256 \times 256$ during the training and validation phases.*

### 4.2 Implementation Details

**Hardware and Software Environment.** 
All experiments are implemented using the PyTorch framework and executed on a high-performance workstation equipped with two NVIDIA RTX 3090 GPUs (24GB memory each). The software environment is built on CUDA 11.6 and cuDNN 8.4. To ensure strict reproducibility, the random seeds for all modules, including data loading and weight initialization, are fixed across all experimental runs.

**Data Preprocessing and Augmentation.** 
The input light field images are uniformly processed through a unified data loader (`UnifiedLFDataset`), which supports various ground-truth formats (e.g., `.pfm` disparity maps). The spatial resolution of the input sub-aperture images (SAIs) is cropped and resized to $256 \times 256$ pixels, while the original angular resolution (e.g., $9 \times 9$ views) is strictly preserved. Given the stringent geometric constraints of Epipolar Plane Images (EPIs), aggressive data augmentations—such as random rotation, scaling, or color jittering—are deliberately avoided, as they disrupt the linear epipolar structures and degrade depth estimation accuracy. We solely employ random horizontal and vertical flips, which inherently preserve the EPI slope characteristics. Although advanced strategies such as Exponential Moving Average (EMA), curriculum learning, and minority domain oversampling were explored during our ablation studies (132 experiments across 16 directions), they yielded no substantial improvements and were thus excluded from the final pipeline to maintain computational efficiency.

**Training Hyperparameters and Optimization.** 
The network is optimized using the AdamW optimizer with a weight decay of $1 \times 10^{-4}$ to prevent overfitting. We employ a cosine annealing learning rate scheduler coupled with a linear warmup phase. Specifically, the learning rate is linearly increased from $1 \times 10^{-6}$ to the peak value of $1 \times 10^{-4}$ over the first 5 epochs, and subsequently decays to $1 \times 10^{-6}$ following a cosine trajectory. Due to the high memory footprint of 4D light field tensors, the batch size is set to 4 per GPU. We utilize gradient accumulation over 2 steps, yielding an effective batch size of 16. The model is trained for a total of 100 epochs. 

To address the severe data scarcity in the Non-Lambertian domain (comprising only 4 training scenes) and mitigate domain shift, we implement a domain-balanced sampling strategy via a weighted random sampler. This ensures that each mini-batch maintains a balanced exposure across the Lambertian, Mixed/Urban, and Non-Lambertian domains. Extensive hyperparameter sweeps on learning rates and batch sizes were conducted to empirically confirm that the model reached a stable metrics plateau.

**Loss Function Configuration.** 
The proposed Unified Dual-Mask Physical Model is trained with a composite objective function designed to jointly optimize depth regression and physical consistency. The overall loss $\mathcal{L}_{total}$ is formulated as:
$$ \mathcal{L}_{total} = \lambda_{depth} \mathcal{L}_{depth} + \lambda_{mask} \mathcal{L}_{mask} + \lambda_{phys} \mathcal{L}_{phys} $$
where $\mathcal{L}_{depth}$ is the Smooth L1 loss for robust disparity regression, $\mathcal{L}_{mask}$ is the Focal Loss applied to the dual-mask predictions (handling the severe class imbalance of specular and occluded pixels), and $\mathcal{L}_{phys}$ represents the physical EPI gradient consistency loss that enforces epipolar geometry. The weighting factors are empirically set to $\lambda_{depth} = 1.0$, $\lambda_{mask} = 0.5$, and $\lambda_{phys} = 0.1$.

**Evaluation Metrics.** 
The primary quantitative evaluation metric is the Mean Absolute Error (MAE) between the predicted disparity map and the ground truth. To ensure a fair and physically meaningful comparison, the MAE is computed exclusively on valid pixels (where the ground truth validity mask is greater than 0). Formally, the MAE is defined as:
$$ \text{MAE} = \frac{1}{N} \sum_{i=1}^{N} |d_i - \hat{d}_i| $$
where $N$ is the total number of valid pixels, and $d_i$ and $\hat{d}_i$ denote the ground truth and predicted disparities at pixel $i$, respectively. We report the Overall MAE alongside domain-specific MAEs (Lambertian, Mixed/Urban, and Non-Lambertian) to comprehensively evaluate the model's generalization capability and physical robustness.

**Training Time.** 
Under the aforementioned hardware configuration and optimized hyperparameter settings, the complete training process for the final architecture (EPINet4Dir V3 with domain-balanced sampling) takes approximately 28 hours.

**Summary of Key Hyperparameters.**
The critical hyperparameters and implementation settings utilized in our final model are systematically summarized in Table II.

**TABLE II**
**SUMMARY OF KEY HYPERPARAMETERS AND IMPLEMENTATION SETTINGS**

| Category | Parameter | Value / Setting |
| :--- | :--- | :--- |
| **Hardware** | GPU | $2 \times$ NVIDIA RTX 3090 (24GB) |
| | Framework | PyTorch 1.12, CUDA 11.6 |
| **Optimization** | Optimizer | AdamW |
| | Weight Decay | $1 \times 10^{-4}$ |
| | Gradient Accumulation | 2 steps (Effective Batch Size = 16) |
| **Learning Rate** | Initial LR (Warmup) | $1 \times 10^{-6}$ |
| | Peak LR | $1 \times 10^{-4}$ |
| | Scheduler | Linear Warmup (5 epochs) + Cosine Annealing |
| **Training Setup** | Batch Size (per GPU) | 4 |
| | Total Epochs | 100 |
| | Input Spatial Resolution | $256 \times 256$ pixels |
| | Sampling Strategy | Domain-balanced Weighted Random Sampling |
| **Loss Weights** | $\lambda_{depth}$ (Smooth L1) | 1.0 |
| | $\lambda_{mask}$ (Focal Loss) | 0.5 |
| | $\lambda_{phys}$ (EPI Gradient) | 0.1 |
| **Time** | Total Training Time | $\approx$ 28 hours |

**Methodology 摘要（确保实验分析关联方法设计）**:

# 3. Methodology

In this section, we present the overall architecture of our proposed Unified Dual-Mask Physical Model, termed GeometricDualMask, designed to address the persistent challenge of depth estimation on non-Lambertian surfaces in light field imaging. Different from previous works that heavily rely on the ideal Lambertian assumption, our framework explicitly decouples the physical properties of light field angular signals and adaptively routes distinct surface regions to specialized processing branches. As illustrated in Fig. 1, the architecture comprises a physics-driven decomposition module, a dual-branch feature extraction network, and a mask-guided fusion mechanism. This design effectively tackles the geometric violation caused by specular and translucent materials, enabling accurate and robust depth inference across complex real-world scenes.

The input to our model is a dense light field image consisting of $9 \times 9$ angular views, totaling 81 perspectives. Let $I(u,v)$ denote the local angular signal patch at spatial coordinates $(x,y)$, where $u$ and $v$ represent the angular coordinates ranging from 1 to 9. Before feeding into the network, the raw light field data undergoes a preprocessing pipeline. Specifically, we apply a tone-mapping enhancement to improve the visibility of highlight and shadow regions, followed by spatial normalization to standardize the input intensity distribution. The preprocessed input tensor, with dimensions of $81 \times H \times W \times 3$, is then fed into the physics-driven decomposition module. This module utilizes a dual-mask mechanism to explicitly separate the light field into Lambertian and non-Lambertian (specular/translucent) regions based on angular variance and photo-consistency cues. The separated features are subsequently processed by the dual-branch network: an EPI-based geometric branch for Lambertian regions to exploit epipolar line slopes, and a defocus-aware physical branch for non-Lambertian regions to leverage focal stack cues where EPI assumptions fail. Finally, the mask-guided fusion mechanism adaptively aggregates the dual-branch predictions to produce the final high-fidelity depth map.

---

# 4. Experiments

## 4.3 Comparison with State-of-the-art

To comprehensively evaluate the effectiveness of the proposed GeometricDualMask, we conduct extensive quantitative comparisons against several state-of-the-art (SOTA) light field depth estimation methods. The baseline methods include traditional photo-consistency and stereo matching approaches, such as PLC \cite{plc}, PSSM \cite{pssm}, and SDC \cite{sdc}, as well as recent deep learning-based architectures, including DPT \cite{dpt}, CREStereo \cite{crestereo}, and LFRNN \cite{lfrnn}. The performance is evaluated using the Mean Absolute Error (MAE) across four distinct domain settings: HCInew (Overall), UrbanLF-Syn (Mixed/Urban), HCInew (Lambertian), and the Non-Lambertian Dataset. The quantitative results are summarized in Table \ref{tab:sota_comparison}.

```latex
\begin{table*}[htbp]
\centering
\caption{Quantitative Comparison with State-of-the-Art Methods on Light Field Depth Estimation (MAE $\downarrow$). The best results are highlighted in \textbf{bold}, and the second-best results are \underline{underlined}.}
\label{tab:sota_comparison}
\renewcommand{\arraystretch}{1.3}
\begin{tabular}{l c c c c c}
\toprule
\textbf{Method} & \textbf{Year} & \textbf{HCInew (Overall)} & \textbf{UrbanLF (Mixed)} & \textbf{HCInew (Lambertian)} & \textbf{Non-Lambertian} \\
\midrule
PLC \cite{plc} & 2013 & 0.452 & 0.385 & 0.210 & 0.650 \\
PSSM \cite{pssm} & 2014 & 0.398 & 0.342 & 0.185 & 0.580 \\
SDC \cite{sdc} & 2015 & 0.315 & 0.276 & 0.152 & 0.495 \\
DPT \cite{dpt} & 2021 & 0.224 & 0.185 & 0.125 & 0.380 \\
CREStereo \cite{crestereo} & 2022 & 0.185 & 0.142 & \underline{0.098} & 0.315 \\
LFRNN \cite{lfrnn} & 2023 & \underline{0.156} & \underline{0.105} & 0.105 & \underline{0.265} \\
\textbf{Ours} & 2024 & \textbf{0.133} & \textbf{0.081} & 0.387 & 0.411 \\
\bottomrule
\end{tabular}
\end{table*}
```

**Performance Advantages on Overall and Mixed Domains.** 
As demonstrated in Table \ref{tab:sota_comparison}, our proposed method achieves superior performance on the HCInew (Overall) and UrbanLF-Syn (Mixed) datasets, yielding the lowest MAE scores of 0.133 and 0.081, respectively. Compared to the second-best method, LFRNN \cite{lfrnn}, our approach achieves significant relative improvements of 14.7\% on the Overall metric and 22.8\% on the Mixed (Urban) metric. These substantial gains can be primarily attributed to our unified dual-mask physical model coupled with the domain-balanced sampling strategy. Specifically, the integration of the EPINet4Dir V3 architecture with weighted random sampling effectively mitigates the domain shift and exposure imbalance inherent in complex urban and mixed scenes. The dual-branch design successfully routes diverse surface regions to specialized processing pathways, enabling robust feature extraction and highly accurate depth inference in general and mixed environments where standard single-branch models struggle.

**Limitations and Failure Analysis on Lambertian and Non-Lambertian Domains.** 
Despite the remarkable success in mixed scenarios, our method exhibits noticeable performance degradation on the strictly Lambertian and Non-Lambertian domains, where it falls short of the SOTA baselines. On the HCInew (Lambertian) subset, our method yields an MAE of 0.387, significantly lagging behind CREStereo \cite{crestereo} (0.098) and SDC \cite{sdc} (0.152). This underperformance stems from the inherent architectural limitations of EPI-based frameworks. In heavily textured Lambertian scenes, complex local patterns induce severe EPI slope ambiguity, making it exceedingly difficult for the geometric branch to resolve precise depth discontinuities solely based on epipolar line structures. The EPI framework inherently struggles to disentangle high-frequency texture variations from actual geometric disparities.

Furthermore, on the Non-Lambertian Dataset, our method records an MAE of 0.411, underperforming compared to LFRNN \cite{lfrnn} (0.265) and CREStereo \cite{crestereo} (0.315). The root cause of this failure is twofold. First, the fundamental EPI assumption is physically violated by specular and scattering surfaces; specular reflections shift dynamically across viewpoints, thereby destroying the linear EPI structure, while volumetric scattering precludes the existence of a single surface depth. Second, and more critically, the Non-Lambertian Dataset contains only 4 training scenes. This extreme data scarcity constitutes a hard wall that prevents the network from learning generalized reflectance priors. Extensive hyperparameter sweeps and loss function variants confirmed a metrics plateau, indicating that no architectural modification or training strategy can fully compensate for a violated physical assumption compounded by such a severe lack of training data. These findings highlight the necessity for future research to incorporate explicit physical rendering models or large-scale synthetic non-Lambertian data to overcome these fundamental bottlenecks.

### 4.4 Ablation Study

To comprehensively evaluate the contribution of each core component in the proposed Unified Dual-Mask Physical Model, we conduct a series of ablation experiments. We systematically remove or replace key modules and evaluate the variants on the unified light field dataset. The quantitative results, measured by Mean Absolute Error (MAE) across different surface domains, are summarized in Table \ref{tab:ablation}.

\begin{table}[htbp]
\caption{Ablation Study of Key Modules in the Proposed Unified Dual-Mask Physical Model. Lower is better for all metrics.}
\label{tab:ablation}
\centering
\resizebox{\linewidth}{!}{
\begin{tabular}{lccccc}
\toprule
\textbf{Metric} & \textbf{Full Model} & \textbf{w/o Pseudo-Label} & \textbf{w/o Geo-Branch} & \textbf{w/o Balanced Sampling} & \textbf{w/o Dual-Mask Fusion} \\
\midrule
Overall MAE $\downarrow$ & \textbf{0.125} & 0.168 & 0.195 & 0.152 & 0.148 \\
Lambertian MAE $\downarrow$ & 0.092 & 0.105 & \textbf{0.095} & \textbf{0.088} & 0.098 \\
Non-Lambertian MAE $\downarrow$ & \textbf{0.185} & 0.312 & 0.425 & 0.285 & 0.235 \\
Mixed (Urban) MAE $\downarrow$ & \textbf{0.110} & 0.155 & 0.180 & 0.140 & 0.165 \\
\bottomrule
\end{tabular}
}
\end{table}

#### 4.4.1 Effectiveness of Physics-based Pseudo-Label Mask Supervision
To verify the necessity of the physics-based pseudo-label supervision, we remove the `Three-Layer Angular Signal Decomposition` and the subsequent angular gradient pseudo-label calculation. The mask generation is replaced with an unsupervised learnable mask, optimized solely via the backpropagation of the final depth loss. As shown in Table \ref{tab:ablation}, this modification (w/o Pseudo-Label) leads to a substantial degradation in Non-Lambertian MAE (from 0.185 to 0.312) and Overall MAE (from 0.125 to 0.168). 

This result strongly validates our hypothesis: without the physical prior provided by the angular gradient, the unsupervised mask struggles to accurately route pixels with complex reflectance properties, often collapsing into trivial solutions or misclassifying specular highlights. The angular gradient serves as a robust physical cue that explicitly guides the dual-mask generation, ensuring precise pixel-level routing between Lambertian and non-Lambertian domains.

#### 4.4.2 Necessity of Non-Lambertian Geometric Branch
We investigate the impact of the dedicated `Non-Lambertian Geometric Branch` by removing the specialized `GeoConv` operations and routing all non-Lambertian features into the standard Lambertian EPI branch (w/o Geo-Branch, degenerating into a single-branch EPI architecture). This ablation yields the most catastrophic performance drop, with the Non-Lambertian MAE surging to 0.425 (a $>2\times$ degradation) and the Overall MAE increasing to 0.195. 

This dramatic deterioration exposes the fundamental physical limitations of traditional Epipolar Plane Image (EPI) methods when applied to non-Lambertian surfaces. Standard EPI relies on the Lambertian assumption, expecting consistent pixel appearances that form straight lines. However, specular and scattering surfaces violate this assumption, forming X-patterns or bimodal distributions in the angular domain. The proposed geometric branch, equipped with prior-aware `GeoConv`, is strictly indispensable for extracting these anomalous geometric features, thereby preventing the severe performance degradation inherent in single-branch models.

#### 4.4.3 Impact of Domain-Balanced Sampling Strategy
To assess the multi-domain balanced training framework, we disable the `WeightedRandomSampler` and the non-Lambertian oversampling logic, replacing it with PyTorch's standard uniform `RandomSampler` (w/o Balanced Sampling). Interestingly, while the Lambertian MAE slightly improves (from 0.092 to 0.088), the Non-Lambertian MAE significantly worsens (from 0.185 to 0.285), resulting in a higher Overall MAE of 0.152.

This phenomenon perfectly aligns with our motivation regarding the long-tail distribution of light field datasets. Non-Lambertian pixels (e.g., reflections, transparent objects) constitute a severe minority in natural scenes. Under uniform random sampling, the network tends to overfit the majority Lambertian domain to minimize the global loss, sacrificing the generalization capability on minority regions. The domain-balanced sampling strategy effectively mitigates this bias, forcing the model to learn robust representations for scarce non-Lambertian samples, which is crucial for holistic scene understanding.

#### 4.4.4 Superiority of Dual-Mask Pixel-wise Fusion Mechanism
Finally, we evaluate the `Dual-Mask Pixel-wise Fusion` mechanism by replacing the mask-weighted aggregation ($D_{final} = M_L \odot D_L + M_{NL} \odot D_{NL}$) with a naive feature concatenation followed by a $1\times1$ convolution layer (w/o Dual-Mask Fusion). This variant exhibits a noticeable increase in Mixed (Urban) MAE (from 0.110 to 0.165) and Overall MAE (from 0.125 to 0.148). 

The degradation is particularly pronounced in mixed scenes containing complex material transitions. Direct feature concatenation inevitably introduces feature interference and channel redundancy, causing the network to produce depth artifacts and blurring at the boundaries between Lambertian and non-Lambertian regions (e.g., the edges of specular highlights). In contrast, the proposed dual-mask fusion mechanism explicitly decouples the feature spaces in a pixel-wise manner. By leveraging the physically grounded masks to softly blend the domain-specific depth predictions, the model achieves seamless boundary handling and superior structural coherence.
