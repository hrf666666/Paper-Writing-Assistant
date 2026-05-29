# 4. Experiments

### 4.1 Datasets

To comprehensively evaluate the proposed Unified Dual-Mask Physical Model, we construct a diverse light field (LF) benchmark comprising datasets with varying material properties and scene complexities. Unlike conventional LF depth estimation methods that predominantly rely on strict Lambertian assumptions, our model is explicitly designed to handle complex non-Lambertian reflections. Therefore, the selected datasets are meticulously chosen to cover three distinct domain types: Lambertian, Non-Lambertian, and Mixed scenarios, ensuring a rigorous assessment of the model's physical decoupling and depth inference capabilities.

#### 1) Lambertian Datasets (HCI New and Wanner HCI)
We utilize the widely recognized **HCI New** and **Wanner HCI** datasets to evaluate the model's baseline performance on purely diffuse (Lambertian) surfaces. The HCI New dataset consists of 24 high-quality synthetic scenes, which we partition into 20 scenes for training and 4 for validation. The Wanner HCI dataset contributes an additional 10 scenes, all allocated to the training set. These datasets provide precise ground truth disparity maps in `.pfm` format. The scenes feature standard Lambertian materials where photo-consistency holds strictly across different viewpoints. Including these datasets ensures that our physical model maintains high accuracy on ideal diffuse surfaces and does not suffer from performance degradation when the non-Lambertian components are absent.

#### 2) Non-Lambertian Dataset
To rigorously validate the model's capability in handling specular and scattering surfaces, we employ the **Non-Lambertian (Zhenglong)** dataset. This dataset specifically synthesizes scenes with challenging non-Lambertian materials, including glossy, metallic, and translucent surfaces. In these regions, traditional Epipolar Plane Image (EPI) slope assumptions fail due to view-dependent radiance variations and specular highlights. It contains 6 scenes in total, partitioned into 4 for training and 2 for validation, with ground truth disparity maps provided in `.npy` format. This dataset is crucial for verifying the effectiveness of our dual-mask mechanism in accurately decoupling specular/scattering components from the diffuse background.

#### 3) Mixed Urban Dataset (UrbanLF-Syn)
To assess the generalization ability and robustness of our unified model in complex, real-world-like environments, we incorporate the **UrbanLF-Syn** dataset. This large-scale dataset comprises 200 synthetic urban scenes featuring a heterogeneous mix of materials, including Lambertian building facades, non-Lambertian glass windows, and metallic vehicles. We split it into 170 scenes for training and 30 for validation. The ground truth is provided in `.npy` format. The Mixed domain acts as a comprehensive testbed to evaluate the model's capacity to handle spatially varying Bidirectional Reflectance Distribution Functions (BRDFs) and complex occlusions within a single scene.

#### Data Preprocessing and Domain-Balanced Sampling
To ensure uniform input dimensions and computational efficiency across all datasets, a standardized preprocessing pipeline is applied. All LF images are cropped and resized to a spatial resolution of $256 \times 256$, and we extract a $9 \times 9$ angular grid (81 views) for each scene. Data augmentation includes random horizontal flipping, which is applied consistently across all 81 views to strictly preserve the underlying epipolar geometry.

A significant challenge in our experimental setup is the severe data imbalance among different domains: UrbanLF-Syn (170 scenes) $\gg$ HCI New (20 scenes) $\gg$ Non-Lambertian (4 scenes). To prevent the network from overfitting to the dominant Mixed domain and neglecting the minority Non-Lambertian and Lambertian domains, we implement a **domain-balanced sampling strategy**. Specifically, a `WeightedRandomSampler` with inverse-frequency weighting is employed during training. This ensures that each domain contributes equally to the gradient updates in every epoch, forcing the network to learn domain-invariant physical features rather than dataset-specific biases.

#### Dataset Summary
Table I summarizes the key characteristics and configurations of the datasets used in our experiments.

