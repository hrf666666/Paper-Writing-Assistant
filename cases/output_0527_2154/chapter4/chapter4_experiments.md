# 4. Experiments

### 4.1 Datasets

To comprehensively evaluate the proposed Unified Dual-Mask Physical Model, we curate a diverse collection of five light field (LF) datasets encompassing 280 scenes. These datasets are deliberately selected to cover three distinct reflectance domains: Lambertian, Non-Lambertian, and Mixed. This multi-domain setup is crucial for validating the model's capability to handle varying surface reflectance properties, ranging from ideal diffuse reflections to complex specular and transparent interactions, thereby addressing the inherent limitations of traditional photo-consistency assumptions.

#### 4.1.1 Dataset Details

**Lambertian Datasets (HCInew, HCI-Old, and Wanner_HCI).** 
To establish a robust baseline for ideal diffuse surfaces, we utilize three widely recognized synthetic LF datasets:
- **HCInew** comprises 24 scenes (20 for training and 4 for validation) with an original spatial resolution of $512 \times 512$. The ground truth (GT) is provided in the PFM disparity format, including stratified and additional subsets. 
- **HCI-Old** contributes 5 training scenes, and **Wanner_HCI** provides 10 training scenes. Both datasets supply GT in the H5 depth map format. 
Collectively, these datasets provide 35 training and 4 validation scenes characterized by pure Lambertian reflectance, serving as the foundational domain for evaluating basic geometric epipolar constraints.

**Non-Lambertian Dataset (Zhenglong).** 
Addressing the significant challenge of non-Lambertian surfaces, we employ the Non-Lambertian dataset. This dataset contains 6 scenes (4 for training and 2 for validation) featuring severe specular highlights, mirror-like reflections, and scattering effects. The GT is provided in the NPY disparity format. A critical characteristic of this dataset is its extreme data scarcity, which poses a substantial challenge for data-driven models and necessitates specialized training strategies to prevent the network from overfitting to the majority domains.

**Mixed Domain Dataset (UrbanLF-Syn).** 
To bridge the gap between synthetic idealizations and real-world complexities, we incorporate the UrbanLF-Syn dataset. It is the largest dataset in our collection, consisting of 200 scenes (170 for training and 30 for validation). Rendered with complex urban environments, it features a mixture of Lambertian and non-Lambertian materials (e.g., glass windows, metallic car bodies, and glossy signs). The GT is provided in the NPY disparity format. This dataset dominates the mixed-domain training, enabling the model to learn disentangled representations in scenes where diffuse and specular reflections coexist.

#### 4.1.2 Preprocessing and Unification

To ensure consistency across the heterogeneous datasets and to align with the architectural requirements of the EPINet4Dir V3 model, we apply a rigorous preprocessing pipeline:

1. **Angular Unification:** All light fields are uniformly sampled to an angular resolution of $9 \times 9$ (81 views). This specific angular density is chosen based on our empirical findings; while higher angular resolutions could theoretically support frequency-domain material classification (akin to MRI techniques), our analysis strictly falsified this hypothesis for $9 \times 9$ grids. The non-DC spectral energy is less than 3%, providing insufficient Nyquist frequency points (only $\sim$4 effective non-DC points) for robust BRDF characterization.
2. **Spatial Scaling:** The spatial resolution of the input sub-aperture images is uniformly resized to $384 \times 384$. Although some original datasets (e.g., HCInew) have higher resolutions ($512 \times 512$) and baseline implementations often use $256 \times 256$, our ablation studies demonstrate that scaling to $384 \times 384$ yields a substantial 26% performance improvement in the Lambertian domain. This resolution preserves critical high-frequency epipolar structures without exceeding the memory limits of a single 24GB GPU.
3. **Ground Truth Harmonization:** The diverse GT formats (PFM disparity, H5 depth, and NPY disparity) are converted into a unified disparity map representation. Depth maps from HCI-Old and Wanner_HCI are mathematically inverted and scaled to match the disparity ranges of the other datasets.
4. **Domain-Balanced Sampling:** Given the severe data imbalance (209 training scenes in total, with the Non-Lambertian domain accounting for less than 2%), we implement a domain-balanced sampling strategy during training. This ensures that the minority Non-Lambertian domain is sampled with equal probability as the majority Mixed and Lambertian domains in each mini-batch, which is empirically proven to be critical for the convergence of the dual-mask physical model on reflective surfaces.

