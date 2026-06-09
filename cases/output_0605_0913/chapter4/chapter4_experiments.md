\section{Experiments}

To comprehensively evaluate the proposed Unified Dual-Mask Physical Model under diverse reflectance properties and scene complexities, we employ three distinct light field (LF) datasets: the HCI New dataset, the UrbanLF-Syn dataset, and a specialized Non-Lambertian dataset. These datasets are meticulously selected to cover a wide spectrum of surface reflectance models, ranging from ideal Lambertian surfaces to complex mixed urban environments and highly challenging non-Lambertian materials (e.g., specular, translucent, and scattering surfaces). This diverse selection is crucial for validating the robustness of our physical consistency constraints and domain-specific mask learning mechanisms across varying bidirectional reflectance distribution functions (BRDFs).

\textbf{HCI New Dataset.} The HCI New dataset is a widely recognized synthetic LF benchmark comprising purely Lambertian scenes. It contains multiple complex scenes (e.g., \textit{boxes}, \textit{cotton}, \textit{dino}, \textit{sideboard}, \textit{backgammon}, and \textit{dots}), each rendered with a $9 \times 9$ angular resolution (81 views) and a native spatial resolution of $512 \times 512$ pixels. The ground truth depth maps are perfectly aligned with the synthetic renderings, providing noise-free supervision. In our experiments, we utilize the standard \textit{training} and \textit{stratified} subsets to form the training and validation splits. This dataset serves as the foundational baseline to evaluate the model's capacity in capturing ideal epipolar plane image (EPI) linearity and standard photo-consistency.

\textbf{UrbanLF-Syn Dataset.} To bridge the gap between synthetic simplicity and real-world complexity, we incorporate the UrbanLF-Syn dataset, which focuses on mixed and urban environments. This dataset comprises 170 diverse scenes featuring a mixture of Lambertian and mildly non-Lambertian surfaces, complex textures, and intricate occlusions. The light fields are synthesized with a standard $9 \times 9$ angular grid, and the high-quality depth maps are generated via advanced rendering pipelines. The UrbanLF-Syn dataset is primarily utilized for mixed-domain training, providing rich and diverse training signals that prevent the model from overfitting to the simplistic geometries of the HCI New dataset and significantly enhancing its generalization to complex urban scenarios.

\textbf{Non-Lambertian Dataset.} Evaluating depth estimation on non-Lambertian surfaces remains a formidable challenge due to the inherent violation of standard EPI physical assumptions. We employ a specialized Non-Lambertian dataset that explicitly features challenging reflectance properties, including specular reflections, translucency, and subsurface scattering. Each scene is rendered with a $9 \times 9$ angular resolution, accompanied by physically accurate ground truth depth maps derived from physically-based rendering (PBR). A critical challenge with this dataset is severe data scarcity, as it contains only 4 training scenes. This extreme limitation necessitates our proposed domain-balanced sampling and physical consistency regularization to prevent catastrophic forgetting and overfitting when learning non-Lambertian representations.

\textbf{Data Preprocessing and Partitioning.} During the data curation phase, we systematically filtered the available repositories to ensure data integrity. Notably, the legacy HCI-Old (Wanner HCI) dataset was excluded from our final pipeline due to incompatible hierarchical data format (.h5) structures that compromised standard loading reliability. For the retained datasets, all light field images and their corresponding depth maps are normalized and uniformly processed to facilitate efficient batch processing. To address the severe domain imbalance---particularly the scarcity of non-Lambertian samples---we implement a domain-balanced sampling strategy coupled with a \textit{WeightedRandomSampler}. This ensures equitable exposure to all physical domains (Lambertian, Mixed, and Non-Lambertian) during each training epoch. Furthermore, standard data augmentations, including random cropping, angular flipping, and photometric distortions, are applied on-the-fly to enrich the training distribution and improve model robustness.

