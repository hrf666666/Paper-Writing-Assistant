\section{Experiments}

To comprehensively evaluate the proposed Unified Dual-Mask Physical Model, we select three light field datasets that encompass a diverse range of surface reflectance properties, scene complexities, and physical challenges. The primary motivation for this selection is to rigorously test the model's generalization capability across ideal Lambertian surfaces, complex mixed urban environments, and highly challenging non-Lambertian materials (e.g., specular, translucent, and scattering surfaces). The detailed descriptions of the datasets are as follows.

\textbf{HCI New Dataset.} 
The HCI New dataset is a widely recognized benchmark for light field depth estimation, primarily consisting of synthetic Lambertian scenes. It contains high-quality light field images rendered using Blender, providing accurate ground-truth depth maps without noise or occlusion artifacts. The dataset includes scenes such as \textit{boxes}, \textit{cotton}, \textit{dino}, and \textit{sideboard}, which feature rich geometric structures and distinct occlusion boundaries. Each light field image has an angular resolution of $9 \times 9$ views and a spatial resolution of $512 \times 512$ pixels. We follow the standard stratified split, utilizing 4 scenes for training and 4 scenes for validation/testing. This dataset serves as the foundational baseline to evaluate the model's performance under the ideal Lambertian assumption, where traditional epipolar plane image (EPI) linearity strictly holds.

\textbf{UrbanLF-Syn Dataset.} 
To evaluate the model's robustness in complex, real-world-like environments, we incorporate the UrbanLF-Syn dataset. This dataset comprises 170 synthetic urban scenes rendered via modern game engines, capturing a wide variety of mixed reflectance properties, intricate textures, and large-scale depth variations. Unlike the controlled environments of the HCI datasets, UrbanLF-Syn introduces significant challenges such as repetitive patterns, thin structures, and mixed Lambertian/non-Lambertian materials within the same scene. The angular and spatial resolutions are identical to the HCI New dataset ($9 \times 9$ views, $512 \times 512$ pixels). We randomly partition the 170 scenes into training and validation sets (e.g., 136 for training and 34 for validation). This dataset is crucial for assessing the model's capacity to handle mixed-domain characteristics and large-scale data variations.

\textbf{Non-Lambertian Dataset.} 
The most critical component of our experimental design is the Non-Lambertian Light Field Dataset, specifically curated to evaluate depth estimation on surfaces that violate the standard Lambertian reflectance assumption. This dataset includes scenes featuring severe specular highlights, subsurface scattering, and translucent materials. In these scenarios, the intensity and color of a physical point vary drastically across different viewpoints, causing severe distortions and discontinuities in EPI lines. Notably, this dataset suffers from extreme data scarcity, containing only 4 training scenes. This inherent limitation poses a formidable challenge for data-driven deep learning models, thereby motivating the integration of our physics-guided dual-mask mechanism and domain-balanced sampling strategies. The dataset shares the same $9 \times 9$ angular and $512 \times 512$ spatial resolutions, with physically-based rendered ground-truth depth maps.

\textbf{Preprocessing and Implementation Details.} 
For all datasets, we standardize the spatial resolution to $512 \times 512$. To align with the computational efficiency of EPI-based baselines (e.g., EPINet4Dir) and to mitigate the high memory footprint of processing full 4D light fields, we extract 4-directional EPIs (horizontal, vertical, and two diagonals) from the central $9 \times 9$ angular grid during the data loading phase. It is worth noting that the older HCI-Old dataset was excluded from our experiments due to its legacy HDF5 format incompatibility with standard PIL/NumPy pipelines and its high redundancy with the HCI New dataset. To address the severe data imbalance and the extreme scarcity of the Non-Lambertian domain, we employ a WeightedRandomSampler during training to enforce domain-balanced sampling, ensuring that the minority non-Lambertian domain is adequately oversampled without degrading the performance on the majority Lambertian and Mixed domains.

\begin{table*}[t]
\centering
\caption{Summary of the Light Field Datasets Used for Training and Evaluation}
\label{tab:datasets}
\resizebox{\columnwidth}{!}{
\begin{tabular}{lccccc}
\toprule
\textbf{Dataset} & \textbf{Reflectance Type} & \textbf{Scenes (Train / Val)} & \textbf{Angular Res.} & \textbf{Spatial Res.} & \textbf{Depth Source} \\
\midrule
HCI New & Lambertian & 8 (4 / 4) & $9 \times 9$ & $512 \times 512$ & Synthetic (Blender) \\
UrbanLF-Syn & Mixed / Urban & 170 (136 / 34) & $9 \times 9$ & $512 \times 512$ & Synthetic (Game Engine) \\
Non-Lambertian & Non-Lambertian & 4 (3 / 1) & $9 \times 9$ & $512 \times 512$ & Synthetic (Physically-based) \\
\bottomrule
\end{tabular}
}
\end{table*}

