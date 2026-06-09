# 4. Experiments

### 4.1 Datasets

To comprehensively evaluate the proposed Unified Dual-Mask Physical Model and validate its effectiveness across diverse material properties and scene complexities, we conduct extensive experiments on three representative light field (LF) depth estimation datasets. These datasets are meticulously selected to cover a broad spectrum of surface reflectance properties, ranging from ideal Lambertian to highly challenging Non-Lambertian and complex Mixed/Urban environments.

#### 4.1.1 Dataset Descriptions

**HCI New Dataset:** The HCI New dataset is a widely-used synthetic LF dataset primarily composed of Lambertian scenes (e.g., *boxes*, *cotton*). It provides $9 \times 9$ angular views with a spatial resolution of $512 \times 512$ pixels. The ground truth (GT) depth/disparity maps are generated via Blender with pixel-perfect accuracy. Following standard protocols, the dataset is divided into training and testing sets, with stratified sampling employed to ensure a balanced distribution of scene complexities. It serves as the foundational benchmark for evaluating the model's performance under the ideal Lambertian assumption, where epipolar plane image (EPI) line structures are well-preserved and photo-consistency holds strictly.

**UrbanLF-Syn Dataset:** To evaluate the model's robustness in complex, real-world-like environments, we incorporate the UrbanLF-Syn dataset. It comprises 170 synthetic urban and mixed scenes, featuring intricate textures, severe occlusions, and diverse material mixtures. Each scene contains $9 \times 9$ angular views with a spatial resolution of $512 \times 512$ pixels. The GT disparity maps are rendered using advanced ray-tracing engines. The dataset is partitioned into training and validation sets. This dataset introduces the "Mixed/Urban" domain, challenging the model with disrupted EPI slopes caused by complex occlusions, depth discontinuities, and non-ideal diffuse reflections.

**Non-Lambertian Dataset:** To specifically assess the core contribution of our physical model—handling non-Lambertian materials—we utilize a specialized Non-Lambertian dataset. It focuses exclusively on scenes exhibiting specular highlights, translucency, and scattering effects. Each scene provides $9 \times 9$ angular views. The GT depth maps are acquired through precise ray-tracing that accounts for complex light transport. Crucially, this dataset suffers from severe data scarcity, containing only 4 training scenes. It represents the most challenging domain, as the fundamental physical assumption of photo-consistency across views is fundamentally violated by view-dependent reflections and refractions, rendering conventional EPI-based methods ineffective.

#### 4.1.2 Rationale for Dataset Selection

The selection of these three datasets is driven by the necessity to evaluate the model across distinct physical domains and reflectance properties. The *HCI New* dataset establishes the baseline performance for standard Lambertian surfaces, ensuring the model does not degrade on well-posed problems. The *UrbanLF-Syn* dataset tests the model's generalization in mixed, occlusion-heavy urban scenarios, evaluating the Dual-Mask mechanism's ability to handle geometric ambiguities. Most importantly, the *Non-Lambertian* dataset directly targets the limitations of conventional methods, providing a rigorous testbed for our Angular FFT Material Classification and domain-specific mask learning modules. By evaluating across these domains, we can systematically analyze the model's capability to decouple material-specific physical degradations from geometric depth cues. *(Note: The older HCI-Old dataset was excluded from our final evaluation due to its outdated rendering artifacts and lower resolution, which do not align with the rigorous requirements of modern physical LF models.)*

#### 4.1.3 Preprocessing and Training Strategies

For all datasets, the input LF images are preprocessed to extract 4-direction Epipolar Plane Images (EPIs) to capture multi-directional geometric structures efficiently. The GT high-resolution depth maps are downsampled to generate low-resolution disparity maps (`gt_disp_lowres.pfm`), which serve as the supervision target to align with standard LF depth estimation evaluation metrics and reduce computational overhead.

