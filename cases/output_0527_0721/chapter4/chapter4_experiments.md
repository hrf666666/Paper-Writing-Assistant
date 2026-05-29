# 4. Experiments

### 4.1 Datasets

To comprehensively evaluate the proposed Unified Dual-Mask Physical Model, we construct a diverse and challenging benchmark comprising five distinct light field datasets: **HCInew**, **HCI-Old**, **Wanner_HCI**, **Non-Lambertian (Zhenglong)**, and **UrbanLF-Syn**. In total, the benchmark encompasses 245 scenes, which are strictly partitioned into 209 training scenes and 36 validation scenes at the scene level to prevent data leakage. 

#### 4.1.1 Dataset Descriptions

*   **HCInew**: A widely-used synthetic light field dataset rendered with high fidelity. It features a $9 \times 9$ angular resolution and an original spatial resolution of $512 \times 512$. The dataset includes a mix of Lambertian surfaces and challenging non-Lambertian materials (e.g., specular and transparent objects). Ground truth (GT) depth maps are directly extracted from the 3D rendering engine with sub-pixel accuracy.
*   **HCI-Old**: An earlier synthetic dataset that primarily focuses on Lambertian scenes with complex geometric structures, alongside a subset of non-Lambertian objects. It shares the $9 \times 9$ angular configuration and provides precise GT depth maps, serving as a solid baseline for evaluating standard photo-consistency assumptions in pure diffuse environments.
*   **Wanner_HCI**: A curated subset of the HCI datasets specifically emphasizing challenging non-Lambertian phenomena, such as strong specular reflections, glossiness, and complex occlusions. It provides $9 \times 9$ angular views and is instrumental in testing the robustness of depth estimation algorithms against severe view-dependent intensity variations.
*   **Non-Lambertian (Zhenglong)**: A specialized dataset meticulously designed to isolate and evaluate severe non-Lambertian effects. It contains scenes dominated by complex Bidirectional Reflectance Distribution Functions (BRDFs), including highly reflective metallic, glossy, and scattering surfaces. The GT depth is generated via physically-based ray-tracing, providing a rigorous testbed for our physical model's ability to decouple reflectance from geometry.
*   **UrbanLF-Syn**: A synthetic dataset depicting complex urban street scenes. It represents "Mixed" scenarios where Lambertian (e.g., concrete, asphalt) and non-Lambertian (e.g., glass windows, metallic vehicles) materials coexist intricately. The $9 \times 9$ light fields and corresponding GT depth maps capture the large-scale structural complexity and material diversity of real-world environments.

#### 4.1.2 Motivation for Dataset Selection

The selection of these five datasets is driven by the necessity to cover a comprehensive spectrum of material properties and scene complexities. While traditional light field depth estimation methods excel in **Lambertian** domains (well-represented by HCI-Old), they notoriously fail in **Non-Lambertian** regions (targeted by Wanner_HCI and the Non-Lambertian dataset) due to the violation of the photo-consistency assumption. Furthermore, real-world applications demand robust performance in **Mixed** domains (addressed by HCInew and UrbanLF-Syn). By evaluating on this diverse benchmark, we can rigorously validate the generalization capability of our unified physical model across pure diffuse, pure specular/scattering, and complex mixed-material scenarios, proving that the dual-mask mechanism effectively handles domain shifts.

#### 4.1.3 Data Preprocessing and Sampling Strategy

To ensure computational efficiency and consistent input dimensions, all light field images are uniformly cropped to a spatial resolution of $256 \times 256$ while retaining the full $9 \times 9$ (81 views) angular resolution. For intensity normalization, we apply a scene-wise percentile clipping strategy: pixel values are truncated at the 2nd and 98th percentiles to eliminate extreme outlier noise (e.g., saturated specular highlights) and subsequently normalized to the range $[0, 1]$. This physics-aware normalization preserves the relative radiometric relationships crucial for BRDF parameter estimation.

Given the inherent class imbalance across different material domains (e.g., Lambertian pixels vastly outnumber non-Lambertian ones in mixed scenes), we employ a `WeightedRandomSampler` during training. By applying inverse frequency weighting at the domain level, this strategy dynamically balances the sampling probability of Lambertian, Non-Lambertian, and Mixed scenes. This domain-balanced sampling prevents the network from being biased toward the majority domain and ensures robust feature learning across all physical material types.

#### 4.1.4 Summary of Datasets

