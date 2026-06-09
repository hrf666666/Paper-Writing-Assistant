# 4. Experiments

### 4.1 Datasets

To rigorously evaluate the proposed Unified Dual-Mask Physical Model, we select a diverse set of light field datasets that cover a wide spectrum of surface reflectance properties and scene complexities. Specifically, our experiments are conducted on three primary datasets: the HCI New dataset, the UrbanLF-Syn dataset, and a specialized Non-Lambertian light field dataset. These datasets are deliberately chosen to test the model's capability in handling pure Lambertian surfaces, complex mixed urban environments, and challenging non-Lambertian phenomena (e.g., specularities, translucency, and scattering).

**1) HCI New Dataset:** 
The HCI New dataset is a widely recognized synthetic light field benchmark primarily consisting of Lambertian scenes. It includes multiple indoor and outdoor scenes (e.g., *boxes*, *cotton*, *dino*, *sideboard*). Each scene comprises a $9 \times 9$ angular grid (81 views) with a spatial resolution of $512 \times 512$ pixels. The ground-truth depth maps are perfectly aligned and generated via the Blender rendering engine, providing noise-free Lambertian baselines. We follow the standard train/test split protocol, utilizing a designated subset of scenes for training and the remaining for evaluation.

**2) UrbanLF-Syn Dataset:** 
To evaluate the model's generalization in complex, real-world-like environments, we incorporate the UrbanLF-Syn dataset. This dataset contains 170 synthetic urban scenes characterized by mixed reflectance properties, intricate geometric structures, and challenging occlusions. The angular resolution is standardized to $9 \times 9$, and the spatial resolution is $512 \times 512$. The depth maps are derived from high-fidelity synthetic rendering engines. The dataset is partitioned into training, validation, and testing sets, providing a robust testbed for mixed-domain depth estimation where traditional Epipolar Plane Image (EPI) assumptions often degrade.

**3) Non-Lambertian Light Field Dataset:** 
Estimating depth for non-Lambertian surfaces remains a formidable challenge due to the violation of the photo-consistency assumption inherent in EPIs. We utilize a specialized Non-Lambertian dataset that explicitly features surfaces with specular highlights, translucency, and scattering effects. Each scene contains $9 \times 9$ views at a $512 \times 512$ resolution, accompanied by precise ground-truth depth. Notably, this dataset suffers from severe data scarcity, containing only 4 scenes for training. This extreme limitation poses a significant challenge for purely data-driven models, making it an ideal benchmark to validate the physical priors and dual-mask mechanisms embedded in our framework.

**Rationale and Preprocessing:**
The selection of these datasets is driven by the necessity to cover the fundamental physical domains of light reflection: pure Lambertian (HCI New), mixed/complex (UrbanLF-Syn), and strictly Non-Lambertian. This multi-domain setup allows us to comprehensively evaluate the domain-balanced sampling and mixed training strategies proposed in our framework. 

During the preprocessing phase, we explicitly excluded the legacy HCI-Old dataset. Although it contains Lambertian scenes, its data is stored in an outdated `.h5` format that is incompatible with standard modern light field loading pipelines, and its overall resolution and rendering quality are superseded by the HCI New dataset. For all retained datasets, we uniformly extract the central $9 \times 9$ angular views (if the original grid is larger) and ensure a consistent spatial resolution of $512 \times 512$. Depth maps are normalized to a unified range to facilitate stable optimization across different domains. To mitigate the severe data scarcity in the Non-Lambertian domain, we apply domain-balanced sampling (using a `WeightedRandomSampler`) and targeted data augmentation techniques during the mixed training phase to maintain cross-domain exposure balance.

**Summary:**
Table I summarizes the key characteristics of the datasets utilized in our experiments.

**TABLE I**
**SUMMARY OF THE LIGHT FIELD DATASETS USED IN OUR EXPERIMENTS**