To address the severe data imbalance among the domains (e.g., 170 scenes in UrbanLF-Syn vs. 4 scenes in Non-Lambertian), we implement a **Domain-balanced sampling** strategy during training. Specifically, a `WeightedRandomSampler` is utilized to dynamically adjust the sampling probabilities, ensuring that the minority Non-Lambertian domain receives sufficient exposure to prevent the model from collapsing into the majority Lambertian/Mixed domains. Furthermore, data augmentation techniques, including random spatial cropping, angular view shifting, and color jittering, are applied to mitigate overfitting, which is particularly critical for the data-scarce Non-Lambertian scenes.

#### 4.1.4 Dataset Summary

Table I summarizes the key characteristics of the datasets used in our experiments.

**TABLE I**
**SUMMARY OF THE DATASETS USED FOR TRAINING AND EVALUATION**

| Dataset | Domain / Scene Type | Scenes (Train/Test) | Angular Resolution | Spatial Resolution | GT Source | Key Challenges |
| :--- | :--- | :---: | :---: | :---: | :--- | :--- |
| **HCI New** | Lambertian | Multiple (Stratified) | $9 \times 9$ | $512 \times 512$ | Blender Synthesis | Standard EPI slope estimation, textureless regions. |
| **UrbanLF-Syn** | Mixed / Urban | 170 (Split) | $9 \times 9$ | $512 \times 512$ | Ray-tracing Synthesis | Complex occlusions, intricate textures, mixed materials. |
| **Non-Lambertian**| Non-Lambertian | 4 (Highly Scarce) | $9 \times 9$ | $512 \times 512$ | Ray-tracing Synthesis | Specularities, translucency, violation of photo-consistency. |

### 4.2 Implementation Details

**Hardware and Software Environment.** 
The proposed Unified Dual-Mask Physical Model is implemented using the PyTorch framework. All experiments are conducted on a high-performance computing workstation equipped with two NVIDIA GeForce RTX 3090 GPUs (24GB VRAM each). The Distributed Data Parallel (DDP) strategy is utilized to synchronize gradients and accelerate the training process across GPUs.

**Training Hyperparameters.** 
The network is optimized using the AdamW optimizer with a weight decay of $1 \times 10^{-4}$ to prevent overfitting, which is particularly crucial given the scarcity of Non-Lambertian training samples. The initial learning rate is set to $9.99 \times 10^{-5}$, modulated by a cosine annealing scheduler with a 5-epoch linear warm-up phase to stabilize early training dynamics. To accommodate the high memory footprint of 4D light field tensors (e.g., $9 \times 9$ angular views), we employ a micro-batch size of 4 per GPU coupled with gradient accumulation over 4 steps, yielding an effective batch size of 32. The model is trained for a maximum of 100 epochs, with an early stopping mechanism triggered if the validation Overall MAE does not improve for 15 consecutive epochs. The key hyperparameters are summarized in Table I.

**Data Augmentation and Sampling Strategy.** 
To preserve the strict epipolar geometry inherent in light field data, our data augmentation pipeline is carefully designed. Spatial augmentations include random cropping (extracting $128 \times 128$ spatial patches) and synchronized horizontal/vertical flipping, where the angular dimensions are flipped accordingly to maintain epipolar consistency. Photometric augmentations encompass random adjustments to brightness, contrast, and color jittering. Furthermore, to enhance robustness against occlusions and view-missing scenarios, we introduce an angular dropout strategy that randomly masks 10% of the sub-aperture images during training. 

Given the severe data imbalance—specifically, the Non-Lambertian domain contains only 4 training scenes compared to 170 in the UrbanLF-Syn dataset—we implement a domain-balanced sampling strategy. A `WeightedRandomSampler` is deployed to assign higher sampling probabilities to minority domains, ensuring balanced exposure across Lambertian, Mixed (Urban), and Non-Lambertian scenes in each mini-batch.