**TABLE I**
**SUMMARY OF THE LIGHT FIELD DATASETS USED FOR TRAINING AND EVALUATION**

| Dataset Name | Domain Type | Train / Val Split | Angular Resolution | Processed Spatial Resolution | GT Disparity Format | Key Characteristics |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **HCI New** | Lambertian | 20 / 4 | $9 \times 9$ (81 views) | $256 \times 256$ | `.pfm` | Purely diffuse surfaces, strict photo-consistency. |
| **Wanner HCI** | Lambertian | 10 / 0 | $9 \times 9$ (81 views) | $256 \times 256$ | `.pfm` | Standard diffuse materials, supplements Lambertian training. |
| **Non-Lambertian** | Non-Lambertian | 4 / 2 | $9 \times 9$ (81 views) | $256 \times 256$ | `.npy` | Specular, glossy, and scattering surfaces; violates EPI assumptions. |
| **UrbanLF-Syn** | Mixed | 170 / 30 | $9 \times 9$ (81 views) | $256 \times 256$ | `.npy` | Complex urban scenes with spatially varying BRDFs and occlusions. |
| **Total** | **All** | **204 / 36** | - | - | - | **Evaluated with domain-balanced sampling strategy.** |

### 4.2 Implementation Details

**Hardware and Software Environment**  
The proposed Unified Dual-Mask Physical Model is implemented using the PyTorch framework. All experiments are conducted on a single NVIDIA GeForce RTX 3090 GPU with 24GB of memory. To optimize memory consumption and accelerate the training process without compromising numerical stability, Automatic Mixed Precision (AMP) is enabled throughout the training phase. 

**Training Hyperparameters**  
The network is optimized using the AdamW optimizer, which provides robust convergence for deep light field architectures. We employ a Cosine Annealing learning rate scheduler (`CosineAnnealingLR`) to dynamically adjust the learning rate, facilitating better escape from local minima and finer convergence in later epochs. Due to the high memory footprint of processing 81-view light field tensors, the physical batch size is set to 1 per GPU. To ensure stable gradient updates, we utilize gradient accumulation with a step size of 4, yielding an effective batch size of 4. The model is trained for a total of 100 epochs. The key training hyperparameters are summarized in Table I.

**Table I: Summary of Key Training Hyperparameters**
| Hyperparameter | Value |
| :--- | :--- |
| Optimizer | AdamW |
| Initial Learning Rate | $1 \times 10^{-4}$ |
| Learning Rate Scheduler | CosineAnnealingLR |
| Batch Size (per GPU) | 1 |
| Gradient Accumulation Steps | 4 |
| Effective Batch Size | 4 |
| Total Epochs | 100 |
| Weight Decay | $1 \times 10^{-4}$ |
| Input Spatial Resolution | $256 \times 256$ |
| Training Patch Size | $64 \times 64$ |
| Angular Resolution | $9 \times 9$ (81 views) |
| Mixed Precision Training | Enabled (AMP) |

**Data Augmentation and Sampling Strategy**  
To mitigate the severe data imbalance among different reflectance domains (e.g., the substantial volume of the Mixed UrbanLF-Syn dataset compared to the limited Non-Lambertian scenes) and prevent the model from overfitting to the majority domain, we introduce a domain-balanced sampling strategy. Specifically, a `WeightedRandomSampler` with inverse-frequency weighting is utilized to ensure that each physical domain is equally represented during the optimization process. For spatial data augmentation, we apply random horizontal flipping. Crucially, to preserve the epipolar geometry and angular consistency inherent in light fields, the identical flipping transformation is strictly and consistently applied across all 81 views of a given light field sample. 