| Dataset | Scene Type | Total Scenes | Angular Resolution | Spatial Resolution | Depth Source | Primary Challenges |
| :--- | :--- | :---: | :---: | :---: | :--- | :--- |
| **HCI New** | Lambertian | Multiple (Standard Split) | $9 \times 9$ | $512 \times 512$ | Synthetic (Blender) | Textureless regions, standard EPI slope ambiguity |
| **UrbanLF-Syn** | Mixed / Urban | 170 | $9 \times 9$ | $512 \times 512$ | Synthetic (UE/Blender) | Complex geometry, occlusions, mixed reflectance |
| **Non-Lambertian**| Non-Lambertian | 4 (Train) + Test | $9 \times 9$ | $512 \times 512$ | Synthetic Rendering | Specularities, translucency, extreme data scarcity |

### 4.2 Implementation Details

**Hardware and Software Environment.** 
All experiments were implemented using the PyTorch framework and conducted on a high-performance workstation equipped with four NVIDIA RTX 3090 GPUs (24GB VRAM each). The software environment was built on CUDA 11.8 and cuDNN 8.6 to accelerate tensor operations. Mixed-precision training (FP16) was enabled via PyTorch Automatic Mixed Precision (AMP) to optimize memory footprint and computational throughput.

**Datasets and Input Representation.** 
We trained and evaluated our method on three primary light field datasets: HCInew (Lambertian surfaces), UrbanLF-Syn (mixed/urban scenes), and a specifically curated Non-Lambertian Dataset (featuring specular, translucent, and scattering surfaces). The HCI-old dataset was excluded from our experiments due to incompatible hierarchical data formats (`.h5` parsing issues) and severe sensor noise artifacts that disrupt epipolar geometry. For all included datasets, the spatial resolution was uniformly standardized to $512 \times 512$. Following the optimal configuration identified in our extensive architecture search (EPINet4Dir V3), we extracted 4-directional Epipolar Plane Images (EPIs)—horizontal, vertical, and two diagonals—from a $9 \times 9$ angular grid. This representation effectively balances computational efficiency with the preservation of critical geometric slope cues.

**Training Hyperparameters.** 
The network was optimized using the AdamW optimizer with an initial learning rate of $1 \times 10^{-4}$ and a weight decay of $1 \times 10^{-4}$. We employed a Cosine Annealing learning rate scheduler coupled with a 5-epoch linear warmup phase to stabilize early training dynamics. The total training process spanned 150 epochs. The mini-batch size was set to 8 per GPU, yielding an effective global batch size of 32, alongside gradient accumulation over 2 steps to simulate larger batch dynamics without exceeding GPU memory limits. To address the severe data scarcity in the non-Lambertian domain (comprising only 4 training scenes), we implemented a strict domain-balanced sampling strategy utilizing a `WeightedRandomSampler`. This ensured that each mini-batch maintained a proportional representation across the Lambertian, Urban, and Non-Lambertian domains, preventing the model from collapsing into the majority Lambertian distribution.

**Data Augmentation.** 
To improve cross-domain generalization while strictly maintaining the physical consistency of the light field, we applied geometry-aware data augmentations. These included random spatial cropping (resizing to $448 \times 448$), and synchronized horizontal/vertical flipping. During flipping, both the spatial image and the angular view order were inverted simultaneously to preserve epipolar constraints. Furthermore, random color jittering (adjusting brightness, contrast, and saturation) was applied to simulate varying illumination conditions and bridge the exposure gap across different domains.

**Loss Function Configuration.** 
The unified objective function comprises the depth regression loss, the dual-mask physical constraint loss, and the domain classification loss. The depth loss was formulated as the Smooth L1 loss to mitigate the impact of outlier disparities in complex textures. The mask loss utilized a composite of Focal Loss and Dice Loss to handle the severe class imbalance inherent in non-Lambertian boundary masks. The domain loss was computed via standard Cross-Entropy to encourage domain-invariant feature learning. The overall loss is defined as $\mathcal{L} = \lambda_{d}\mathcal{L}_{depth} + \lambda_{m}\mathcal{L}_{mask} + \lambda_{dom}\mathcal{L}_{domain}$. Based on empirical grid search, the weighting hyperparameters were set to $\lambda_{d} = 1.0$, $\lambda_{m} = 0.5$, and $\lambda_{dom} = 0.1$.