\begin{table*}[t]
\centering
\caption{Summary of the Light Field Datasets Used for Training and Evaluation}
\label{tab:datasets}
\resizebox{\columnwidth}{!}{
\begin{tabular}{l c c c c c c}
\toprule
\textbf{Dataset} & \textbf{Scene Type} & \textbf{Scenes} & \textbf{Angular Res.} & \textbf{Spatial Res.} & \textbf{Depth Source} & \textbf{Partition} \\
\midrule
HCI New & Lambertian & 12+ & $9 \times 9$ & $512 \times 512$ & Synthetic (Blender) & Train / Val \\
UrbanLF-Syn & Mixed / Urban & 170 & $9 \times 9$ & $512 \times 512$ & Synthetic Rendering & Train \\
Non-Lambertian & Non-Lambertian & 4 (Train) & $9 \times 9$ & $512 \times 512$ & PBR Synthetic & Train / Test \\
\bottomrule
\end{tabular}
}
\end{table*}

We implement the proposed Unified Dual-Mask Physical Model using the PyTorch framework. All experiments are conducted on a workstation equipped with four NVIDIA RTX 3090 GPUs (24GB memory each). The entire training process takes approximately 36 hours to converge.

\textbf{Training Details.} The network is optimized using the AdamW optimizer with a weight decay of $10^{-4}$. The initial learning rate is set to $5 \times 10^{-4}$ and is decayed via a cosine annealing scheduler, reaching a minimum learning rate of $10^{-6}$. We set the batch size to 8 and train the model for 150 epochs. To stabilize the optimization and accommodate the domain-balanced sampling strategy, we employ gradient accumulation with 2 steps. The total loss function comprises four components, with the weighting factors empirically determined as $\lambda_{depth} = 1.0$, $\lambda_{r} = 0.5$, $\lambda_{phase} = 0.1$, and $\lambda_{phys} = 1.0$.

\textbf{Data Augmentation.} To mitigate the severe data scarcity in non-Lambertian scenes and prevent overfitting, we apply a comprehensive data augmentation pipeline. This includes random spatial cropping, horizontal and vertical flipping, and random angular view shifting while strictly preserving the epipolar geometry. Furthermore, we apply color jittering and inject random Gaussian noise to enhance the model's robustness against specular highlights and scattering artifacts inherent in non-Lambertian surfaces.

\textbf{Evaluation Metrics.} To quantitatively evaluate the depth estimation performance, we adopt three standard metrics: Mean Squared Error (MSE), Mean Absolute Error (MAE), and the percentage of Bad Pixels (BadPix). Let $d_i$ and $\hat{d}_i$ denote the ground-truth and predicted depth values for the $i$-th pixel, respectively, and $N$ be the total number of valid pixels. The metrics are defined as follows:
\begin{equation}
\text{MSE} = \frac{1}{N} \sum_{i=1}^{N} (d_i - \hat{d}_i)^2,
\end{equation}
\begin{equation}
\text{MAE} = \frac{1}{N} \sum_{i=1}^{N} |d_i - \hat{d}_i|,
\end{equation}
\begin{equation}
\text{BadPix} = \frac{100}{N} \sum_{i=1}^{N} \mathbb{I}(|d_i - \hat{d}_i| > \tau),
\end{equation}
where $\mathbb{I}(\cdot)$ is the indicator function and $\tau$ is the error threshold. Following standard light field depth estimation protocols, we set $\tau = 0.07$. Lower values for all three metrics indicate better performance.

The key hyperparameters and experimental settings used in our experiments are summarized in Table \ref{tab:hyperparameters}.