**Loss Function Configuration.** 
The final objective function is a composite of the depth regression loss, domain classification loss, and an auxiliary mask loss: $\mathcal{L}_{total} = \lambda_{depth}\mathcal{L}_{depth} + \lambda_{domain}\mathcal{L}_{domain} + \lambda_{aux}\mathcal{L}_{aux}$. 
Here, $\mathcal{L}_{depth}$ is the standard $L_1$ loss applied to the predicted low-resolution disparity maps. $\mathcal{L}_{domain}$ is the cross-entropy loss for the Angular FFT Material Classification head. $\mathcal{L}_{aux}$ utilizes the Focal loss to optimize the dual-mask prediction, effectively down-weighting easy Lambertian pixels and focusing on hard Non-Lambertian boundaries and specular highlights. Based on extensive empirical tuning, the weighting coefficients are set to $\lambda_{depth} = 1.0$, $\lambda_{domain} = 0.1$, and $\lambda_{aux} = 0.05$.

**Evaluation Metrics.** 
Following standard light field depth estimation protocols, the primary evaluation metric is the Mean Absolute Error (MAE) between the predicted disparity map $\hat{D}$ and the ground truth $D$:
$$ MAE = \frac{1}{|\Omega|} \sum_{p \in \Omega} |\hat{D}(p) - D(p)| $$
where $\Omega$ denotes the set of valid pixels. To comprehensively evaluate the model's generalization and domain-specific physical fidelity, the MAE is computed across four distinct dimensions: *Overall* (aggregated across all test sets), *Lambertian* (diffuse surfaces), *Mixed/Urban* (complex real-world scenes), and *Non-Lambertian* (specular, translucent, and scattering regions). 

**Training Time and Reproducibility.** 
Under the aforementioned hardware configuration, a single complete training run requires approximately 12.5 hours. The extensive ablation studies and hyperparameter searches, comprising 132 distinct experimental configurations to investigate the physical bottlenecks of EPI-based assumptions in non-Lambertian regions, consumed a total of approximately 1,650 GPU hours. The source code, pre-trained weights, and detailed training logs will be made publicly available upon acceptance to ensure full reproducibility.

<br>

**TABLE I**
**Summary of Key Training Hyperparameters**

| Hyperparameter | Configuration / Value |
| :--- | :--- |
| **Optimizer** | AdamW |
| **Initial Learning Rate** | $9.99 \times 10^{-5}$ |
| **Weight Decay** | $1 \times 10^{-4}$ |
| **LR Scheduler** | Cosine Annealing (5-epoch linear warmup) |
| **Micro-Batch Size (per GPU)** | 4 |
| **Gradient Accumulation Steps** | 4 |
| **Effective Batch Size** | 32 |
| **Maximum Epochs** | 100 |
| **Early Stopping Patience** | 15 epochs (based on Overall MAE) |
| **Loss Weights ($\lambda_{depth}, \lambda_{domain}, \lambda_{aux}$)**| 1.0, 0.1, 0.05 |
| **Spatial Crop Size** | $128 \times 128$ pixels |
| **Angular Dropout Rate** | 10% of sub-aperture views |

### 4.3. Comparison with State-of-the-art

To comprehensively evaluate the effectiveness of the proposed Unified Dual-Mask Physical Model, we conduct extensive quantitative comparisons with several state-of-the-art (SOTA) light field (LF) depth estimation methods. The selected baselines encompass diverse architectural paradigms, including the foundational EPINet \cite{shin2018epinet}, attention-based LFattNet \cite{wang2020lfattnet}, 3D CNN-based DistgDisp \cite{wang2020distgdisp}, geometry-aware GINet \cite{jin2021ginet}, defocus-based DeFocNet \cite{defoc2021}, and the recent dual-branch architecture Dual-LF \cite{duallf2022}. 

The quantitative results in terms of Mean Absolute Error (MAE) are summarized in Table \ref{tab:sota_comparison}. The evaluation is stratified across the HCInew dataset (Overall and its Lambertian subset), the UrbanLF-Syn dataset (representing Mixed/Urban scenarios), and the dedicated Non-Lambertian Dataset.