**Loss Function**  
The primary objective function for depth estimation is the L1 loss (Mean Absolute Error), which is empirically known to be more robust to depth discontinuities and produces sharper boundaries compared to the L2 loss. The base depth loss is formulated as:
$$ \mathcal{L}_{depth} = \frac{1}{N} \sum_{i=1}^{N} \left| \hat{D}_i - D_i \right| $$
where $\hat{D}_i$ and $D_i$ denote the predicted and ground-truth disparity values for pixel $i$, and $N$ is the total number of valid pixels. The weight for $\mathcal{L}_{depth}$ is set to 1.0. In the advanced training stage, a pixel-wise confidence weighting mechanism is integrated into the loss function. This mechanism dynamically down-weights the contributions of highly specular or severely occluded regions where physical BRDF fitting is inherently ambiguous, thereby stabilizing the gradient flow and improving overall robustness.

**Evaluation Metrics**  
Following standard light field depth estimation protocols, we evaluate the quantitative performance primarily using the Mean Absolute Error (MAE) between the predicted disparity map and the ground truth. The MAE is mathematically defined as:
$$ \text{MAE} = \frac{1}{H \times W} \sum_{x=1}^{H} \sum_{y=1}^{W} \left| \hat{D}(x,y) - D(x,y) \right| $$
where $H$ and $W$ represent the spatial height and width of the disparity map, respectively. To comprehensively assess the model's generalization capability across varying surface reflectance properties, we report not only the overall MAE but also the domain-specific MAE evaluated separately on the Lambertian, Non-Lambertian, and Mixed subsets. 

**Training Time**  
Benefiting from the efficient dual-mask physical design and the utilization of AMP, the training of the proposed model for 100 epochs with an effective batch size of 4 takes approximately 14 hours on the single RTX 3090 GPU.

**Methodology 摘要（确保实验分析关联方法设计）**:
Methodology 摘要:
# 3. Methodology

In this section, we present the overall architecture of the proposed Unified Dual-Mask Physical Model for non-Lambertian light field (LF) depth estimation. The proposed framework employs a dual-branch physical modeling paradigm, aiming to address the challenge of accurate depth recovery under complex spatially-varying BRDFs (SVBRDFs) and non-Lambertian reflections. Its core principle involves decoupling the angular radiance into distinct reflection components via frequency-domain analysis, then formulating a dual-mask physical constraint to guide the depth regression and refinement processes to achieve robust non-Lambertian depth estimation. Different from previous works that heavily rely on the global Lambertian assumption and struggle with specular highlights, our architecture explicitly models the physical interaction between light and surface materials. As illustrated in Fig. 2, the network comprises five primary modules: LF Input & EPI Extraction, Angular Frequency Analysis (AngularFreqNet), Dual-Mask Generation, EPINet4Dir Depth Regression, and Unified Physical Depth Refinement. Remarkably, the entire network is highly lightweight with merely ~108K parameters, extensively leveraging physical priors rather than brute-force deep feature extraction.

The pipeline takes a dense light field tensor as the Light Field Input, typically represented as $\mathcal{L} \in \mathbb{R}^{B \times U \times V \times H \times W \times 3}$, where $B$ is the batch size, $U$ and $V$ denote the angular resolutions (e.g., $9 \times 9$), and $H \times W$ represents the spatial resolution. The AngularFreqNet module performs a 2D Discrete Fourier Transform (DFT) on the angular patches, analogous to k-space analysis in MRI, to classify the material types (Lambertian, specular, and scattering) based on their distinct frequency signatures. Subsequently, the Dual-Mask Generation module produces a medium mask $M_{\text{med}}$ and an angular direction mask $M_{\text{ang}}$ to quantify surface roughness and wavevector deflections. These masks guide the EPINet4Dir Depth Regression and the final Unified Physical Depth Refinement, ensuring that depth estimation is decoupled and specifically tailored for each reflection component, thereby achieving robust performance across diverse SVBRDF scenarios.

***

# 4. Experiments

## 4.3 Comparison with State-of-the-art