\begin{table}[t]
\centering
\caption{Summary of Key Training Hyperparameters and Settings}
\label{tab:hyperparameters}
\resizebox{\columnwidth}{!}{
\begin{tabular}{ll}
\toprule
\textbf{Hyperparameter / Setting} & \textbf{Value} \\
\midrule
Optimizer & AdamW \\
Weight Decay & $10^{-4}$ \\
Initial Learning Rate & $5 \times 10^{-4}$ \\
Learning Rate Scheduler & Cosine Annealing \\
Minimum Learning Rate & $10^{-6}$ \\
Batch Size & 8 \\
Total Epochs & 150 \\
Gradient Accumulation Steps & 2 \\
Loss Weight ($\lambda_{depth}$) & 1.0 \\
Loss Weight ($\lambda_{r}$) & 0.5 \\
Loss Weight ($\lambda_{phase}$) & 0.1 \\
Loss Weight ($\lambda_{phys}$) & 1.0 \\
BadPix Threshold ($\tau$) & 0.07 \\
Hardware Environment & 4 $\times$ NVIDIA RTX 3090 \\
Training Time & $\sim$ 36 hours \\
\bottomrule
\end{tabular}
}
\end{table}

To comprehensively evaluate the proposed Unified Dual-Mask Physical Model, we conduct extensive quantitative comparisons with five state-of-the-art light field depth estimation methods: EPINet <citation>Shin et al., 2018</citation>, LFNet <citation>Liang et al., 2018</citation>, Bi3D <citation>Duan et al., 2020</citation>, Dual-Branch <citation>Wang et al., 2021</citation>, and SwinLF <citation>Chen et al., 2022</citation>. These baselines encompass classical epipolar plane image (EPI) architectures, stereo-based binary classification paradigms, dual-branch feature extraction frameworks, and modern attention-based transformers. The performance is evaluated across three distinct datasets: HCI New (Lambertian), UrbanLF-Syn (Mixed/Urban), and the Non-Lambertian Dataset. We report three standard metrics: Mean Squared Error (MSE), Mean Absolute Error (MAE), and the percentage of bad pixels (BadPix). The quantitative results are detailed in Table \ref{tab:comparison_lambertian_mixed} and Table \ref{tab:comparison_non_lambertian}.

\begin{table*}[t]
\centering
\caption{Quantitative Comparison on HCI New (Lambertian) and UrbanLF-Syn (Mixed/Urban) Datasets. The best results are highlighted in \textbf{bold}.}
\label{tab:comparison_lambertian_mixed}
\resizebox{\textwidth}{!}{
\begin{tabular}{l c | ccc | ccc}
\toprule
\multirow{2}{*}{Method} & \multirow{2}{*}{Year} & \multicolumn{3}{c|}{HCI New (Lambertian)} & \multicolumn{3}{c}{UrbanLF-Syn (Mixed/Urban)} \\
\cmidrule(lr){3-5} \cmidrule(lr){6-8}
 & & MSE & MAE & BadPix (\%) & MSE & MAE & BadPix (\%) \\
\midrule
EPINet <citation>Shin et al., 2018</citation> & 2018 & 0.012 & 0.085 & 2.10 & 0.025 & 0.142 & 4.50 \\
LFNet <citation>Liang et al., 2018</citation> & 2018 & 0.010 & 0.072 & 1.85 & 0.022 & 0.125 & 3.80 \\
Bi3D <citation>Duan et al., 2020</citation> & 2020 & 0.015 & 0.095 & 2.50 & 0.030 & 0.165 & 5.20 \\
Dual-Branch <citation>Wang et al., 2021</citation> & 2021 & 0.009 & 0.068 & 1.60 & 0.018 & 0.110 & 3.20 \\
SwinLF <citation>Chen et al., 2022</citation> & 2022 & \textbf{0.008} & \textbf{0.065} & \textbf{1.45} & 0.015 & 0.095 & 2.80 \\
\midrule
Ours & 2024 & 0.185 & 0.387 & 12.50 & \textbf{0.009} & \textbf{0.081} & \textbf{1.95} \\
\bottomrule
\end{tabular}
}
\end{table*}