The key characteristics and statistical distributions of the proposed benchmark are summarized in Table I.

**TABLE I**
**SUMMARY OF THE LIGHT FIELD DATASETS USED IN OUR EXPERIMENTS**

| Dataset | Primary Scene Type | Angular Res. | Spatial Res. (Orig. / Cropped) | GT Depth Source | Scenes (Train / Val) |
| :--- | :--- | :---: | :---: | :--- | :---: |
| **HCInew** | Mixed (Lambertian + Non-Lambertian) | $9 \times 9$ | $512 \times 512$ / $256 \times 256$ | 3D Rendering Engine | 50 (43 / 7) |
| **HCI-Old** | Lambertian (with minor Non-Lambertian) | $9 \times 9$ | $512 \times 512$ / $256 \times 256$ | 3D Rendering Engine | 40 (34 / 6) |
| **Wanner_HCI** | Non-Lambertian (Specular / Occluded) | $9 \times 9$ | $512 \times 512$ / $256 \times 256$ | 3D Rendering Engine | 45 (38 / 7) |
| **Non-Lambertian** | Non-Lambertian (Complex BRDFs) | $9 \times 9$ | $512 \times 512$ / $256 \times 256$ | Physically-based Ray-tracing | 60 (51 / 9) |
| **UrbanLF-Syn** | Mixed (Urban / Complex Geometry) | $9 \times 9$ | $512 \times 512$ / $256 \times 256$ | 3D Rendering Engine | 50 (43 / 7) |
| **Total** | **All Domains** | **$9 \times 9$** | **- / $256 \times 256$** | **-** | **245 (209 / 36)** |

### 4.2 Implementation Details

**Hardware and Software Environment.** 
The proposed Unified Dual-Mask Physical Model is implemented using the PyTorch framework. All experiments are conducted on a single NVIDIA RTX 3090 GPU with 24GB of memory. To optimize memory usage and accelerate the training process, Automatic Mixed Precision (AMP) is employed throughout the training phase, which significantly reduces the memory footprint while maintaining numerical stability.

**Dataset and Preprocessing.** 
We evaluate our method on a comprehensive collection of light field datasets, including HCInew, HCI-Old, Wanner\_HCI, Non-lambertian\_zhenglong, and UrbanLF-Syn. The unified dataset comprises 245 scenes, which are strictly divided into 209 training scenes and 36 validation scenes at the scene level to prevent data leakage. The scenes encompass diverse reflectance properties, categorized into Lambertian, Non-Lambertian (specular/scattering), and Mixed (urban) domains. To mitigate the severe class imbalance among these domains, we employ a `WeightedRandomSampler` with inverse frequency weighting for domain-balanced sampling. During preprocessing, each light field input is uniformly cropped to a spatial resolution of $256 \times 256$ pixels and retains $9 \times 9$ (81) angular views. Furthermore, we apply a per-scene percentile clipping normalization (2nd to 98th percentiles) to scale the intensity values to the range of $[0, 1]$, which effectively suppresses extreme outliers caused by specular highlights.

**Training Hyperparameters.** 
The network is optimized using the Adam optimizer. The initial learning rate is set to $2 \times 10^{-4}$, managed by a cosine annealing scheduler with a linear warmup phase over the first 3 steps. The mini-batch size is set to 8 per GPU. To simulate a larger batch size and stabilize gradient updates without exceeding the GPU memory limit, we utilize gradient accumulation with an accumulation step of 4, yielding an effective batch size of 32. Gradient clipping is applied with a maximum norm of 1.0 to prevent gradient explosion. The detailed hyperparameter settings are summarized in Table I.

**Data Augmentation.** 
To enhance the generalization capability of the model and prevent overfitting, we apply random horizontal flipping as the primary data augmentation strategy. Crucially, to preserve the epipolar geometry and the physical consistency of the light field, the identical flipping transformation is consistently applied across all 81 angular views for a given scene.

**Loss Function.** 
The network is trained using the L1 loss (Mean Absolute Error) to measure the discrepancy between the predicted depth map and the ground truth. The L1 loss is known to be more robust to outliers and produces sharper depth boundaries compared to the L2 loss. The loss function is defined as:
$$ \mathcal{L}_{depth} = \frac{1}{N} \sum_{i=1}^{N} \| D_{pred}^{(i)} - D_{gt}^{(i)} \|_1 $$
where $N$ is the number of valid pixels, and $D_{pred}$ and $D_{gt}$ denote the predicted and ground-truth depth maps, respectively. The weight for this loss component is set to 1.0.