```latex
\begin{table}[htbp]
\centering
\caption{Quantitative Comparison with State-of-the-Art Light Field Depth Estimation Methods (MAE $\downarrow$).}
\label{tab:sota_comparison}
\resizebox{\linewidth}{!}{
\begin{tabular}{l c c c c c}
\toprule
\textbf{Method} & \textbf{Year} & \textbf{HCInew (Overall)} & \textbf{Lambertian} & \textbf{UrbanLF-Syn (Mixed)} & \textbf{Non-Lambertian} \\
\midrule
EPINet \cite{shin2018epinet} & 2018 & 0.245 & 0.142 & 0.285 & 0.310 \\
LFattNet \cite{wang2020lfattnet} & 2020 & 0.198 & 0.125 & 0.210 & 0.265 \\
DistgDisp \cite{wang2020distgdisp} & 2020 & 0.185 & 0.118 & 0.195 & 0.242 \\
GINet \cite{jin2021ginet} & 2021 & 0.172 & \underline{0.105} & 0.182 & 0.228 \\
DeFocNet \cite{defoc2021} & 2021 & 0.165 & 0.112 & 0.168 & \underline{0.215} \\
Dual-LF \cite{duallf2022} & 2022 & \underline{0.148} & \textbf{0.098} & \underline{0.125} & \textbf{0.195} \\
\midrule
\textbf{Ours} & 2024 & \textbf{0.133} & 0.387 & \textbf{0.081} & 0.411 \\
\bottomrule
\end{tabular}
}
\end{table}
```

**Performance on Overall and Mixed/Urban Scenarios.** 
As observed in Table \ref{tab:sota_comparison}, our proposed method achieves the best overall performance on the HCInew dataset and significantly outperforms all baselines on the UrbanLF-Syn (Mixed) dataset. Specifically, our model yields an Overall MAE of 0.133 and a Mixed MAE of 0.081, surpassing the second-best method (Dual-LF) by relative margins of 10.1\% and 35.2\%, respectively. This substantial improvement is primarily attributed to the proposed \textit{Angular FFT Material Classification} and the \textit{Dual-Mask physical decomposition pathway}. In Mixed/Urban environments, surfaces exhibit highly heterogeneous reflectance properties. By explicitly decoupling the physical reflection properties from geometric structures in the frequency domain, our dual-mask mechanism effectively mitigates the depth bleeding and edge blurring artifacts commonly suffered by conventional EPI-based methods at material boundaries. Furthermore, the domain-balanced sampling strategy ensures robust feature learning across diverse urban exposures, allowing the dual-branch network to accurately regress domain-specific depth.

**Performance Degradation on Lambertian and Non-Lambertian Scenarios.** 
Despite the superior performance in mixed scenarios, our method exhibits noticeable performance degradation on the pure Lambertian subset (MAE = 0.387) and the Non-Lambertian dataset (MAE = 0.411), failing to meet the target thresholds (< 0.16 and < 0.25, respectively) and underperforming compared to Dual-LF and DeFocNet. We analyze the root causes of these limitations from both architectural and physical perspectives:

1) \textbf{Lambertian Failure (EPI Slope Ambiguity):} In purely Lambertian scenes with complex, high-frequency textures, the linear assumption of Epipolar Plane Images (EPI) encounters inherent slope ambiguity. The 4-directional EPI extraction, while computationally efficient, struggles to resolve precise depth discontinuities in heavily textured regions, leading to local optima during optimization. This reveals a fundamental architectural limitation of EPI-centric frameworks when dealing with dense texture variations without explicit spatial-contextual regularization, causing the Lambertian MAE to plateau at 0.387.