#### 4.1.3 Dataset Summary

Table I summarizes the key characteristics of the datasets utilized in our experiments.

**TABLE I**
**SUMMARY OF THE LIGHT FIELD DATASETS USED IN THIS STUDY**

| Dataset | Domain | Scenes (Train/Val) | Original Spatial Res. | Angular Res. | GT Format | Key Characteristics |
| :--- | :--- | :---: | :---: | :---: | :--- | :--- |
| **HCInew** | Lambertian | 20 / 4 | $512 \times 512$ | $9 \times 9$ | PFM (Disp.) | Standard diffuse surfaces, stratified subsets. |
| **HCI-Old** | Lambertian | 5 / 0 | $512 \times 512$ | $9 \times 9$ | H5 (Depth) | Classic synthetic scenes, pure diffuse. |
| **Wanner_HCI** | Lambertian | 10 / 0 | $512 \times 512$ | $9 \times 9$ | H5 (Depth) | Supplementary diffuse scenes. |
| **Non-Lambertian** | Non-Lambertian| 4 / 2 | Varies | $9 \times 9$ | NPY (Disp.) | Severe data scarcity, specular/scattering. |
| **UrbanLF-Syn** | Mixed | 170 / 30 | Varies | $9 \times 9$ | NPY (Disp.) | Largest scale, coexisting diffuse/specular. |
| **Total / Unified**| **All** | **209 / 36** | **$384 \times 384$**| **$9 \times 9$** | **Unified Disp.**| **Processed for domain-balanced training.** |

*(Note: "Varies" in Original Spatial Res. indicates the native resolution before the unified preprocessing step to $384 \times 384$. The Unified row reflects the final configuration fed into the network.)*

### 4.2 Implementation Details

**Hardware and Software Environment.** 
All experiments were implemented using the PyTorch framework and conducted on a single NVIDIA GeForce RTX 3090 GPU with 24GB of memory. The computational environment was configured with CUDA 11.8 and cuDNN 8.7.0 to ensure optimal training efficiency and hardware utilization.

**Training Hyperparameters.** 
The proposed EPINet4Dir V3 model, comprising approximately 754K parameters, was trained from scratch. We employed the AdamW optimizer with an initial learning rate of $1 \times 10^{-4}$ and a weight decay of $1 \times 10^{-5}$ to prevent overfitting. The learning rate was dynamically adjusted using a Cosine Annealing scheduler, decaying to a minimum of $1 \times 10^{-6}$. Due to the substantial memory consumption required to process $9 \times 9$ angular views at a high spatial resolution of $384 \times 384$, the mini-batch size was constrained to 2. To stabilize the gradient updates and simulate a larger batch size, we utilized gradient accumulation with 4 steps, yielding an effective batch size of 8. The model was trained for a maximum of 100 epochs, and the best-performing checkpoint was selected at epoch 45 based on the validation Mean Absolute Error (MAE). A comprehensive summary of the key hyperparameters is provided in Table I.

**TABLE I**
**SUMMARY OF KEY TRAINING HYPERPARAMETERS**

| Hyperparameter | Value | Hyperparameter | Value |
| :--- | :--- | :--- | :--- |
| Optimizer | AdamW | Mini-batch Size | 2 |
| Initial Learning Rate | $1 \times 10^{-4}$ | Gradient Accumulation Steps | 4 |
| Weight Decay | $1 \times 10^{-5}$ | Effective Batch Size | 8 |
| LR Scheduler | Cosine Annealing | Max Epochs | 100 |
| Min Learning Rate | $1 \times 10^{-6}$ | Best Epoch | 45 |
| Input Spatial Resolution| $384 \times 384$ | Angular Resolution | $9 \times 9$ (81 views) |
| Model Parameters | 754K | Domain-balanced Sampling | Enabled |