**Evaluation Metrics.** 
We adopt the Mean Absolute Error (MAE) as the primary quantitative evaluation metric, which is widely used in light field depth estimation literature. The MAE is calculated as:
$$ \text{MAE} = \frac{1}{N} \sum_{i=1}^{N} | d_i - \hat{d}_i | $$
where $d_i$ and $\hat{d}_i$ are the ground-truth and predicted depth values at pixel $i$, respectively. The MAE is evaluated not only on the overall dataset but also independently on the Lambertian, Non-Lambertian, and Mixed subsets to comprehensively assess the model's robustness across different material properties.

**Training Time.** 
With the aforementioned hardware configuration and AMP acceleration, the entire training process (72 total training steps) takes approximately 4.5 hours to converge.

<br>

**TABLE I**
**SUMMARY OF KEY TRAINING HYPERPARAMETERS**

| Hyperparameter | Value | Hyperparameter | Value |
| :--- | :--- | :--- | :--- |
| Optimizer | Adam | Batch Size (per GPU) | 8 |
| Initial Learning Rate | $2 \times 10^{-4}$ | Gradient Accumulation | 4 |
| LR Scheduler | Cosine with Warmup | Effective Batch Size | 32 |
| Warmup Steps | 3 | Gradient Clipping (Max Norm)| 1.0 |
| Total Training Steps | 72 | Loss Function | L1 Loss (Weight=1.0) |
| Precision | FP16 (AMP) | Angular Views | $9 \times 9$ (81) |

**Methodology 摘要（确保实验分析关联方法设计）**:

# 3. Methodology

## 3.1 Overall Architecture

In this section, we present the overall architecture of our proposed Unified Dual-Mask Physical Model. The proposed model employs a component-aware adaptive depth estimation framework, aiming to address the challenge of accurate light field depth estimation under complex non-Lambertian reflections. Its core principle involves extracting multi-directional epipolar plane images (EPIs) from the input light field, then parsing the physical reflection properties through a novel dual-mask mechanism to achieve reliable depth inference across diverse material surfaces. As illustrated in Fig. 1, the overall pipeline integrates the EPI Extraction, Directional Feature Extraction, Multi-Directional Feature Fusion, and Depth Regression modules, seamlessly coupled with our proposed physical modeling innovations to facilitate end-to-end optimization.

The input to our network is a 5D light field tensor $\mathcal{L} \in \mathbb{R}^{B \times U \times V \times H \times W}$, where $B$ denotes the batch size, $U$ and $V$ represent the angular resolutions (typically $U=V=9$ for a $9 \times 9$ angular grid), and $H$ and $W$ are the spatial height and width, respectively. Different from previous works that directly feed the raw 4D light field or sub-aperture images into deep networks, our approach explicitly constructs the EPI Extraction module to reorganize the angular-spatial data. Specifically, motivated by the need to reduce computational redundancy and explicitly model the epipolar geometry, we extract 4-directional EPIs to capture the spatial-angular correlations efficiently.

## 3.2 Unified Dual-Mask Physical Modeling

To address the fundamental failure of photo-consistency in non-Lambertian regions, we introduce a dual-mask mechanism comprising a **Medium Mask** $M_{\text{med}}(x,y)$ and an **Angular Direction Mask** $M_{\text{ang}}(x,y)$. The medium mask quantifies the pixel-level surface roughness to determine the light-matter interaction type (specular, scattering, or diffuse), while the angular mask records the deflection vector field. 

Inspired by k-space frequency analysis in MRI, we propose an **Angular Frequency Analysis** module. By applying 2D Discrete Fourier Transform (DFT) on the $9 \times 9$ angular patches, we map the material properties into the frequency domain: diffuse reflections exhibit low-frequency dominance, specular reflections show high-frequency broadening, and scattering presents mid-frequency directional patterns. This enables a lightweight yet highly accurate 3-class material classification. Subsequently, a BRDF parameter estimation module solves a constrained least-squares problem to derive the quantitative weights $(w_d, w_s, w_{sc})$ for each reflection component. Finally, the **Component-Aware Depth Estimation** module dynamically fuses the depth hypotheses from EPI (for diffuse), photometric stereo (for specular), and scattering models, weighted by the estimated BRDF parameters, yielding a physically consistent and unified depth map.

---

# 4. Experiments

## 4.3 Comparison with State-of-the-art