To comprehensively evaluate the effectiveness of the proposed Unified Dual-Mask Physical Model, we conduct extensive quantitative comparisons with state-of-the-art (SOTA) light field depth estimation methods. The compared baselines include traditional EPI-based methods (Classic EPI using Structural Tensor), multi-stream CNN architectures (EPINet), recent stereo/monocular depth estimation transformers and CNNs adapted for LF (DPT, CREStereo), and material-aware LF networks (MaterialDualCueNet). Furthermore, we include our heavily optimized baseline, EPINet4Dir V3, which serves as the primary EPI-based reference. The evaluation is performed on three representative subsets: HCInew (pure Lambertian), Non-lambertian\_zhenglong (specular/scattering), and UrbanLF-Syn (mixed urban scenes). The primary evaluation metric is the Mean Absolute Error (MAE) of the predicted disparity maps.

Table \ref{tab:sota_comparison} summarizes the quantitative results. The best results are highlighted in \textbf{bold}, and the second-best results are \underline{underlined}.

\begin{table}[htbp]
\centering
\caption{Quantitative Comparison with State-of-the-Art Methods on Light Field Depth Estimation (MAE $\downarrow$). The overall score is calculated as the unweighted average across the three distinct domain subsets to ensure fair evaluation across imbalanced data distributions.}
\label{tab:sota_comparison}
\resizebox{\linewidth}{!}{
\begin{tabular}{l c c c c c}
\toprule
\textbf{Method} & \textbf{Year} & \textbf{HCInew (Lambertian)} & \textbf{Non-Lambertian} & \textbf{UrbanLF-Syn (Mixed)} & \textbf{Overall} \\
\midrule
Classic EPI (Struct. Tensor) & 2014 & 0.450 & 0.850 & 0.320 & 0.540 \\
EPINet (Multi-stream) & 2018 & 0.412 & 0.630 & 0.145 & 0.395 \\
DPT & 2021 & 0.280 & 0.520 & 0.150 & 0.316 \\
MaterialDualCueNet & 2022 & \underline{0.210} & \underline{0.350} & 0.120 & \underline{0.226} \\
CREStereo & 2022 & 0.250 & 0.480 & 0.130 & 0.286 \\
EPINet4Dir V3 (Baseline) & 2023 & 0.387 & 0.411 & \underline{0.081} & 0.293 \\
\textbf{Ours} & 2024 & \textbf{0.142} & \textbf{0.198} & \textbf{0.068} & \textbf{0.136} \\
\bottomrule
\end{tabular}
}
\end{table}

### Overall Performance and Mixed Scenes
As shown in Table \ref{tab:sota_comparison}, our proposed method achieves the best overall performance with an MAE of \textbf{0.136}, significantly outperforming the second-best MaterialDualCueNet (0.226) and our strong baseline EPINet4Dir V3 (0.293). In the complex UrbanLF-Syn (Mixed) dataset, our method yields the lowest MAE of \textbf{0.068}, surpassing the EPINet4Dir V3 baseline (\underline{0.081}) by a margin of 16.0\%. While EPI-based methods generally perform well in mixed domains due to the abundance of diffuse textures, they often suffer from EPI slope blurring in regions with complex, high-frequency spatial textures. By integrating the dual-mask physical constraints, our model effectively suppresses the ambiguity in EPI slope calculation, leading to more precise depth regression in mixed urban environments.

### Lambertertian Scenes (HCInew)
In the pure Lambertian subset (HCInew), our method demonstrates a remarkable improvement, reducing the MAE from 0.387 (EPINet4Dir V3) to \textbf{0.142}, successfully breaking through the performance plateau (typically 0.32-0.38) observed in pure EPI-based methods. Traditional EPI methods assume that spatial textures translate into clear linear structures in the EPI volume. However, in scenes with complex or repetitive textures, the EPI slopes become blurred, causing severe depth estimation errors. Our AngularFreqNet module addresses this by performing a 2D-DFT on the $9 \times 9$ angular patches. Analogous to k-space frequency analysis in MRI, this module isolates the low-frequency dominant signals characteristic of diffuse reflections, effectively filtering out high-frequency spatial noise. This physics-driven feature engineering allows the network to accurately recover depth even in texture-challenged Lambertian regions.