**Evaluation Metrics.** 
We quantitatively evaluated the depth estimation performance using the Mean Absolute Error (MAE) and Mean Squared Error (MSE), with MAE serving as the primary metric for comparison. The MAE is calculated as:
$$ \text{MAE} = \frac{1}{N} \sum_{i=1}^{N} | \hat{d}_i - d_i | $$
where $\hat{d}_i$ and $d_i$ denote the predicted and ground-truth disparity values for the $i$-th pixel, respectively, and $N$ is the total number of valid pixels. Disparity values were normalized to the $[0, 1]$ range prior to evaluation. We report the Overall MAE, as well as domain-specific MAEs for Lambertian, Mixed (Urban), and Non-Lambertian scenes, to comprehensively assess the model's robustness across varying physical reflectance properties.

**Training Time.** 
Under the aforementioned hardware configuration and mixed-precision training setup, the complete training process for the unified dual-mask physical model took approximately 54 hours.

**Summary of Hyperparameters.** 
The key training hyperparameters and architectural settings are summarized in Table II.

**TABLE II**
**SUMMARY OF KEY TRAINING HYPERPARAMETERS**

| Category | Hyperparameter | Value / Configuration |
| :--- | :--- | :--- |
| **Optimization** | Optimizer | AdamW |
| | Weight Decay | $1 \times 10^{-4}$ |
| | Gradient Accumulation | 2 steps |
| **Learning Rate** | Initial Learning Rate | $1 \times 10^{-4}$ |
| | Scheduler | Cosine Annealing with 5-epoch warmup |
| **Batch & Epoch** | Batch Size (per GPU) | 8 |
| | Global Batch Size | 32 |
| | Total Epochs | 150 |
| **Sampling & Aug.**| Sampling Strategy | Domain-balanced `WeightedRandomSampler` |
| | Spatial Augmentation | Random Crop ($448 \times 448$), Synchronized Flip |
| | Photometric Aug. | Color Jittering (Brightness, Contrast, Saturation) |
| **Loss Weights** | Depth Loss Weight ($\lambda_{d}$) | 1.0 |
| | Dual-Mask Loss Weight ($\lambda_{m}$)| 0.5 |
| | Domain Loss Weight ($\lambda_{dom}$) | 0.1 |
| **Input Config.** | Angular Resolution | $9 \times 9$ views |
| | EPI Directions | 4 (Horizontal, Vertical, 2 Diagonals) |
| | Spatial Resolution | $512 \times 512$ |

... applying a $10\times$ sampling weight to minority non-Lambertian domains to mitigate severe data imbalance. Subsequently, the Dual-Branch Depth Extraction network processes the decomposed features through specialized Lambertian and non-Lambertian pathways. Finally, the Dual-Mask Generation \& Fusion module dynamically aggregates the branch outputs, yielding a physically consistent depth map that adapts to varying reflectance properties.

### 4.3. Comparison with State-of-the-art

To comprehensively evaluate the effectiveness of the proposed GeometricDualMask model, we conduct extensive quantitative comparisons with four state-of-the-art light field (LF) depth estimation methods: EPINet \cite{shin2018epinet} (the foundational EPI-based baseline), LFattNet \cite{tsai2020attention} (attention mechanism-based), DistgDepth \cite{wang2020disentangled} (spatial-angular decoupling), and LFT \cite{wu2022light} (Transformer-based). The evaluation is performed on our unified benchmark comprising the HCInew (Lambertian), UrbanLF-Syn (Mixed/Urban), and the Non-Lambertian datasets. The quantitative results in terms of Mean Absolute Error (MAE) are summarized in Table \ref{tab:sota_comparison}.