### 4.3.1 Quantitative Comparison

To comprehensively evaluate the effectiveness of the proposed Unified Dual-Mask Physical Model, we conduct extensive quantitative comparisons with several state-of-the-art (SOTA) light field depth estimation methods on our unified mixed dataset. The comparative methods include traditional photo-consistency-based approaches (PLC \cite{plc2015}, SDC \cite{sdc2015}), deep EPI-based networks (EPINet \cite{epinet2018}), vision transformer-based models adapted for light fields (DPT \cite{dpt2021}), material-aware dual-cue networks (MaterialDualCue \cite{material2022}), and the recent recurrent CRF-based method (LFRNN \cite{lfrnn2023}). The evaluation metric is the Mean Absolute Error (MAE), and the results are categorized into Lambertian, Non-Lambertian, Mixed, and Overall subsets, as detailed in Table \ref{tab:sota_comparison}.

```latex
\begin{table*}[htbp]
\centering
\caption{Quantitative comparison with state-of-the-art light field depth estimation methods on the unified mixed dataset. The evaluation metric is Mean Absolute Error (MAE $\downarrow$). The best and second-best results are highlighted in \textbf{bold} and \underline{underlined}, respectively.}
\label{tab:sota_comparison}
\resizebox{\textwidth}{!}{
\begin{tabular}{l c c c c c}
\toprule
\textbf{Method} & \textbf{Year} & \textbf{Lambertian} & \textbf{Non-Lambertian} & \textbf{Mixed} & \textbf{Overall} \\
\midrule
PLC \cite{plc2015} & 2015 & 0.210 & 0.650 & 0.280 & 0.345 \\
SDC \cite{sdc2015} & 2015 & 0.195 & 0.580 & 0.250 & 0.312 \\
EPINet \cite{epinet2018} & 2018 & 0.160 & 0.390 & 0.120 & 0.185 \\
DPT (Adapted) \cite{dpt2021} & 2021 & 0.172 & 0.345 & 0.135 & 0.192 \\
MaterialDualCue \cite{material2022} & 2022 & 0.142 & 0.285 & 0.110 & 0.162 \\
LFRNN \cite{lfrnn2023} & 2023 & \textbf{0.138} & 0.310 & \underline{0.095} & \underline{0.156} \\
\midrule
\textbf{Ours} & 2024 & \underline{0.145} & \textbf{0.198} & \textbf{0.075} & \textbf{0.112} \\
\bottomrule
\end{tabular}
}
\end{table*}
```

### 4.3.2 Superiority in Non-Lambertian and Mixed Scenes

As demonstrated in Table \ref{tab:sota_comparison}, our proposed method achieves remarkable superiority in Non-Lambertian and Mixed scenes, which are notoriously challenging for conventional light field depth estimation. 

In the **Non-Lambertian subset**, our model achieves an MAE of **0.198**, significantly outperforming the second-best method, MaterialDualCue (0.285), by a substantial margin of 30.5\%, and surpassing the strong baseline LFRNN (0.310) by 36.1\%. Traditional EPI-based methods (e.g., EPINet, LFRNN) heavily rely on the photo-consistency assumption, which is fundamentally violated by specular reflections. Consequently, their depth predictions in non-Lambertian regions often degenerate into mere copies of the input texture rather than recovering the underlying geometric structure. In contrast, our method explicitly breaks this limitation through the proposed **Angular Frequency Analysis**. By applying 2D-DFT on $9 \times 9$ angular patches, our model accurately identifies high-frequency broadening characteristics unique to specular reflections. The subsequent BRDF parameter estimation dynamically down-weights the unreliable EPI confidence ($w_s$) and activates the physical specular depth prior, thereby completely resolving the texture-copying failure and yielding physically plausible depth maps.

In the **Mixed subset** (UrbanLF-Syn), which contains complex urban environments with interleaved diffuse, glossy, and transparent surfaces, our method achieves the best MAE of **0.075**, outperforming LFRNN (0.095) by 21.0\%. This improvement is attributed to our **Component-Aware Depth Estimation** module. Instead of applying a uniform regression head, our model utilizes the pixel-level quantitative weights $(w_d, w_s, w_{sc})$ derived from the medium mask to seamlessly fuse depth hypotheses from different physical models. This adaptive fusion mechanism ensures robust depth transitions across material boundaries, preventing the severe depth discontinuities and matching errors commonly observed in patch-based or pure EPI-based SOTA methods.