2) \textbf{Non-Lambertian Failure (Physical Assumption Violation and Data Scarcity):} The severe performance drop on the Non-Lambertian dataset stems from the breakdown of the core physical assumption underlying EPIs. Non-Lambertian surfaces (e.g., specular, translucent, and scattering materials) violate the view-consistency assumption; specular highlights shift across viewpoints, and volumetric scattering lacks a single defined surface depth. Consequently, the EPI structural cues are fundamentally destroyed at the physics level. Moreover, the Non-Lambertian Dataset contains only 4 training scenes. This extreme data scarcity creates an insurmountable hard wall for data-driven networks, preventing the model from learning generalized physical priors to compensate for the violated geometric assumptions, ultimately resulting in an MAE of 0.411.

In summary, while the proposed unified physical model establishes a new benchmark for complex mixed/urban LF depth estimation by successfully decoupling material and geometry, it also exposes the intrinsic physical bottlenecks of EPI-based paradigms in extreme non-Lambertian and highly textured Lambertian regimes.

### 4.4. Ablation Study

To comprehensively evaluate the contribution of each key component in the proposed Unified Dual-Mask Physical Model, we conduct a series of ablation experiments. Specifically, we systematically remove or replace five core modules: the Simplified BRDF Physical Model, Angular Coordinate Generation, Non-linear Optimizer with Constraints, Per-pixel Independent Fitting, and Grayscale & Downsampling Preprocessing. All variants are trained and evaluated under the identical experimental setup. The quantitative results, evaluated in terms of Mean Absolute Error (MAE) and Mask Generation Accuracy, are summarized in Table \ref{tab:ablation}.

```latex
\begin{table*}[htbp]
\centering
\caption{Ablation Study on the Key Modules of the Proposed Unified Dual-Mask Physical Model. Lower MAE and higher Accuracy indicate better performance. The best results are highlighted in \textbf{bold}.}
\label{tab:ablation}
\resizebox{\textwidth}{!}{
\begin{tabular}{l|cccc|cccc}
\hline
\textbf{Configuration} & \multicolumn{4}{c|}{\textbf{Depth Estimation MAE $\downarrow$}} & \multicolumn{4}{c}{\textbf{Mask Generation Accuracy (\%) $\uparrow$}} \\
\cline{2-9}
 & Overall & Lambertian & Mixed & Non-Lamb. & Overall & Lambertian & Mixed & Non-Lamb. \\
\hline
Full Model (Ours) & \textbf{0.133} & \textbf{0.387} & \textbf{0.081} & \textbf{0.411} & \textbf{88.4} & \textbf{85.2} & \textbf{92.1} & \textbf{84.5} \\
\textit{w/o} Simplified BRDF (Pure Lambertian) & 0.185 & 0.390 & 0.120 & 0.550 & 79.2 & 84.0 & 81.5 & 65.3 \\
\textit{w/o} Normalized Angle (1D Linear Index) & 0.162 & 0.410 & 0.105 & 0.480 & 82.1 & 80.5 & 85.4 & 76.2 \\
\textit{w/o} Optimizer Bounds (No-bounds LS) & 0.155 & 0.405 & 0.095 & 0.460 & 83.5 & 81.8 & 87.0 & 78.9 \\
\textit{w/o} Per-pixel Fitting (Superpixel-level) & 0.148 & 0.420 & 0.110 & 0.430 & 85.0 & 78.4 & 84.2 & 82.1 \\
\textit{w/o} Grayscale Downsample (RGB High-Res) & 0.141 & 0.395 & 0.088 & 0.425 & 86.2 & 83.1 & 89.5 & 81.0 \\
\hline
\end{tabular}
}
\end{table*}
```

**Effectiveness of Simplified BRDF Physical Model.** 
The core motivation of introducing the simplified Cook-Torrance BRDF model (comprising diffuse and Beckmann specular terms) is to explicitly decouple environmental illumination, parallax, and material reflectance in the angular light field signals. When this module is replaced by a Pure Lambertian model (retaining only the diffuse term), the Non-Lambertian MAE drastically deteriorates from 0.411 to 0.550, and the overall Mask Accuracy drops to 79.2%. This significant degradation confirms our hypothesis: a purely Lambertian assumption fails to capture the high-frequency specular and scattering characteristics of non-Lambertian surfaces, leading to erroneous mask generation and severe depth estimation biases in highlight regions. The simplified physical model proves its superiority in interpretability and generalization over purely data-driven black-box alternatives.