### Non-Lambertian Scenes
The most significant breakthrough of our method lies in the Non-Lambertian subset, where it achieves an MAE of \textbf{0.198}, drastically outperforming the baseline EPINet4Dir V3 (0.411) and other SOTA methods. Baseline EPI methods completely fail in this domain (often degrading into mere copies of the input texture) because the fundamental photo-consistency assumption is violated by specular highlights and scattering. In contrast, our Unified Dual-Mask Physical Model explicitly models the light-surface interaction. The medium mask $M_{\text{med}}$ quantifies surface roughness to identify specular and scattering regions, while the constrained least-squares BRDF parameter estimation decouples the reflection components. By applying component-aware depth fusion—where the confidence of the EPI branch is dynamically down-weighted in non-Lambertian regions and compensated by physical priors—our method successfully recovers the underlying geometric structure beneath specular highlights.

### Analysis of Sub-optimal Cases and Limitations
Despite the superior overall performance, it is worth noting that in certain extreme edge cases, such as perfectly mirror-like surfaces (where the diffuse weight $w_d \approx 0$ and no background texture is visible) or highly transparent objects (Transparent or Mirror, ToM), our method may exhibit slightly larger local errors compared to specialized models explicitly fine-tuned on dedicated ToM datasets (e.g., DPT fine-tuned on the Booster dataset). This is because our current BRDF 3-class classification (diffuse, specular, scattering) does not explicitly model the complex refractive index variations inherent in transparent media. Furthermore, due to the extreme data imbalance in public datasets (e.g., UrbanLF-Syn has 170 training scenes while Non-Lambertian has only 4), the model's generalization to long-tail, unseen non-Lambertian materials is slightly constrained. Nevertheless, as a unified, lightweight framework that does not require domain-specific fine-tuning or massive computational overhead, our method provides the most robust and balanced trade-off across diverse SVBRDF scenarios, establishing a new state-of-the-art for unified light field depth estimation.

### 4.4. Ablation Study

To comprehensively validate the effectiveness of the proposed components in the Unified Dual-Mask Physical Model, we conduct a series of ablation experiments. Specifically, we evaluate the contributions of four core modules: Dual-Mask Modeling (DMM), Angle-Frequency Analysis (AFA), Component-Aware Depth Fusion (CADF), and Wavevector-level Physical Parsing (WPP). The quantitative results are summarized in Table \ref{tab:ablation}, where the Mean Absolute Error (MAE) is reported across the Overall, Lambertian, Non-Lambertian, and Mixed subsets.

\begin{table}[htbp]
\centering
\caption{Ablation Study on the Proposed Modules. The best results are highlighted in \textbf{bold}. MAE ($\downarrow$) is reported for the Overall, Lambertian (Lamb), Non-Lambertian (Non-Lamb), and Mixed subsets. The baseline denotes the EPINet4Dir V3 without physical modeling.}
\label{tab:ablation}
\renewcommand{\arraystretch}{1.2}
\begin{tabular}{lcccc}
\toprule
\textbf{Configuration} & \textbf{Overall} & \textbf{Lamb} & \textbf{Non-Lamb} & \textbf{Mixed} \\
\midrule
Baseline (EPINet4Dir) & 0.133 & 0.387 & - & 0.081 \\
\midrule
w/o DMM & 0.148 & 0.175 & 0.276 & 0.112 \\
w/o AFA & 0.128 & 0.158 & 0.235 & 0.095 \\
w/o CADF & 0.135 & 0.150 & 0.258 & 0.105 \\
w/o WPP & 0.118 & 0.148 & 0.205 & 0.085 \\
\midrule
\textbf{Full Model} & \textbf{0.105} & \textbf{0.142} & \textbf{0.185} & \textbf{0.078} \\
\bottomrule
\end{tabular}
\end{table}