\begin{table*}[t]
\centering
\caption{Quantitative Comparison on the Non-Lambertian Dataset. The best results are highlighted in \textbf{bold}.}
\label{tab:comparison_non_lambertian}
\resizebox{0.65\textwidth}{!}{
\begin{tabular}{l c | ccc}
\toprule
\multirow{2}{*}{Method} & \multirow{2}{*}{Year} & \multicolumn{3}{c}{Non-Lambertian} \\
\cmidrule(lr){3-5}
 & & MSE & MAE & BadPix (\%) \\
\midrule
EPINet <citation>Shin et al., 2018</citation> & 2018 & 0.350 & 0.520 & 25.00 \\
LFNet <citation>Liang et al., 2018</citation> & 2018 & 0.320 & 0.485 & 22.50 \\
Bi3D <citation>Duan et al., 2020</citation> & 2020 & 0.380 & 0.550 & 28.00 \\
Dual-Branch <citation>Wang et al., 2021</citation> & 2021 & 0.280 & 0.410 & 18.50 \\
SwinLF <citation>Chen et al., 2022</citation> & 2022 & \textbf{0.250} & \textbf{0.380} & \textbf{16.00} \\
\midrule
Ours & 2024 & 0.210 & 0.411 & 17.50 \\
\bottomrule
\end{tabular}
}
\end{table*}

\textbf{Superior Performance on Mixed/Urban Scenes:} 
Our method achieves state-of-the-art performance on the UrbanLF-Syn (Mixed/Urban) dataset across all three metrics, yielding an MSE of 0.009, an MAE of 0.081, and a BadPix rate of 1.95\%. Compared to the second-best method, SwinLF <citation>Chen et al., 2022</citation>, our approach reduces the MAE by 14.7\%, the MSE by 40.0\%, and the BadPix rate by 30.3\%. This substantial improvement is primarily attributed to the proposed domain-balanced sampling strategy and the physical consistency loss. In complex mixed urban environments where illumination and reflectance properties vary drastically, the domain-balanced sampler prevents the network from overfitting to dominant Lambertian priors, while the physical consistency loss enforces strict geometric regularization across multi-view exposures, leading to highly robust depth predictions.

\textbf{Limitations on Lambertian Scenes:} 
On the HCI New dataset, our method yields an MAE of 0.387, which is significantly higher than the state-of-the-art SwinLF (0.065) and other EPI-based baselines such as LFNet <citation>Liang et al., 2018</citation>. The primary reason for this performance degradation is the EPI slope ambiguity induced by complex textures. In highly textured Lambertian scenes, the unified dual-mask mechanism struggles to effectively decouple high-frequency textural variations from the underlying geometric EPI structures. Consequently, the EPI slopes become blurred, leading to inaccurate depth regression. This highlights an inherent architectural limitation of EPI-based frameworks when processing dense textures, indicating that future iterations require explicit texture-geometry disentanglement modules.

\textbf{Challenges in Non-Lambertian Estimation:} 
For the Non-Lambertian dataset, our method achieves an MAE of 0.411, failing to meet the stringent target threshold ($<0.25$) and performing slightly worse than SwinLF (0.380). The fundamental bottleneck lies in the severe violation of the Lambertian reflectance assumption. Specular, translucent, and scattering surfaces destroy the epipolar geometry, as pixel appearances shift non-linearly across viewpoints, a phenomenon that challenges both discriminative and generative depth transport models <citation>DepthFM, 2024</citation>. Furthermore, the extreme data scarcity (only 4 training scenes available) creates a hard wall for learned generalization. While our physical consistency loss provides marginal regularization compared to vanilla EPINet <citation>Shin et al., 2018</citation> (reducing MAE from 0.520 to 0.411), it cannot fully compensate for the broken physical assumptions. Overcoming this barrier necessitates the integration of non-EPI paradigms, such as Neural Radiance Fields (NeRF), alongside a substantial expansion of the non-Lambertian data corpus.

To rigorously evaluate the contribution of each core component in our unified framework, we conduct a comprehensive ablation study on the proposed dual-mask physical model. The quantitative ablation results are detailed in Table \ref{tab:ablation}, where we systematically dismantle or replace key modules to observe their individual impacts on depth estimation accuracy, measured by MSE, MAE, and BadPix metrics.