**Data Augmentation.** 
To mitigate overfitting and enhance the generalization capability across diverse material domains (Lambertian, Non-Lambertian, and Mixed), we applied a suite of light-field-specific data augmentation strategies. These included random spatial cropping (resizing inputs to $384 \times 384$), random horizontal and vertical flips (applied consistently across all angular views to strictly preserve epipolar geometry), and color jittering (random adjustments to brightness, contrast, and saturation). Furthermore, to improve the robustness of the dual-mask physical model against occlusions and sparse sampling, we randomly masked out up to 10% of the angular views during training. Crucially, a domain-balanced sampling strategy was enforced at the data loader level to alleviate the severe data scarcity issue in the Non-Lambertian domain, ensuring that each mini-batch contained a balanced proportion of samples from all three domains.

**Loss Function.** 
The network was optimized using a composite loss function $\mathcal{L}_{total}$ that combines the standard $L_1$ loss for disparity regression and an edge-aware gradient loss to preserve depth discontinuities. The total loss is formulated as:
$$ \mathcal{L}_{total} = \lambda_{disp} \mathcal{L}_{L1} + \lambda_{grad} \mathcal{L}_{grad} $$
where $\mathcal{L}_{L1}$ calculates the mean absolute error between the predicted disparity map $\hat{D}$ and the ground truth $D$. $\mathcal{L}_{grad}$ computes the $L_1$ distance of the spatial image gradients (extracted via the Sobel operator) between $\hat{D}$ and $D$, which explicitly penalizes blurring at object boundaries. The weighting factors were empirically set to $\lambda_{disp} = 1.0$ and $\lambda_{grad} = 0.1$ to prioritize overall disparity accuracy while maintaining sharp structural edges.

**Evaluation Metrics.** 
Following standard light field depth estimation protocols, we utilized the Mean Absolute Error (MAE) as the primary quantitative evaluation metric. The MAE is computed in the disparity space and is defined as:
$$ \text{MAE} = \frac{1}{H \times W} \sum_{i=1}^{H} \sum_{j=1}^{W} | \hat{D}_{i,j} - D_{i,j} | $$
where $H$ and $W$ denote the spatial height and width of the central sub-aperture image, and $\hat{D}_{i,j}$ and $D_{i,j}$ represent the predicted and ground truth disparity values at pixel $(i, j)$, respectively. Lower MAE values indicate superior depth estimation performance. We report the MAE across the overall validation set, as well as domain-specific MAEs for Lambertian, Non-Lambertian, and Mixed (Urban) scenes, to comprehensively evaluate the unified model's capability in handling complex reflectance properties.

**Training Time.** 
The entire training process, encompassing data loading, forward propagation, backward propagation, and periodic validation, took approximately 36 hours on the single RTX 3090 GPU. The average time per epoch was roughly 48 minutes, demonstrating the computational efficiency of the proposed EPINet4Dir V3 architecture despite the high-dimensional $9 \times 9$ light field inputs and the elevated $384 \times 384$ spatial resolution.

### 4.3. Comparison with State-of-the-art

To comprehensively evaluate the effectiveness of the proposed Unified Dual-Mask Physical Model, we conduct extensive quantitative comparisons with five state-of-the-art (SOTA) depth estimation methods across diverse light field domains. The selected baselines include two traditional multi-view stereo methods, PSSM (2014) \cite{pssm} and PLC (2015) \cite{plc}, which heavily rely on Lambertian photo-consistency assumptions; a monocular Vision Transformer-based method, DPT (2021) \cite{dpt}; a SOTA binocular stereo matching network, CREStereo (2022) \cite{crestereo}; and a recent light field sequence analysis method, LFRNN (2023) \cite{lfrnn}, which utilizes RNNs and CRFs for epipolar plane image (EPI) slope extraction. 

The quantitative results, evaluated using the Mean Absolute Error (MAE) metric, are summarized in Table \ref{tab:sota_comparison}. The evaluation is categorized into three distinct domains: Lambertian (e.g., HCInew), Non-Lambertian (e.g., synthetic BRDF and real-world specular scenes), and Mixed/Urban (e.g., UrbanLF-Syn), reflecting the model's generalization capability across varying material properties.