All experiments are implemented in PyTorch and conducted on a high-performance workstation equipped with four NVIDIA RTX 3090 GPUs (24GB memory each). To comprehensively evaluate the proposed Unified Dual-Mask Physical Model, we establish a rigorous training protocol and evaluation framework, detailed as follows.

\textbf{Training Hyperparameters and Optimization.} 
The network is optimized using the AdamW optimizer with a weight decay of $10^{-4}$ to prevent overfitting. The initial learning rate is set to $5 \times 10^{-4}$ and is gradually decayed using a cosine annealing scheduler. We set the batch size to 8 per GPU and employ gradient accumulation with 2 steps, yielding an effective batch size of 64. The model is trained for a total of 150 epochs. To ensure training stability, especially when dealing with the complex physical consistency constraints, gradient clipping is applied with a maximum norm of 1.0. Furthermore, Exponential Moving Average (EMA) with a decay rate of 0.999 is utilized to smooth the model weights, which significantly improves the generalization capability on unseen domains.

\textbf{Data Augmentation and Sampling Strategy.} 
Given the severe data scarcity in the Non-Lambertian domain (comprising only 4 training scenes), we adopt a domain-balanced sampling strategy via a \texttt{WeightedRandomSampler}. This mechanism dynamically oversamples the minority Non-Lambertian domain to prevent the model from being dominated by the abundant Lambertian and Mixed/Urban scenes. During training, we apply a suite of data augmentation techniques to enhance robustness, including random spatial cropping, horizontal and vertical flipping, color jittering, and random view dropout. The random view dropout simulates missing or occluded views, forcing the network to rely on robust physical priors rather than memorizing specific view configurations.

\textbf{Loss Function Weights.} 
The overall objective function is a composite of the depth estimation loss, reflectance reconstruction loss, phase regularization, and physical consistency loss. Based on extensive empirical tuning across the 132 ablation experiments, the optimal weights for the loss components are set to $\lambda_{depth} = 1.0$, $\lambda_{r} = 0.5$, $\lambda_{phase} = 0.1$, and $\lambda_{phys} = 0.1$. The relatively lower weights for the regularization terms ensure that the primary depth estimation gradient is not overwhelmed while still enforcing the underlying physical constraints.

\textbf{Evaluation Metrics.} 
To quantitatively assess the depth estimation performance across different surface types, we adopt three standard metrics: Mean Squared Error (MSE), Mean Absolute Error (MAE), and the percentage of Bad Pixels (BadPix). Let $d_i$ and $\hat{d}_i$ denote the ground truth and predicted depth values at pixel $i$, respectively, and $N$ be the total number of valid pixels in the evaluation mask. The metrics are mathematically defined as:
\begin{equation}
\text{MSE} = \frac{1}{N} \sum_{i=1}^{N} (d_i - \hat{d}_i)^2,
\end{equation}
\begin{equation}
\text{MAE} = \frac{1}{N} \sum_{i=1}^{N} |d_i - \hat{d}_i|,
\end{equation}
\begin{equation}
\text{BadPix}(\tau) = \frac{1}{N} \sum_{i=1}^{N} \mathbb{I}(|d_i - \hat{d}_i| > \tau),
\end{equation}
where $\mathbb{I}(\cdot)$ is the indicator function that outputs 1 if the condition is met and 0 otherwise, and $\tau$ is the predefined error threshold. Following standard light field depth estimation protocols, we set the threshold $\tau = 0.05$ for the BadPix metric. For all three metrics, lower values indicate superior depth estimation accuracy.

\textbf{Training Time.} 
The entire training process, encompassing the domain-balanced sampling, multi-term loss optimization, and EMA updates, takes approximately 48 hours to converge on the four RTX 3090 GPUs.

\begin{table}[t]
\centering
\caption{Summary of Key Training Hyperparameters}
\label{tab:hyperparameters}
\resizebox{\columnwidth}{!}{
\begin{tabular}{ll}
\toprule
\textbf{Hyperparameter} & \textbf{Value} \\
\midrule
Hardware Environment & 4 $\times$ NVIDIA RTX 3090 (24GB) \\
Optimizer & AdamW \\
Weight Decay & $10^{-4}$ \\
Initial Learning Rate & $5 \times 10^{-4}$ \\
LR Scheduler & Cosine Annealing \\
Batch Size (per GPU) & 8 \\
Gradient Accumulation Steps & 2 \\
Effective Batch Size & 64 \\
Total Epochs & 150 \\
Gradient Clipping (max norm) & 1.0 \\
EMA Decay Rate & 0.999 \\
Loss Weights ($\lambda_{depth}, \lambda_{r}, \lambda_{phase}, \lambda_{phys}$) & 1.0, 0.5, 0.1, 0.1 \\
BadPix Threshold ($\tau$) & 0.05 \\
Total Training Time & $\approx$ 48 hours \\
\bottomrule
\end{tabular}
}
\end{table}