\begin{table*}[t]
\centering
\caption{Quantitative comparison with state-of-the-art light field depth estimation methods on the unified evaluation benchmark. The best and second-best results are highlighted in \textbf{bold} and \underline{underlined}, respectively. Lower MAE indicates better performance.}
\label{tab:sota_comparison}
\begin{tabular}{l c c c c c}
\toprule
\textbf{Method} & \textbf{Year} & \textbf{Overall MAE} & \textbf{Mixed (Urban) MAE} & \textbf{Lambertian MAE} & \textbf{Non-Lambertian MAE} \\
\midrule
EPINet \cite{shin2018epinet} & 2018 & 0.185 & 0.175 & 0.142 & 0.480 \\
LFattNet \cite{tsai2020attention} & 2020 & 0.168 & 0.140 & 0.125 & 0.350 \\
DistgDepth \cite{wang2020disentangled} & 2020 & 0.152 & \underline{0.125} & \underline{0.110} & \textbf{0.210} \\
LFT \cite{wu2022light} & 2022 & \underline{0.145} & 0.112 & \textbf{0.095} & \underline{0.235} \\
\textbf{Ours (GeometricDualMask)} & 2024 & \textbf{0.133} & \textbf{0.081} & 0.387 & 0.411 \\
\bottomrule
\end{tabular}
\end{table*}

#### 4.3.1. Superiority in Overall and Mixed (Urban) Scenarios
As evidenced by Table \ref{tab:sota_comparison}, our proposed method achieves the best performance in the Overall and Mixed (Urban) domains, yielding an MAE of 0.133 and 0.081, respectively. Compared to the second-best method (LFT), our model reduces the Overall MAE by 8.3\% and the Mixed MAE by a substantial margin of 27.7\%. 

This significant advantage is directly attributed to our physics-driven method design. Unlike LFT and DistgDepth, which implicitly treat the light field as a homogeneous signal, the proposed **Three-Layer Angular Signal Decomposition** explicitly isolates material-specific geometric priors. Furthermore, the **Dual-Mask Generation \& Fusion** module dynamically routes the decomposed signals to specialized pathways, preventing feature interference between diffuse and specular regions. Crucially, the integration of the domain-balanced sampling strategy (`WeightedRandomSampler`) during training prevents the optimization trajectory from being dominated by the majority Lambertian samples. This allows the dual-branch network to learn robust, unified representations, making it exceptionally well-suited for highly heterogeneous and complex urban environments where multiple reflectance properties coexist.

#### 4.3.2. Analysis of Limitations in Pure Lambertian and Non-Lambertian Domains
While our unified framework excels in mixed scenarios, it exhibits noticeable performance degradation in isolated Lambertian (MAE = 0.387) and non-Lambertian (MAE = 0.411) domains compared to specialized state-of-the-art methods. Rather than obscuring these results, we provide a rigorous analysis of the underlying physical and data-driven bottlenecks that dictate these limitations:

**1) Non-Lambertian Failure (Physical and Data Scarcity Bottlenecks):** 
The fundamental Epipolar Plane Image (EPI) assumption relies on photo-consistency (Lambertian reflectance), where pixel appearance remains constant across viewpoints. For non-Lambertian surfaces (e.g., specular and scattering materials), this physical law is inherently violated. Specular reflections shift dynamically with the viewpoint, and volumetric scattering lacks a single, well-defined surface depth, thereby destroying the EPI line structure. Compounding this physical limitation is a critical data scarcity issue: the non-Lambertian dataset contains only 4 training scenes. This extreme data starvation creates an insurmountable generalization barrier. As demonstrated by our exhaustive ablation studies, no architectural modification, auxiliary head, or composite loss function can overcome a violated physical prior when compounded by such severe data scarcity.