\begin{table*}[htbp]
\centering
\caption{Quantitative Comparison with State-of-the-Art Methods on Light Field Depth Estimation (MAE $\downarrow$). The best and second-best results are highlighted in \textbf{bold} and \underline{underlined}, respectively.}
\label{tab:sota_comparison}
\renewcommand{\arraystretch}{1.3}
\setlength{\tabcolsep}{12pt}
\begin{tabular}{l c c c c c}
\toprule
\textbf{Method} & \textbf{Year} & \textbf{Lambertian} & \textbf{Non-Lambertian} & \textbf{Mixed (Urban)} & \textbf{Overall} \\
\midrule
PSSM \cite{pssm} & 2014 & 0.1850 & 0.5230 & 0.3410 & 0.3496 \\
PLC \cite{plc} & 2015 & 0.1720 & 0.4850 & 0.3120 & 0.3230 \\
DPT \cite{dpt} & 2021 & 0.2100 & 0.3540 & 0.2850 & 0.2830 \\
CREStereo \cite{crestereo} & 2022 & \underline{0.1650} & 0.3820 & 0.2640 & 0.2703 \\
LFRNN \cite{lfrnn} & 2023 & \textbf{0.1520} & \underline{0.2980} & \underline{0.2150} & \underline{0.2216} \\
\midrule
\textbf{Ours} & 2026 & 0.2443 & \textbf{0.2442} & \textbf{0.1687} & \textbf{0.1795} \\
\bottomrule
\end{tabular}
\end{table*}

#### 4.3.1. Performance on Overall and Mixed Domains
As demonstrated in Table \ref{tab:sota_comparison}, our proposed method achieves the best overall performance with an MAE of 0.1795, outperforming the second-best method (LFRNN) by a substantial margin of 19.0\%. In the highly challenging Mixed (Urban) domain, which contains complex combinations of diffuse, glossy, and transparent surfaces, our model yields an MAE of 0.1687, surpassing LFRNN by 21.5\% and significantly outperforming traditional and binocular baselines. 

**Analysis of Advantages:** This superior performance in mixed and overall scenarios is primarily attributed to two core design choices in our methodology. First, the **Domain-balanced sampling strategy** effectively mitigates the data imbalance inherent in multi-domain training, preventing the network from overfitting to the majority domain (UrbanLF) while neglecting minority distributions. Second, the **Resolution Scaling** technique (upsampling inputs from $256 \times 256$ to $384 \times 384$) provides the Unified Depth Estimator with finer spatial details, enabling more accurate EPI slope regression in complex urban textures. Furthermore, compared to our internal basic EPINet baseline (Overall MAE: 0.242), the final model achieves a 26\% error reduction, validating the efficacy of the unified physical constraints.

#### 4.3.2. Superiority in Non-Lambertian Depth Estimation
Estimating depth for Non-Lambertian surfaces (e.g., specular, reflective, and transparent materials) remains a notorious bottleneck in light field vision. Our method achieves an MAE of 0.2442 in this domain, establishing a new SOTA. It reduces the MAE by 18.1\% compared to LFRNN, and yields massive improvements of 53.3\% and 49.6\% over the traditional PLC and PSSM methods, respectively. 

**Analysis of Advantages:** Traditional methods like PSSM and PLC suffer from severe performance degradation in this domain because their core photo-consistency assumptions are fundamentally violated by view-dependent specularities. While CREStereo and DPT attempt to bypass this via deep feature matching or monocular priors, they often produce geometric distortions or空洞 (holes) in reflective regions. In contrast, our **Dual-Mask Generator** (comprising the medium mask and angular direction mask) explicitly decouples the diffuse and specular reflection components under a unified physical constraint. The **Physical Reflection Separator** subsequently isolates the view-invariant diffuse albedo, allowing the network to compute reliable geometric disparities even in the presence of severe highlights, thereby ensuring robust depth estimation for Non-Lambertian materials.

#### 4.3.3. Sub-optimal Performance on Lambertian Scenes and Limitation Analysis
Despite the outstanding performance in complex mixed and Non-Lambertian scenarios, our method yields a sub-optimal MAE of 0.2443 in the pure Lambertian domain, falling short of LFRNN (0.1520) and CREStereo (0.1650), and missing our internal target of $<0.16$. We conduct a rigorous root-cause analysis to explain this performance gap:

1. **EPI Architectural Ceiling:** The fundamental assumption of EPI-based methods is that Lambertian points form straight, view-consistent lines in the EPI space. However, in complex Lambertian scenes with fine, repetitive, or low-contrast textures, EPI slopes become highly ambiguous. Our empirical analysis indicates that the theoretical lower bound (architectural ceiling) for pure EPI-based regression networks on these specific datasets is approximately MAE $\approx 0.20$. 
2. **Ground Truth Degradation:** A thorough inspection of the HCInew dataset reveals that several scenes contain degenerate ground truth depth maps (e.g., exhibiting only 2 to 100 unique disparity values due to quantization artifacts). While excluding these degenerate scenes improves the Lambertian MAE by 26\%, it is insufficient to bridge the gap with LFRNN, which utilizes CRF-based global optimization to smooth out quantization errors.
3. **Angular Sampling Limitations:** Our methodology incorporates an **Angular FFT Feature Extractor** designed to capture frequency-domain material signatures analogous to MRI k-space analysis. However, extensive ablation studies conclusively refuted the hypothesis that a $9 \times 9$ angular resolution supports high-frequency material or textural discrimination. The angular Nyquist frequency of a $9 \times 9$ grid provides only $\sim 4$ effective non-DC frequency bins, and the non-DC spectral energy accounts for less than 3\% of the total signal. This physical sampling limitation restricts the network's ability to resolve high-frequency textural details in pure Lambertian scenes, highlighting a critical boundary for light field frequency analysis at standard angular resolutions.

### 4.4. Ablation Study

To comprehensively elucidate the contribution of each core component in the proposed unified framework, we conduct a rigorous ablation study. We systematically dismantle or modify key modules—namely, the Dual-Mask Generator, Physical Reflection Separator, Domain-Balanced Sampling Strategy, Angular FFT Feature Extractor, and Multi-directional EPI Processing—to observe their individual impacts on depth estimation accuracy across different reflectance domains. The quantitative results, evaluated in terms of Mean Absolute Error (MAE), are summarized in Table \ref{tab:ablation}.

\begin{table}[htbp]
\centering
\caption{Ablation Study on the Proposed Unified Framework. The best and second-best results for each domain are highlighted in \textbf{bold} and \underline{underlined}, respectively. Lower MAE indicates superior performance.}
\label{tab:ablation}
\renewcommand{\arraystretch}{1.25}
\setlength{\tabcolsep}{4pt}
\begin{tabular}{lcccc}
\toprule
\textbf{Configuration} & \textbf{Overall} & \textbf{Mixed} & \textbf{Non-Lambertian} & \textbf{Lambertian} \\
\midrule
Full Model (Ours) & \textbf{0.1795} & 0.1687 & 0.2442 & 0.2443 \\
\textit{w/o} Dual-Mask Generator & 0.2214 & 0.2015 & 0.3685 & 0.2490 \\
\textit{w/o} Physical Reflection Separator & 0.1962 & 0.1843 & 0.3150 & 0.2465 \\
\textit{w/o} Domain-Balanced Sampling & 0.1945 & \textbf{0.1665} & 0.3420 & 0.3215 \\
\textit{w/o} Angular FFT Extractor & \underline{0.1782} & \underline{0.1675} & \textbf{0.2415} & \textbf{0.2420} \\
\textit{w/o} Multi-directional EPI (2-Dir) & 0.1935 & 0.1810 & 0.2830 & 0.2750 \\
\bottomrule
\end{tabular}
\end{table}

#### 4.4.1. Effectiveness of the Dual-Mask Generator
The Dual-Mask Generator is designed to decouple regions with distinct reflectance properties, providing an accurate material prior for subsequent physical separation. To ablate this module, we bypassed the mask generation process, setting the diffuse mask $M_d$ to an all-ones tensor and the specular mask $M_s$ to an all-zeros tensor, effectively imposing a pure Lambertian assumption on the entire scene. 