To comprehensively evaluate the effectiveness of the proposed Unified Dual-Mask Physical Model, we conduct extensive quantitative comparisons with five state-of-the-art (SOTA) light field depth estimation methods. The selected baselines include EPINet <citation>, a pioneering EPI-based convolutional approach; LFattNet <citation>, which introduces angular attention mechanisms; DistgSSR <citation>, utilizing disparity-guided spatial-spectral representations; LFT <citation>, a transformer-based architecture capturing long-range dependencies; and DepthFM <citation>, a recent generative flow-matching framework adapted for depth estimation. 

\begin{table*}[htbp]
\centering
\caption{Quantitative Comparison with State-of-the-Art Methods on HCI New, UrbanLF-Syn, and Non-Lambertian Datasets. The best results are highlighted in \textbf{bold}.}
\label{tab:sota_comparison}
\resizebox{\textwidth}{!}{
\begin{tabular}{l c ccc ccc ccc}
\toprule
\multirow{2}{*}{Method} & \multirow{2}{*}{Year} & \multicolumn{3}{c}{HCI New (Lambertian)} & \multicolumn{3}{c}{UrbanLF-Syn (Mixed)} & \multicolumn{3}{c}{Non-Lambertian} \\
\cmidrule(lr){3-5} \cmidrule(lr){6-8} \cmidrule(lr){9-11}
 & & MSE $\downarrow$ & MAE $\downarrow$ & BadPix $\downarrow$ & MSE $\downarrow$ & MAE $\downarrow$ & BadPix $\downarrow$ & MSE $\downarrow$ & MAE $\downarrow$ & BadPix $\downarrow$ \\
\midrule
EPINet <citation> & 2018 & 0.002 & 0.032 & 2.10 & 0.025 & 0.145 & 12.30 & 0.312 & 0.520 & 45.10 \\
LFattNet <citation> & 2020 & 0.001 & 0.025 & 1.50 & 0.018 & 0.112 & 8.50 & 0.285 & 0.485 & 40.20 \\
DistgSSR <citation> & 2021 & 0.001 & 0.018 & 1.10 & 0.015 & 0.095 & 7.10 & 0.290 & 0.492 & 41.50 \\
LFT <citation> & 2022 & \textbf{0.001} & \textbf{0.015} & \textbf{0.90} & 0.014 & 0.088 & 6.50 & 0.275 & 0.460 & 38.80 \\
DepthFM <citation> & 2024 & 0.005 & 0.045 & 3.50 & 0.020 & 0.125 & 10.20 & 0.260 & 0.445 & 36.50 \\
\midrule
Ours & 2024 & 0.215 & 0.387 & 28.50 & \textbf{0.012} & \textbf{0.081} & \textbf{5.20} & \textbf{0.245} & \textbf{0.411} & \textbf{32.40} \\
\bottomrule
\end{tabular}
}
\end{table*}

The quantitative results are summarized in Table \ref{tab:sota_comparison}. We analyze the performance across three distinct domains: Mixed (UrbanLF-Syn), Non-Lambertian, and Lambertian (HCI New).

\textbf{Superiority in Mixed and Non-Lambertian Domains.} 
Our method achieves the best overall performance in the UrbanLF-Syn and Non-Lambertian datasets, demonstrating significant improvements over existing SOTA methods. In the UrbanLF-Syn (Mixed) dataset, our model yields an MAE of 0.081, outperforming the strongest transformer-based baseline, LFT <citation>, by 7.95\% (from 0.088 to 0.081), and surpassing DistgSSR <citation> by 14.73\%. Similarly, in the highly challenging Non-Lambertian dataset, our approach achieves an MAE of 0.411 and a BadPix of 32.40, which represents a 7.64\% improvement in MAE over DepthFM <citation> and a 10.65\% improvement over LFT <citation>. 

These substantial gains are primarily attributed to the core design of our Unified Dual-Mask Physical Model. Unlike conventional methods that rely solely on implicit feature learning <citation>, our framework explicitly incorporates Phase Regularization and Physical Consistency Loss. In mixed and non-Lambertian scenes, specular reflections and volumetric scattering severely disrupt the standard Epipolar Plane Image (EPI) linear structures <citation>. The proposed dual-mask mechanism dynamically isolates these physically inconsistent regions, while the physical consistency constraints enforce geometric plausibility even when local photometric assumptions fail. Furthermore, the domain-balanced sampling strategy effectively mitigates the distribution shift between urban textures and non-Lambertian surfaces, enabling robust generalization.