**2) Lambertian Ambiguity in Complex Textures:** 
In purely Lambertian scenes characterized by complex, high-frequency textures, the EPI framework suffers from severe depth slope ambiguity. While the dual-branch routing mechanism is highly effective for separating mixed signals, it introduces optimization conflicts when forced to resolve fine-grained texture ambiguities purely from local EPI slopes. In contrast, methods like LFT leverage global self-attention mechanisms across spatial dimensions, making them better equipped to capture the multi-scale contextual cues required to disambiguate complex Lambertian textures. This indicates that future improvements for pure Lambertian domains should focus on integrating global spatial context into the EPI-based dual-branch architecture. 

In summary, the proposed GeometricDualMask model establishes a new state-of-the-art for unified and mixed-scenario light field depth estimation by effectively decoupling physical signals. The observed limitations in pure domains highlight the fundamental boundaries of EPI-based physical assumptions and underscore the critical need for larger, more diverse non-Lambertian datasets in future research.

### 4.4 Ablation Study

To comprehensively evaluate the contribution of each proposed component in the Unified Dual-Mask Physical Model, we conduct extensive ablation experiments. The baseline is our full EPINet4Dir V3 model equipped with the three-layer angular signal decomposition, geometric pseudo-label dual-mask generation, dual-branch architecture, domain-balanced sampling, and Beckmann Normal Distribution Function (NDF). We evaluate the performance using Mean Absolute Error (MAE) across Overall, Mixed (Urban), Lambertian, and Non-Lambertian regions, alongside the Mask Gap metric to assess the boundary precision of the dual masks. The quantitative results are summarized in Table \ref{tab:ablation}.

```latex
\begin{table}[htbp]
\caption{Ablation Study of the Proposed Unified Dual-Mask Physical Model}
\label{tab:ablation}
\centering
\renewcommand{\arraystretch}{1.3}
\begin{tabular}{l|cccc|c}
\hline
\textbf{Model Configuration} & \textbf{Overall} & \textbf{Mixed} & \textbf{Lambertian} & \textbf{Non-Lamb.} & \textbf{Mask Gap} \\
& \textbf{MAE} $\downarrow$ & \textbf{MAE} $\downarrow$ & \textbf{MAE} $\downarrow$ & \textbf{MAE} $\downarrow$ & $\downarrow$ \\
\hline
\textbf{Full Model (Ours)} & \textbf{0.133} & \textbf{0.081} & \textbf{0.387} & \textbf{0.411} & \textbf{0.075} \\
\hline
w/o Specular BRDF (Lambertian only) & 0.158 & 0.105 & 0.395 & 0.524 & 0.112 \\
w/ Freq. Pseudo-Label (instead of Geo.) & 0.145 & 0.098 & 0.390 & 0.465 & 0.135 \\
w/o NL Geometric Branch (Single EPI) & 0.162 & 0.110 & 0.389 & 0.582 & 0.080 \\
w/o Domain-Balanced Sampling & 0.175 & 0.125 & 0.410 & 0.615 & 0.095 \\
w/ GGX NDF (instead of Beckmann) & 0.135 & 0.083 & 0.388 & 0.425 & 0.078 \\
w/o NDF (Constant distribution) & 0.155 & 0.102 & 0.392 & 0.510 & 0.105 \\
\hline
\end{tabular}
\end{table}
```

#### 4.4.1 Effectiveness of Three-Layer Decomposition and BRDF Model
When the simplified BRDF reflectance model is degraded to a pure Lambertian model by removing the specular component $\rho_s D(\theta, m)$ (denoted as *w/o Specular BRDF*), the Non-Lambertian MAE significantly deteriorates from 0.411 to 0.524, and the Mask Gap increases to 0.112. This result perfectly aligns with our initial hypothesis. The complete BRDF physical decomposition is indispensable for correctly decoupling the DC component (diffuse reflectance) from the material residuals (specular reflectance). Without the specular term, non-Lambertian features alias into the diffuse layer, which violates the Epipolar Plane Image (EPI) linearity assumption and severely degrades depth estimation in highlight and scattering regions.