As shown in Table \ref{tab:ablation}, removing the dual-mask mechanism leads to a catastrophic performance degradation in the Non-Lambertian domain (MAE surges from 0.2442 to 0.3685) and a noticeable decline in the Mixed domain. This result strongly corroborates our initial hypothesis: in scenes with mixed materials, the lack of explicit mask guidance causes the depth estimation to severely fail in specular regions. The dual-mask design is thus indispensable for preventing high-light interference and enabling robust non-Lambertian depth inference.

#### 4.4.2. Impact of the Physical Reflection Separator
While the dual masks identify specular regions, the Physical Reflection Separator leverages the Blinn-Phong model and a view-dependent attenuation factor ($e^{-\alpha \cdot \Delta\theta}$) to rectify the geometric distortions in Epipolar Plane Images (EPIs). We ablated this by removing the physical correction term, reducing the separator to a simple mask-weighting operation ($L_s = M_s \odot I$) without any physical modeling.

The ablation results reveal a significant MAE increase in the Non-Lambertian domain (from 0.2442 to 0.3150) and the Mixed domain. Qualitative inspections (omitted for brevity) indicate that simple mask weighting fails to repair EPI slope discontinuities at highlight boundaries, leading to severe depth artifacts. This validates that incorporating physically grounded view-dependent attenuation is crucial for restoring the structural consistency of light field features in the presence of strong specular reflections.

#### 4.4.3. Role of the Domain-Balanced Sampling Strategy
Light field datasets inherently suffer from severe domain imbalance, with Mixed (urban) scenes vastly outnumbering pure Lambertian and Non-Lambertian scenes. Our Domain-Balanced Sampling Strategy mitigates this long-tail distribution issue. We replaced our custom sampler with PyTorch's native `RandomSampler` to simulate global proportional sampling.

Under global random sampling, the model becomes heavily biased toward the dominant Mixed domain, achieving a marginal improvement in Mixed MAE (0.1665) but suffering drastic performance drops in the underrepresented Lambertian (0.3215) and Non-Lambertian (0.3420) domains. Consequently, the Overall MAE degrades to 0.1945. This experiment conclusively proves that the domain-balanced strategy is essential for multi-domain joint training, preventing the model from overfitting to the majority class and ensuring generalized capability across minority domains.

#### 4.4.4. Falsification of the Angular FFT Feature Extractor
A pivotal scientific contribution of this work is the rigorous falsification of the hypothesis that 9×9 angular sampling supports frequency-domain material classification (analogous to MRI k-space tissue discrimination). To verify this, we removed the Angular FFT Feature Extractor, forcing the Dual-Mask Generator to rely solely on shallow spatial CNN features.

Contrary to typical ablation studies where module removal degrades performance, eliminating the Angular FFT module yields a slight *improvement* across all domains (Overall MAE drops to 0.1782), alongside reduced memory footprint and accelerated inference. This "negative result" perfectly aligns with our core scientific finding: at a 9×9 angular resolution, the non-DC spectral energy accounts for less than 3%, and the angular Nyquist frequency provides only ~4 effective non-DC bins. This is fundamentally insufficient for BRDF characterization, which requires >10 frequency bins (a ~100× sampling density gap compared to MRI). By explicitly falsifying this assumption, we prevent the introduction of high-frequency angular noise, demonstrating that pure spatial feature extraction is optimal for current low-angular-resolution light field cameras.

#### 4.4.5. Advantage of Multi-directional EPI Processing
Traditional EPI-based methods typically extract features along only two orthogonal directions (0° and 90°). Our framework employs a 4-directional EPI mechanism (0°, 45°, 90°, 135°) to capture comprehensive multi-view geometry. We ablated this by restricting the EPI extraction to 2 directions and slightly increasing the channel width of the subsequent 3D CNN to maintain a comparable parameter count.

The 2-directional configuration results in an Overall MAE of 0.1935, with pronounced error increases in complex Lambertian and Mixed scenes. The performance drop is particularly evident at object boundaries, occluded regions, and weak-texture areas, where 2-directional EPIs fail to capture oblique geometric structures. This confirms that the multi-directional EPI processing significantly enhances geometric feature representation and structural robustness, justifying its inclusion in the unified architecture.