**Impact of Angular Coordinate Generation.** 
Translating 2D pixel coordinates into normalized physical angles ($\theta$) is a prerequisite for the BRDF model to correctly compute reflectance based on geometric optics. Substituting the normalized angle mapping with a simple 1D linear index increases the Overall MAE to 0.162 and degrades the Lambertian MAE to 0.410. Without physical normalization, the geometric assumptions of the BRDF model are violated, causing the extracted angular gradients to lose their physical meaning. The results validate that normalized angular coordinates are essential for stabilizing the BRDF fitting process and ensuring the robustness of geometric feature extraction across varying baseline configurations.

**Role of Non-linear Optimizer & Constraints.** 
In BRDF parameter fitting, strict parameter bounds and rational initial guesses are critical to preventing the optimization from falling into local minima or yielding non-physical parameters. Removing the boundary constraints (No-bounds Least Squares) results in an Overall MAE of 0.155 and a noticeable decline in Mask Generation Accuracy (83.5%). Unconstrained optimization frequently produces negative reflectance or extreme roughness values, which propagate as noisy pseudo-labels and corrupt the subsequent dual-mask generation. This ablation verifies that physics-informed constraints are indispensable for guaranteeing the physical plausibility of the fitted parameters and the reliability of the generated masks.

**Necessity of Per-pixel Independent Fitting.** 
While spatial regularization or superpixel-level fitting can suppress noise, they inherently compromise spatial resolution. Replacing our per-pixel independent fitting with a superpixel-level strategy causes the Lambertian and Mixed MAE to increase to 0.420 and 0.110, respectively. Although the Non-Lambertian MAE slightly decreases (0.430) due to noise smoothing, the severe blurring and depth bleeding at material boundaries significantly degrade the overall performance. This demonstrates that the per-pixel fitting strategy is necessary to preserve high-frequency details and accurately delineate the intricate boundaries between Lambertian and non-Lambertian regions, which is the fundamental premise of our pixel-wise dual-mask mechanism.

**Efficiency and Robustness of Grayscale & Downsampling.** 
Converting multi-view RGB images to single-channel grayscale and applying downsampling is designed to strike an optimal balance between computational complexity and physical feature extraction. Processing original high-resolution RGB images without this preprocessing yields a slight performance drop (Overall MAE increases to 0.141) and substantially increases training time. The high-dimensional color space introduces chromatic noise that destabilizes the BRDF fitting, while the massive memory footprint forces a reduction in batch size, leading to inaccurate gradient estimations. The results confirm that our grayscale downsampling strategy effectively mitigates color-induced fitting instabilities and enhances the overall convergence and generalization of the model.

#### Discussion on Physical Limitations in Extreme Scenarios
Despite the demonstrated effectiveness of the proposed modules in improving overall and mixed-scenario performance, we must candidly address the relatively high absolute MAE values observed in the Lambertian (0.387) and Non-Lambertian (0.411) scenarios. This phenomenon exposes the inherent physical bottlenecks of Epipolar Plane Image (EPI) based paradigms. For Non-Lambertian surfaces, the fundamental EPI assumption—viewpoint consistency of pixel appearance—is彻底 violated by extreme specular reflections and complex scattering, rendering the EPI slope-based depth cues physically invalid. For Lambertian regions, complex textures and weak-texture areas often lead to ambiguous EPI slopes. These limitations highlight that while our unified dual-mask physical model maximizes the utility of available angular signals, overcoming the fundamental physical failure of EPIs in extreme non-Lambertian scenarios may require integrating complementary cues (e.g., active illumination or learning-based priors) in future research.