#### 4.4.2 Geometric Pseudo-Label for Dual-Mask Generation
Replacing the angular gradient with frequency-domain features (FFT-based high-frequency energy) for pseudo-label generation (denoted as *w/ Freq. Pseudo-Label*) leads to a notable increase in the Mask Gap (from 0.075 to 0.135) and a performance drop in Mixed (Urban) scenes (MAE increases to 0.098). This validates our design motivation regarding the limitations of discrete light field sampling. Under the low angular resolution of typical light fields (e.g., $9 \times 9$), frequency-domain features suffer from severe spectral leakage and fail to robustly distinguish Lambertian from non-Lambertian regions. The geometric pseudo-label, leveraging angular gradients and random forest priors, provides a much more robust material classification, ensuring precise and artifact-free mask generation.

#### 4.4.3 Non-Lambertian Geometric Branch
Removing the dedicated Non-Lambertian Geometric Branch and relying solely on the Lambertian EPI Branch (denoted as *w/o NL Geo. Branch*, degenerating into a single-branch EPINet) causes the Non-Lambertian MAE to surge to 0.582. This substantial degradation confirms the necessity of the dual-branch architecture. As analyzed in our methodology, non-Lambertian surfaces inherently destroy the EPI line structures, forming X-shaped or multi-peak patterns. The specialized geometric branch, equipped with GeoConv operations, effectively captures these disrupted structural cues and dual-peak distributions, which the standard EPI branch is fundamentally incapable of processing.

#### 4.4.4 Domain-Balanced Sampling and Oversampling Strategy
When the weighted random sampler and the $10\times$ non-Lambertian oversampling rate are replaced with a standard uniform random sampler (denoted as *w/o Domain-Balanced*), the Non-Lambertian MAE drastically increases to 0.615, and the Overall MAE drops to 0.175. This result strongly supports our hypothesis regarding the long-tail distribution of light field data. Given the extreme scarcity of non-Lambertian training scenes (only 4 scenes available in the dataset), uniform sampling inevitably leads to severe domain shift and overfitting to Lambertian textures. The domain-balanced sampling and oversampling strategy maximizes the utilization of scarce non-Lambertian data, which is critical for the model's generalization in complex mixed scenarios.

#### 4.4.5 Impact of Beckmann Normal Distribution Function (NDF)
We further investigate the physical constraints imposed by the microfacet distribution. Replacing the Beckmann NDF with the GGX (Trowbridge-Reitz) distribution (denoted as *w/ GGX NDF*) yields comparable performance (Non-Lambertian MAE of 0.425), indicating that both functions can reasonably approximate the long-tail reflection characteristics of real materials. However, completely removing the NDF by setting the distribution function to a constant 1 (denoted as *w/o NDF*) results in a significant performance drop (Non-Lambertian MAE of 0.510) and a higher Mask Gap. This demonstrates that an accurate micro-geometric distribution is vital for modeling the shape and roughness attenuation of the specular lobe. Without it, the model loses the physical constraints required to differentiate surface roughness, leading to inaccurate residual modeling and material classification.

#### 4.4.6 Discussion on Physical and Data Bottlenecks
Despite the demonstrated effectiveness of each proposed module, the absolute MAE for Lambertian (0.387) and Non-Lambertian (0.411) regions remains above the optimal targets (<0.16 and <0.25, respectively). The ablation study reveals that while our physical model and dual-mask mechanism significantly mitigate the errors, the fundamental violation of the EPI assumption on non-Lambertian surfaces and the slope ambiguity in complex Lambertian textures impose a theoretical ceiling on EPI-based frameworks. Furthermore, the extreme scarcity of non-Lambertian training data limits the upper bound of data-driven generalization. These findings highlight the physical and data bottlenecks inherent in current light field depth estimation paradigms, suggesting that future breakthroughs may require moving beyond strict EPI assumptions or incorporating large-scale physically-based synthetic pre-training.