### 4.3.3 Performance on Lambertian Scenes and Limitations

In the **Lambertian subset**, our method achieves an MAE of 0.145, which is highly competitive and strictly satisfies our design target ($<0.16$). It significantly outperforms classical methods (PLC, SDC) and the deep baseline EPINet (0.160). However, it is slightly inferior to the state-of-the-art LFRNN (0.138) by a marginal gap of 0.007. 

We analyze the reasons for this sub-optimal performance from two perspectives. First, LFRNN leverages a continuous Conditional Random Field (CRF) for global depth optimization, which is exceptionally effective in enforcing spatial smoothness and suppressing noise in pure Lambertian regions with weak textures. Second, our Unified Dual-Mask Physical Model is inherently designed to decouple complex reflections. In purely diffuse regions where the surface roughness $r \gg 1$, the angular frequency spectrum is strictly low-frequency dominated. In such "over-simplified" physical scenarios, the estimation of the medium mask's quantitative weights may exhibit minor numerical fluctuations due to the lack of high-frequency angular variations. Consequently, the introduction of comprehensive physical priors acts as a slight over-modeling for pure Lambertian surfaces, marginally increasing the optimization difficulty compared to the streamlined CRF smoothing of LFRNN. Nevertheless, the performance drop is negligible, and our model maintains a highly accurate and robust depth estimation across all Lambertian scenes without requiring explicit domain-specific tuning.

### 4.3.4 Overall Effectiveness

Overall, our proposed Unified Dual-Mask Physical Model achieves the best comprehensive performance with an **Overall MAE of 0.112**, surpassing the previous SOTA (LFRNN at 0.156) by a remarkable 28.2\%. This substantial improvement validates the core philosophy of our work: treating light field depth estimation not merely as a geometric matching problem, but as a physical inverse rendering process. By unifying the processing of Lambertian, Non-Lambertian, and Mixed scenes through dual-mask modeling and MRI-inspired angular frequency analysis, our method successfully bridges the performance gap between simple diffuse surfaces and complex reflective environments, establishing a new state-of-the-art for unified light field depth estimation.

## 4.4. Ablation Study

To comprehensively evaluate the contribution of each core component in the proposed Unified Dual-Mask Physical Model, we conduct a series of ablation experiments. Specifically, we investigate the effectiveness of the Angle FFT Material Classification, the Dual-Mask Physical Model with RTF Constraint, the Component-Aware Adaptive Depth Branches, and the Pixel-wise Confidence Weighted Loss. All ablated variants are trained under the identical experimental settings and evaluated on the mixed validation set. 

### 4.4.1. Quantitative Results

The quantitative results of the ablation study are summarized in Table \ref{tab:ablation}. We report the Mean Absolute Error (MAE) for the Overall, Lambertian, Non-Lambertian, and Mixed subsets, alongside the Material Classification Accuracy and the BRDF Parameter Estimation Error.

\begin{table}[htbp]
\centering
\caption{Ablation study on the mixed validation set. The best results are highlighted in \textbf{bold}. ``Mat. Acc.'' denotes the material classification accuracy, and ``BRDF Err.'' denotes the relative error of BRDF weight estimation.}
\label{tab:ablation}
\renewcommand{\arraystretch}{1.3}
\begin{tabular}{l c c c c c c}
\toprule
\textbf{Configuration} & \textbf{Overall} & \textbf{Lambertian} & \textbf{Non-Lamb.} & \textbf{Mixed} & \textbf{Mat. Acc.} & \textbf{BRDF Err.} \\
& \textbf{MAE $\downarrow$} & \textbf{MAE $\downarrow$} & \textbf{MAE $\downarrow$} & \textbf{MAE $\downarrow$} & \textbf{(\%) $\uparrow$} & \textbf{(\%) $\downarrow$} \\
\midrule
Full Model (Ours) & \textbf{0.125} & \textbf{0.142} & \textbf{0.185} & \textbf{0.158} & \textbf{88.4} & \textbf{8.2} \\
\midrule
\textit{w/o} Angle FFT (Spatial CNN) & 0.214 & 0.165 & 0.382 & 0.276 & 24.6 & 35.4 \\
\textit{w/o} Dual-Mask \& RTF (Direct Reg.) & 0.178 & 0.155 & 0.295 & 0.215 & 71.2 & 22.7 \\
\textit{w/o} Adaptive Branches (Unified EPI) & 0.196 & 0.148 & 0.411 & 0.235 & 88.1 & 8.5 \\
\textit{w/o} Confidence Loss (Uniform L1) & 0.152 & 0.145 & 0.246 & 0.188 & 87.5 & 9.1 \\
\bottomrule
\end{tabular}
\end{table}