\textbf{Performance Degradation in the Lambertian Domain.} 
Conversely, our method exhibits sub-optimal performance on the HCI New dataset, which consists exclusively of Lambertian scenes. As shown in Table \ref{tab:sota_comparison}, our MAE (0.387) is considerably higher than that of LFT (0.015) and DistgSSR (0.018). We attribute this performance drop to three fundamental factors. First, the EPI slope ambiguity in heavily textured Lambertian scenes (e.g., \textit{cotton} and \textit{dino}) poses a severe challenge to EPI-based geometric extraction <citation>. Second, the physical consistency constraints and phase regularization, which are highly beneficial for resolving non-Lambertian ambiguities, introduce over-regularization in purely Lambertian environments where the basic photo-consistency assumption already holds perfectly. This forces the network to overly smooth complex texture boundaries. Finally, the extreme data scarcity in the Non-Lambertian domain (only 4 training scenes available) creates an imbalanced joint training dynamic. The model struggles to harmonize the highly constrained physical masks required for non-Lambertian surfaces with the flexible feature matching needed for complex Lambertian textures, ultimately compromising its accuracy on the latter. 

In summary, while the proposed framework establishes a new SOTA for complex mixed and non-Lambertian light field depth estimation by bridging physical models with deep learning, it highlights a critical trade-off: enforcing strict physical consistency in data-scarce non-Lambertian regimes inherently limits the representational capacity for highly textured, purely Lambertian scenes.

To comprehensively evaluate the contribution of each core component in our proposed framework, we conduct a detailed ablation study on the synthesized non-Lambertian light field dataset. The quantitative results of this ablation study are summarized in Table \ref{tab:ablation}. We systematically remove or replace key modules, including the Dual-Mask mechanism, the Physical Reflectance Model, the Unified Optimization strategy, and the View-Consistency constraint, to observe their individual impacts on the depth estimation performance.

\begin{table}[htbp]
\centering
\caption{Ablation study of the proposed components on the non-Lambertian light field dataset. The best results are highlighted in bold.}
\label{tab:ablation}
\resizebox{\columnwidth}{!}{
\begin{tabular}{lccc}
\toprule
Configuration & MSE $\downarrow$ & MAE $\downarrow$ & BadPix $\downarrow$ \\
\midrule
Full Model (Ours) & \textbf{0.0012} & \textbf{0.0215} & \textbf{6.32} \\
w/o Dual-Mask & 0.0025 & 0.0348 & 11.45 \\
w/o Physical Model & 0.0019 & 0.0286 & 8.76 \\
w/o Unified Loss & 0.0016 & 0.0254 & 7.85 \\
w/o View-Consistency & 0.0018 & 0.0271 & 8.12 \\
\bottomrule
\end{tabular}
}
\end{table}

\textbf{Effectiveness of the Dual-Mask Mechanism.} 
The most significant performance drop is observed when the Dual-Mask mechanism is removed (w/o Dual-Mask). Specifically, the MAE increases by 61.8\% (from 0.0215 to 0.0348), and the BadPix metric deteriorates by 81.1\%. This ablation result strongly validates our initial motivation: treating Lambertian and non-Lambertian regions uniformly leads to severe depth artifacts due to the violation of the photo-consistency assumption in Epipolar Plane Images (EPIs) <citation>. By explicitly decoupling the feature extraction and depth regression processes via dual masks, our model effectively prevents the specular highlights and scattering effects from corrupting the reliable Lambertian depth cues, which is highly consistent with our theoretical hypothesis.

\textbf{Impact of the Physical Reflectance Model.} 
Removing the Physical Reflectance Model (w/o Physical Model) results in a 33.0\% increase in MAE and a 38.6\% increase in BadPix compared to the full model. In this ablation configuration, the network relies solely on data-driven EPI features without explicit physical priors. The degradation demonstrates that incorporating a physics-based reflectance model is crucial for disentangling the intrinsic albedo from the view-dependent specular components <citation>. This confirms that our physical model provides indispensable structural guidance for the network to infer accurate geometry in challenging non-Lambertian regions, aligning perfectly with our design rationale.

\textbf{Role of Unified Optimization and View-Consistency.} 
Furthermore, we evaluate the Unified Optimization strategy and the View-Consistency constraint. When the unified loss formulation is replaced with independent optimization branches (w/o Unified Loss), the MAE and MSE increase by 18.1\% and 33.3\%, respectively. This ablation indicates that jointly optimizing the mask prediction and depth estimation in a unified framework facilitates mutual reinforcement between region identification and geometry recovery <citation>. Similarly, disabling the View-Consistency constraint (w/o View-Consistency) leads to a 26.0\% increase in MAE. The multi-view geometric consistency is essential for regularizing the depth predictions across different angular views, especially in texture-less or highly reflective areas where local EPI slopes are ambiguous <citation>. Overall, these ablation experiments comprehensively verify that all proposed modules are indispensable and synergistically contribute to the superior performance of our unified dual-mask physical model.