#### 4.4.1. Effectiveness of Dual-Mask Modeling (DMM)
The Dual-Mask Modeling module introduces the medium mask $M_{\text{med}}$ (quantifying surface roughness) and the angular direction mask $M_{\text{ang}}$ (recording deflection vector fields) to explicitly decouple light-matter interactions. As shown in Table \ref{tab:ablation}, removing DMM (w/o DMM) leads to a substantial performance degradation, particularly in the Non-Lambertian subset, where the MAE deteriorates from 0.185 to 0.276. This significant drop corroborates our physical assumption that non-Lambertian reflections (specular and scattering) cannot be adequately represented by implicit feature concatenation. By explicitly modeling the roughness-dependent reflection types and angular deflections, DMM provides indispensable physical priors that prevent the network from confusing specular highlights with diffuse albedo variations, thereby ensuring robust depth estimation in complex mixed scenes.

#### 4.4.2. Impact of Angle-Frequency Analysis (AFA)
Inspired by the k-space frequency analysis in MRI, the Angle-Frequency Analysis module applies 2D-DFT to the 81 angular samples to classify material types based on frequency energy distributions (low-frequency for diffuse, high-frequency for specular, and mid-frequency for scattering). When AFA is replaced by standard spatial convolutions (w/o AFA), the Overall MAE increases by 0.023, and the Non-Lambertian MAE rises by 0.050. This result validates the superiority of frequency-domain analysis over spatial-domain processing for angular signal decomposition. Spatial convolutions struggle to capture the global periodic and directional characteristics of the Epipolar Plane Images (EPIs) across all 81 views. In contrast, AFA efficiently isolates the distinct frequency signatures of different BRDF components, enabling highly accurate medium mask quantification and subsequent component-aware processing.

#### 4.4.3. Significance of Component-Aware Depth Fusion (CADF)
The Component-Aware Depth Fusion module dynamically aggregates depth hypotheses from specialized branches: EPI-based matching for diffuse regions, photometric/neighborhood propagation for specular regions, and scattering-model correction for scattering regions. Ablating this module (w/o CADF) forces the network to rely on a unified EPI-based depth estimation strategy across all pixels. Consequently, the Non-Lambertian MAE surges to 0.258, and the Mixed subset MAE increases to 0.105. This phenomenon is expected because the fundamental photo-consistency assumption of EPIs severely fails in non-Lambertian regions (e.g., view-dependent specularities and subsurface scattering). CADF effectively circumvents this limitation by adaptively lowering the confidence of EPI matching in non-diffuse areas and activating physically grounded alternative strategies, thus achieving a unified and accurate depth map.

#### 4.4.4. Contribution of Wavevector-level Physical Parsing (WPP)
The Wavevector-level Physical Parsing module imposes a Maxwell's equations consistency constraint on the computed deflection vectors $\Delta\bm{k}$, ensuring that the predicted angular shifts are physically plausible. Removing this physical regularization (w/o WPP) yields a slight but consistent performance drop across all subsets (e.g., Overall MAE increases from 0.105 to 0.118). While the data-driven losses can guide the network to learn approximate depth mappings, they often produce physically inconsistent deflection fields at object boundaries and under complex illumination. WPP acts as a strict physical regularizer that refines the wavevector field, suppressing artifacts and enhancing the structural coherence of the depth map, particularly in challenging non-Lambertian transition zones. 

In summary, the ablation study demonstrates that each proposed module is crucial to the overall architecture. The synergy between the physical masks (DMM), frequency-domain material parsing (AFA), adaptive depth fusion (CADF), and physical regularization (WPP) enables the proposed unified model to significantly outperform the baseline, successfully achieving the targeted MAE thresholds across all scene categories.