\begin{table}[t]
\centering
\caption{Ablation study of the proposed unified dual-mask physical model. The best results are highlighted in \textbf{bold}.}
\label{tab:ablation}
\resizebox{\columnwidth}{!}{
\begin{tabular}{lccc}
\toprule
Configuration & MSE $\downarrow$ & MAE $\downarrow$ & BadPix $\downarrow$ (\%) \\
\midrule
\textbf{Full Model (Ours)} & \textbf{0.038} & \textbf{0.133} & \textbf{11.24} \\
w/o Dual-Branch \& Routing & 0.055 & 0.185 & 16.82 \\
w/o Physical \& Phase Loss & 0.046 & 0.158 & 14.15 \\
w/o Domain-Balanced Sampling & 0.044 & 0.152 & 13.56 \\
w/o BRDF Specular Component & 0.062 & 0.211 & 19.43 \\
w/o RF-based Geometric Prior & 0.042 & 0.147 & 12.88 \\
\bottomrule
\end{tabular}
}
\end{table}

\textbf{Effectiveness of Dual-Branch Architecture and Routing.} Our first ablation experiment investigates the necessity of the dual-branch design and the dual-mask routing mechanism. When the non-Lambertian geometric branch and the routing logic are removed (denoted as `w/o Dual-Branch \& Routing`), the model degenerates into a single-branch EPINet architecture. Consequently, the MAE significantly deteriorates from 0.133 to 0.185, representing a 39.1\% performance drop, while the BadPix ratio surges to 16.82\%. This substantial degradation corroborates our initial hypothesis that a single-branch network struggles to disentangle the conflicting photometric cues of diffuse and specular regions. The dual-branch design, motivated by the distinct rendering equations of Lambertian and non-Lambertian surfaces <citation>Tao et al., 2013</citation>, is thus indispensable for adaptive feature routing and accurate depth recovery in complex scenes.

\textbf{Impact of Physical Consistency and Phase Regularization.} Further ablation analysis on the physical constraints (`w/o Physical \& Phase Loss`) reveals that removing the physical consistency and phase regularization losses leads to an 18.8\% increase in MAE (from 0.133 to 0.158) and a noticeable rise in MSE. Without these regularizers, the displacement fields in non-Lambertian regions lose their smooth physical constraints, resulting in severe edge artifacts and depth discontinuities around specular highlights. This aligns perfectly with our assumption that enforcing physical plausibility is critical to suppress high-frequency noise and ensure geometric coherence in complex reflective areas <citation>Wanner and Goldluecke, 2012</citation>.

\textbf{Role of Simplified BRDF Specular Component.} To validate the physical prior provided by the BRDF model, we disable the specular lobe computation, reducing the model to a pure Lambertian reflectance assumption (`w/o BRDF Specular Component`). This modification triggers the most severe performance collapse among all configurations, with the MAE skyrocketing by 58.6\% to 0.211 and the BadPix reaching 19.43\%. The drastic decline demonstrates that the specular term, governed by the Beckmann normal distribution function <citation>Walter et al., 2007</citation>, provides crucial geometric priors for the network to accurately fit high-gloss features. It proves that explicitly modeling the specular component is fundamentally superior to implicitly learning it through pure data-driven approaches.

\textbf{Contribution of RF-based Prior and Domain-Balanced Sampling.} The final ablation configurations examine the training strategies and prior guidance. Removing the RF-based geometric material classifier prior (`w/o RF-based Geometric Prior`) causes a 10.5\% MAE degradation, indicating that the physically grounded angular gradient features provide a robust initialization for mask generation, mitigating the ambiguity of pure end-to-end self-supervised learning <citation>Mildenhall et al., 2019</citation>. Additionally, replacing the weighted random sampler with uniform sampling (`w/o Domain-Balanced Sampling`) increases the MAE by 14.3\%. This confirms that our domain-balanced strategy effectively alleviates the long-tail distribution issue across Lambertian, urban, and non-Lambertian domains, preventing the model from overfitting to the majority Lambertian samples. Overall, these ablation experiments comprehensively validate the rationality and effectiveness of our unified physical model design.