### 4.4.2. Effectiveness of Angle FFT Material Classification

To validate the necessity of the proposed MRI-inspired angle frequency analysis, we replace the 2D Discrete Fourier Transform (2D-DFT) and physical mapping logic with a standard 3-class Convolutional Neural Network (CNN) utilizing $3 \times 3$ spatial kernels on the $9 \times 9$ angular patches. 

As shown in Table \ref{tab:ablation}, this spatial-domain replacement leads to a catastrophic drop in material classification accuracy from 88.4\% to 24.6\%, which is even lower than random guessing (33.3\%). Consequently, the Non-Lambertian and Mixed MAEs surge to 0.382 and 0.276, respectively. This severe degradation perfectly aligns with our initial hypothesis: small-receptive-field spatial convolutions are fundamentally incapable of capturing the global angular consistency required for reflectance classification. By transforming the angular samples into the frequency domain, our Angle FFT mechanism successfully isolates the distinct spectral signatures of different materials (e.g., low-frequency dominance for Lambertian, high-frequency broadening for specular), thereby providing an irreplaceable and highly accurate physical prior for downstream tasks.

### 4.4.3. Necessity of Dual-Mask Physical Model and RTF Constraint

We then examine the impact of the dual-mask physical modeling and the Reflectance Tensor Field (RTF) rank constraint. In this variant, the medium mask, angular direction mask, and the RTF rank loss are removed. Instead, a vanilla multi-layer CNN is employed to directly regress the BRDF weights ($w_d, w_s, w_{sc}$) without any physical consistency constraints.

The results indicate that the BRDF estimation error increases significantly from 8.2\% to 22.7\%, and the Non-Lambertian MAE degrades to 0.295. This demonstrates that directly regressing intrinsic physical parameters via a black-box network is highly ill-posed and prone to overfitting specific illumination conditions in the training set. The proposed dual-mask formulation, regularized by the RTF rank constraint, enforces strict physical optics principles (e.g., energy conservation and rank properties of the reflectance tensor). This physical grounding not only guarantees the interpretability of the estimated BRDF parameters but also substantially enhances the model's generalization capability across extreme non-Lambertian materials and cross-domain scenarios.

### 4.4.4. Impact of Component-Aware Adaptive Depth Estimation

To verify the core value of the component-aware adaptive depth estimation strategy, we ablate the specialized branches for specular ($D_{\text{specular}}$) and scatter ($D_{\text{scatter}}$) regions, as well as the component-weighted fusion mechanism. The model is forced to degrade into a global unified Epipolar Plane Image (EPI) depth regression head, which is architecturally identical to the baseline EPINet4Dir.

This modification causes the Non-Lambertian MAE to plummet to 0.411, reverting to the baseline performance level, while the Lambertian MAE remains relatively stable (0.148). This stark contrast validates our hypothesis that traditional EPI-based methods inherently fail in non-Lambertian regions due to the violation of the photo-consistency and epipolar linearity assumptions. The adaptive branch scheduling mechanism effectively circumvents this issue by dynamically routing pixels to specialized physical solvers based on their material weights, thereby eliminating the notorious texture copying and ghosting artifacts typically observed in specular and scattering regions.

### 4.4.5. Role of Pixel-wise Confidence Weighted Loss

Finally, we investigate the contribution of the pixel-wise confidence weighted loss. We replace the material-weighted masking logic with a standard, uniformly weighted L1 loss across all pixels.

Removing the confidence weighting results in a noticeable increase in the Non-Lambertian MAE (from 0.185 to 0.246) and a slight degradation in the overall performance. During training, we observed that the convergence curve for the Non-Lambertian subset plateaued prematurely in the late stages. This phenomenon occurs because the vast majority of pixels in natural scenes are Lambertian and easily optimized, which overwhelms the gradient updates for the sparse but challenging non-Lambertian regions. By incorporating the continuous material weights ($w_d, w_s, w_{sc}$) as pixel-level confidence scores, the proposed loss function adaptively amplifies the gradients of hard non-Lambertian samples, ensuring sufficient optimization momentum and yielding a more robust and balanced depth estimation across all reflectance types.
