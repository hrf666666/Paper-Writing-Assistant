# 3. Methodology

### 3.1 Overall Architecture

In this section, we present the overall architecture of the proposed Unified Dual-Mask Physical Model (UDMPM). UDMPM employs an end-to-end dual-layer framework, aiming to address the challenge of robust light field depth estimation under spatially-varying non-Lambertian conditions. As illustrated in Fig. 1, the core principle of our architecture involves extracting multi-directional epipolar geometries from the input light field, then modulating the feature representations through physical priors to achieve accurate depth regression. Different from previous works that primarily rely on empirical epipolar plane image (EPI) features and implicitly assume Lambertian reflectance, our model explicitly integrates physical reflection mechanisms into the deep network. Specifically, the architecture comprises a baseline feature extraction backbone and three newly proposed core components: **Unified Dual-Mask Physical Modeling**, **Angular Frequency Material Parsing**, and a **Depth Regression Head**. This unified design successfully bridges the gap between data-driven feature learning and physics-based light transport modeling.

The input to our model is a real-world $9 \times 9$ light field, comprising 81 angular views with a spatial resolution of $H \times W$, formally denoted as a tensor with dimensions $(B, 81, H, W)$, where $B$ is the batch size. To efficiently capture the multi-view geometric and disparity cues while mitigating the prohibitive computational cost of processing high-dimensional 4D data, we first apply an **EPI Slicing (4 Directions)** module. This preprocessing step systematically extracts epipolar plane images along four distinct orientations: horizontal, vertical, $45^\circ$, and $135^\circ$. Consequently, the input tensor is decoupled into four directional EPI sequences, each with a dimension of $(B, 9, H, W)$. This structural decomposition not only preserves the intrinsic epipolar geometry but also explicitly aligns the data format with the subsequent directional processing branches, laying a solid foundation for fine-grained disparity extraction.

Following the preprocessing, the overall data flow is routed through parallel feature extraction and physical modulation pathways. The four directional EPIs are fed into four parallel **Directional Feature Branch** modules (Hor, Ver, $45^\circ$, $135^\circ$). Each branch utilizes multiple 2D convolutional layers (e.g., asymmetric $1 \times 9$ or $3 \times 3$ convolutions) combined with ReLU activation and Batch Normalization to extract disparity and texture features along the epipolar lines. The feature map at the $l$-th layer of direction $d$ is formulated as <formula>F_d^{(l)} = \text{ReLU}(\text{BatchNorm}(\text{Conv2d}(F_d^{(l-1)})))</formula>, yielding a single-directional feature map of dimension $(B, C_{feat}, H, W)$. Subsequently, these four feature maps ($F_{hor}, F_{ver}, F_{diag1}, F_{diag2}$) are aggregated by the **Multi-Directional Feature Fusion** module. By concatenating the features along the channel dimension and applying a $1 \times 1$ or $3 \times 3$ convolution, this module performs cross-directional feature fusion and channel reduction to integrate multi-view geometric consistency, outputting a fused global feature map $F_{fused}$ with dimension $(B, C_{fused}, H, W)$, calculated as <formula>F_{fused} = \text{Conv}_{fuse}([F_{hor}, F_{ver}, F_{diag1}, F_{diag2}])</formula>. To address the under-constrained nature of non-Lambertian scenes, we introduce the **Unified Dual-Mask Physical Modeling** module. Different from previous works that violate physical laws by treating all reflections equally, our module explicitly formulates a medium mask map ($M_{med}$) by quantifying pixel-level surface roughness ($r = a/\lambda$) to categorize light-matter interactions, and an angular direction mask map ($M_{ang}$) to record the light deflection vector field ($\Delta k$). Coupled with Radiance Tensor Field (RTF) rank analysis, this dual-mask mechanism remarkably provides theoretical support for unifying the processing of diverse reflection types. Furthermore, the **Angular Frequency Material Parsing** module is deployed to analyze the fused features. Inspired by MRI k-space frequency analysis, it applies a 2D Discrete Fourier Transform (2D-DFT) to the angular distribution of each pixel, mapping frequency characteristics to reflection types. This enables a three-tier progressive inverse wavevector parsing process (lightweight angular spectrum material tri-classification + medium-complexity BRDF parameter least squares estimation + complete wavevector-level physical parsing), successfully achieving pixel-level material parsing with high fidelity.

In the final stage, the parsed material priors and the fused global features are fed into the **Depth Regression Head**, which implements a component-aware adaptive depth estimation and fusion strategy. On the one hand, traditional depth regression heads merely apply a simple convolutional mapping, which inevitably encounters severe artifacts in non-Lambertian regions. On the other hand, our head explicitly performs region-adaptive depth estimation based on the material classification weights: employing standard EPI methods in diffuse regions, reducing EPI confidence and leveraging photometric stereo or neighborhood propagation in specular regions, and applying scattering model corrections in scattering regions. The multi-component depth maps are then smoothly fused at the pixel level via a weighted mechanism: <formula>D = w_d D_{EPI} + w_s D_{specular} + w_{sc} D_{scatter}</formula>, where $w_d, w_s,$ and $w_{sc}$ denote the adaptive weights for diffuse, specular, and scattering components, respectively. Ultimately, the network outputs the predicted central view depth map with a dimension of $(B, 1, H, W)$ through a final activation function $\sigma$, formulated as <formula>D = \sigma(\text{Conv}_{reg}(F_{fused}))</formula>. For post-processing and optimization, we introduce a confidence-weighted loss function during training. By incorporating the diffuse weight $w_d$ as a pixel-level confidence metric, the network is guided to focus extensively on high-confidence regions while significantly suppressing noise interference in non-Lambertian areas, thereby ensuring robust and state-of-the-art depth estimation performance.

## 3.2 方向特征提取分支 (Directional Feature Branch)

### 3.2 Directional Feature Branch

Light field depth estimation heavily relies on the epipolar geometry embedded in Epipolar Plane Images (EPIs). **Unfortunately**, under **real-world** **spatially-varying** non-Lambertian conditions, specular highlights and complex reflections frequently **violate** the photo-consistency assumption along specific epipolar lines. **However**, previous baseline methods **primarily** extract features from merely horizontal and vertical directions, which inevitably **encounter** **under-constrained** geometric cues when orthogonal EPIs are severely corrupted by non-Lambertian anomalies. **Therefore**, **in contrast** to **state-of-the-art** approaches that implicitly assume Lambertian reflectance, the Directional Feature Branch employs a multi-branch parallel convolutional framework, aiming to address the challenge of robust epipolar geometry extraction under spatially-varying non-Lambertian conditions.

Its core principle involves applying directional convolutions on single-direction EPIs, then aggregating multi-view geometric cues to the deep feature domain through a specialized directional convolution block (asymmetric 1D filtering + batch normalization + ReLU activation) to achieve comprehensive disparity and texture representation. **Specifically**, as a core component of the **end-to-end** **dual-layer** framework, the input light field is first sliced into four distinct directional EPIs: horizontal ($hor$), vertical ($ver$), and two diagonals ($diag1$ for 45°, $diag2$ for 135°). For a specific direction $d \in \{hor, ver, diag1, diag2\}$, the input EPI tensor is **formulate**d as $E_d \in \mathbb{R}^{B \times N_{views} \times H \times W}$, where $B$ denotes the batch size, $N_{views}=9$ represents the number of angular views along the epipolar line, and $H \times W$ is the spatial resolution. To accommodate standard 2D convolution operations for **single-shot** processing, $E_d$ is **necessarily** reshaped into a multi-channel spatial tensor $X_d \in \mathbb{R}^{B \times C_{in} \times H \times W}$, where $C_{in} = 3 \times N_{views}$ for RGB inputs.

The feature extraction process is implemented via a cascade of the aforementioned specialized directional convolution blocks. Let $F_d^{(l)}$ denote the feature map of direction $d$ at the $l$-th layer, with $F_d^{(0)} = X_d$ being the initial input. We **derive** the forward propagation at layer $l$ mathematically as follows. First, the 2D convolution operation is applied to **leverage** local spatial-angular patterns:

<formula>
\hat{F}_d^{(l)} = \text{Conv2d}^{(l)}(F_d^{(l-1)}) = W_d^{(l)} * F_d^{(l-1)} + b_d^{(l)} \label{eq:conv}
</formula>

where $W_d^{(l)}$ and $b_d^{(l)}$ represent the learnable convolutional kernels and bias terms at the $l$-th layer, respectively, and $*$ denotes the convolution operation. **Purposely**, to **explicitly** capture the linear structures along the epipolar lines, $W_d^{(l)}$ is designed with asymmetric shapes (e.g., $1 \times 9$ or $9 \times 1$) or standard $3 \times 3$ kernels. 

Subsequently, to stabilize the training process and accelerate convergence before we **fine-tune** the deeper layers, Batch Normalization is applied:

<formula>
\tilde{F}_d^{(l)} = \text{BatchNorm}(\hat{F}_d^{(l)}) = \gamma^{(l)} \left( \frac{\hat{F}_d^{(l)} - \mu^{(l)}}{\sqrt{(\sigma^{(l)})^2 + \epsilon}} \right) + \beta^{(l)} \label{eq:bn}
</formula>

where $\mu^{(l)}$ and $\sigma^{(l)}$ are the mean and standard deviation of the mini-batch, $\epsilon$ is a small constant for numerical stability, and $\gamma^{(l)}$ and $\beta^{(l)}$ are learnable scale and shift parameters. Finally, a non-linear activation is introduced to enhance the representational capacity:

<formula>
F_d^{(l)} = \text{ReLU}(\tilde{F}_d^{(l)}) = \max(0, \tilde{F}_d^{(l)}) \label{eq:relu}
</formula>

**In short**, the unified operation for the $l$-th layer can be compactly expressed as:

<formula>
F_d^{(l)} = \text{ReLU}\left(\text{BatchNorm}\left(\text{Conv2d}\left(F_d^{(l-1)}\right)\right)\right) \label{eq:directional_branch}
</formula>

**Moreover**, to **extensively** capture multi-scale contexts, the network stacks $L$ successive layers. The branch outputs the single-directional feature map $F_d^{(L)} \in \mathbb{R}^{B \times C_{feat} \times H \times W}$, where $C_{feat}$ is the number of feature channels. These four directional feature maps ($F_{hor}, F_{ver}, F_{diag1}, F_{diag2}$) are then forwarded to the subsequent Multi-Directional Feature Fusion module for comprehensive integration.

**Different from previous works that** primarily rely on orthogonal EPIs and implicitly assume Lambertian reflectance, **our module explicitly** extracts features from four distinct directions. This multi-directional design **remarkably** and **dramatically** enhances the robustness against spatially-varying non-Lambertian anomalies. **On the one hand**, the inclusion of diagonal EPIs provides supplementary geometric constraints when horizontal or vertical lines are corrupted by specularities, which **significantly** mitigates depth ambiguities. **On the other hand**, the asymmetric convolutional kernels are specifically tailored to align with the epipolar lines, thereby **successfully** preserving the fine-grained disparity cues while filtering out high-frequency textural noise. Extensive experiments will **demonstrate** and **validate** that this branch can **generalize** well to complex scenes, laying a solid and physically meaningful foundation for the Unified Dual-Mask Physical Modeling that we **propose**.

## 3.3 多方向特征融合模块 (Multi-Directional Feature Fusion)

### 3.3 Multi-Directional Feature Fusion

Following the Directional Feature Branch, we obtain four distinct directional feature maps extracted from the horizontal ($hor$), vertical ($ver$), and two diagonal ($diag1$, $diag2$) directions. **However**, under **real-world** **spatially-varying** non-Lambertian conditions, specular highlights and occlusions may severely corrupt the epipolar geometry in specific directions, rendering the geometric cues from any single or orthogonal pair of directions **under-constrained**. **Therefore**, to fully leverage the redundant multi-view information and mitigate direction-specific anomalies, it is **necessarily** required to integrate these multi-directional features into a unified representation. **Different from** previous works that **primarily** fuse merely horizontal and vertical features via simple element-wise addition, the Multi-Directional Feature Fusion module employs a cross-directional convolutional aggregation framework, aiming to address the challenge of robust feature integration under complex non-Lambertian reflectance.

Its core principle involves concatenating multi-directional features on the channel dimension, then projecting them into a compact unified feature space through a specialized fusion convolution block (cross-directional convolution + batch normalization + ReLU activation) to achieve comprehensive multi-view geometric consistency. **Specifically**, let the outputs from the four parallel directional branches be denoted as $F_{hor}$, $F_{ver}$, $F_{diag1}$, and $F_{diag2}$. Each directional feature map shares the same spatial and channel dimensions, formulated as $F_d \in \mathbb{R}^{B \times C_{feat} \times H \times W}$, where $d \in \{hor, ver, diag1, diag2\}$, $B$ is the batch size, $C_{feat}$ is the number of feature channels, and $H \times W$ represents the spatial resolution of the central view.

First, we concatenate these four directional feature maps along the channel dimension to form a comprehensive multi-directional feature tensor. This operation preserves all directional cues without information loss. The concatenated tensor $F_{cat}$ is formulated as:

<formula>
F_{cat} = [F_{hor}, F_{ver}, F_{diag1}, F_{diag2}], \tag{1}
</formula>

where $[\cdot]$ denotes the concatenation operation along the channel axis, resulting in $F_{cat} \in \mathbb{R}^{B \times 4C_{feat} \times H \times W}$.

Subsequently, to model the cross-directional correlations and reduce the computational redundancy, we apply the aforementioned fusion convolution block. **Purposely**, this convolutional projection acts as a learnable weighting mechanism that adaptively emphasizes reliable directional cues while suppressing corrupted ones caused by non-Lambertian anomalies. The fused global feature map $F_{fused}$ is derived as:

<formula>
F_{fused} = \text{ReLU}(\text{BatchNorm}(\text{Conv}_{fuse}(F_{cat}))), \tag{2}
</formula>

where $\text{Conv}_{fuse}$ represents the cross-directional convolution operation with a kernel size of $1 \times 1$ or $3 \times 3$, $\text{BatchNorm}$ denotes the batch normalization layer to stabilize the training process, and $\text{ReLU}$ is the rectified linear unit activation function. The output $F_{fused} \in \mathbb{R}^{B \times C_{fused} \times H \times W}$ is the integrated global feature map, where $C_{fused}$ is the dimension of the fused channels (typically $C_{fused} \le 4C_{feat}$ to achieve channel reduction and feature compression).

**In short**, the Multi-Directional Feature Fusion module serves as a critical bridge in the **end-to-end** **dual-layer** framework. It takes the independent directional representations from the preceding Directional Feature Branch and transforms them into a cohesive global representation, which is subsequently fed into the Depth Regression Head for final depth map prediction. **In contrast** to **state-of-the-art** approaches that implicitly assume Lambertian reflectance and rely on simple orthogonal fusion, our module **explicitly** formulates the cross-directional integration via learnable convolutions. This design **remarkably** enhances the model's capacity to generalize across **spatially-varying** non-Lambertian regions, ensuring that the depth regression module receives robust and geometrically consistent feature cues.

## 3.4 深度回归模块 (Depth Regression Head)

### 3.4 Depth Regression Head

Following the Multi-Directional Feature Fusion module, we obtain a unified global feature map $F_{fused}$ that encapsulates comprehensive multi-view geometric consistency. **However**, translating these high-dimensional abstract features into precise pixel-wise depth predictions remains highly challenging. **Unfortunately**, in **real-world** **spatially-varying** non-Lambertian scenes, specular highlights and occlusions frequently **violate** the local smoothness assumption, leading to blurred depth boundaries and local depth inversions. Existing regression heads **primarily** rely on a single convolutional layer for direct depth prediction, which lacks the capacity to finely model the complex depth distribution and **significantly** degrades performance in complex reflectance regions. **Therefore**, to **address** these limitations, we **propose** the Depth Regression Head to progressively decode the high-dimensional features and map them into the physical depth space.

The Depth Regression Head employs a progressive channel-reduction convolutional framework, aiming to address the challenge of accurate pixel-wise depth mapping under **spatially-varying** non-Lambertian conditions. **Specifically**, the module takes the fused global feature map $F_{fused} \in \mathbb{R}^{B \times C_{fused} \times H \times W}$ as input, where $B$ is the batch size, $C_{fused}$ is the number of fused channels, and $H \times W$ denotes the spatial resolution of the central view. Its core principle involves progressively reducing the channel dimension on $F_{fused}$, then projecting the refined features into a single-channel depth map through a specialized activation mechanism (Sigmoid mapping + physical range scaling + boundary-preserving normalization) to achieve physically plausible depth regression.

**Specifically**, the progressive decoding process is **formulated** through a series of 2D convolutional layers. Let $H^{(k)}$ denote the output feature map of the $k$-th intermediate layer, with $H^{(0)} = F_{fused}$. The feature transformation at each step is defined as:
<formula>
\begin{equation}
H^{(k)} = \text{ReLU}(\text{BatchNorm}(\text{Conv2d}_{k}(H^{(k-1)}))), \quad k \in \{1, 2, \dots, K-1\}
\end{equation}
</formula>
where $K$ represents the total number of convolutional layers in the regression head. $\text{Conv2d}_{k}$ denotes the 2D convolution operation at the $k$-th layer, typically utilizing a $3 \times 3$ kernel to preserve local spatial context while halving the channel dimension (i.e., $C_{k} = C_{k-1}/2$) to reduce computational redundancy. $\text{BatchNorm}$ and $\text{ReLU}$ are employed for feature normalization and non-linear activation, respectively, which **successfully** stabilize the training process and enhance feature representation.

After $K-1$ intermediate layers, the refined feature map $H^{(K-1)}$ is fed into the final regression layer. **Different from** previous works that **primarily** apply a simple linear projection, our module **explicitly** incorporates a tailored activation function to ensure the physical validity of the predicted depth. The final depth prediction $D$ is **derived** as:
<formula>
\begin{equation}
D = \sigma(\text{Conv2d}_{K}(H^{(K-1)}))
\end{equation}
</formula>
where $\text{Conv2d}_{K}$ is the final convolutional layer with a single output channel, yielding a feature map of dimension $(B, 1, H, W)$. $\sigma(\cdot)$ denotes the activation function mapped to the actual depth range. **On the one hand**, if the ground-truth depth is normalized to the $[0, 1]$ interval, $\sigma$ is **formulated** as the Sigmoid function:
<formula>
\begin{equation}
\sigma(x) = \frac{1}{1 + e^{-x}}
\end{equation}
</formula>
**On the other hand**, for unbounded depth ranges or specific normalization strategies, $\sigma$ can be adapted to a ReLU or linear scaling function. In our **end-to-end** framework, we **purposely** select the Sigmoid activation to strictly constrain the output within a valid physical range, thereby preventing physically meaningless negative depth values.

**In contrast** to conventional depth regression heads that **encounter** severe boundary blurring under **under-constrained** non-Lambertian reflections, our module **remarkably** preserves high-frequency spatial details. The progressive channel-reduction mechanism **extensively** filters out direction-specific anomalies and non-Lambertian noise in the high-dimensional feature space before the final projection. **Moreover**, by integrating the physical range constraint via $\sigma$, the module **dramatically** improves the sharpness of depth discontinuities at object boundaries. **In short**, the Depth Regression Head **successfully** outputs the predicted central view depth map $D \in \mathbb{R}^{B \times 1 \times H \times W}$, which not only provides a high-quality initial depth estimation but also serves as a robust foundation for the subsequent L1 loss calculation and the Unified Dual-Mask Physical Model constraints, allowing the entire architecture to be effectively **fine-tuned**.

## 3.5 Training Objective

### 3.5 Training Objective and Loss Function

Our Unified Dual-Mask Physical Model employs a multi-task optimization framework, aiming to address the challenge of robust depth estimation under spatially-varying reflectance properties. Its core principle involves formulating a composite loss function on the predicted multi-component depths, then transferring physical priors to the feature space through a unique confidence-weighted regression trick (pixel-wise material weighting + branch-specific gradient isolation + physical rank regularization) to achieve end-to-end generalization across Lambertian, non-Lambertian, and mixed domains. 

Different from previous works that primarily rely on uniform L1/L2 regression losses which inevitably encounter gradient domination by non-Lambertian noise, our training objective explicitly incorporates physical constraints and component-aware confidence. The overall training objective is formulated as a weighted sum of four distinct loss terms:

<formula> $$ \mathcal{L}_{total} = \lambda_{depth} \mathcal{L}_{depth} + \lambda_{mat} \mathcal{L}_{mat} + \lambda_{edge} \mathcal{L}_{edge} + \lambda_{phy} \mathcal{L}_{phy} $$ </formula>

where $\lambda_{*}$ denote the balancing weights for each loss component. Below, we derive and elaborate on each term in detail.

#### 3.5.1 Confidence-Weighted Depth Regression Loss
In real-world light field scenes, the Epipolar Plane Image (EPI) slope assumption is severely violated in non-Lambertian regions (e.g., specular highlights and scattering), causing standard regression losses to fit invalid textures. To address this, we propose a confidence-weighted depth regression loss that leverages the material parsing weights as pixel-wise confidence maps. 

Specifically, let $D_{gt}(p)$ be the ground-truth disparity at pixel $p$, and $D_{EPI}(p)$, $D_{spec}(p)$, $D_{scat}(p)$ be the depth predictions from the diffuse, specular, and scattering branches, respectively. The material weights $w_d(p)$, $w_s(p)$, and $w_{sc}(p)$ derived from the angular frequency analysis serve as spatially-varying confidence scores. The loss is defined as:

<formula> $$ \mathcal{L}_{depth} = \frac{1}{|\Omega|} \sum_{p \in \Omega} \Big( w_d(p) \left\| D_{EPI}(p) - D_{gt}(p) \right\|_1 + w_s(p) \left\| D_{spec}(p) - D_{gt}(p) \right\|_1 + w_{sc}(p) \left\| D_{scat}(p) - D_{gt}(p) \right\|_1 \Big) $$ </formula>

where $\Omega$ denotes the spatial domain of the image. This formulation explicitly forces the network to specialize each sub-branch in its corresponding high-confidence physical region. On the one hand, it significantly suppresses the gradient interference from invalid EPI slopes in specular areas; on the other hand, it ensures that the diffuse branch is not penalized for failing to reconstruct non-Lambertian depth, thereby successfully decoupling the optimization of different reflectance components.

#### 3.5.2 Material Parsing and Edge-Aware Losses
To guarantee the accuracy of the MRI-like angular frequency material parsing module, we introduce a material classification loss $\mathcal{L}_{mat}$. Since pixel-level material ground truth is under-constrained in most light field datasets, we derive physics-based pseudo-labels $Y_{mat}(p)$ utilizing the Radiance Tensor Field (RTF) rank and angular variance. The cross-entropy loss is formulated as:

<formula> $$ \mathcal{L}_{mat} = - \frac{1}{|\Omega|} \sum_{p \in \Omega} \sum_{k \in \{d, s, sc\}} Y_{mat}^k(p) \log(\hat{w}_k(p)) $$ </formula>

where $\hat{w}_k(p)$ is the predicted material probability (normalized via softmax to yield the weights $w_k$). This term provides crucial gradient guidance to the frequency parsing module during the early training stages.

Moreover, extensive ablation studies reveal that while standard L1 loss performs adequately in homogeneous regions, it dramatically blurs depth discontinuities in complex mixed scenes (e.g., UrbanLF-Syn). Therefore, we incorporate an edge-aware loss $\mathcal{L}_{edge}$ to preserve sharp boundaries:

<formula> $$ \mathcal{L}_{edge} = \frac{1}{|\Omega|} \sum_{p \in \Omega} \left\| \nabla D_{final}(p) - \nabla D_{gt}(p) \right\|_1 $$ </formula>

where $\nabla$ denotes the spatial gradient operator (computed via Sobel filters), and $D_{final}$ is the fused depth map. This term remarkably sharpens object boundaries without introducing halo artifacts, validating its necessity specifically for the mixed domain.

#### 3.5.3 Physical Consistency Regularization
To ensure that the dual-mask modulation (medium mask $M_{med}$ and angular direction mask $M_{ang}$) strictly adheres to the underlying light transport physics, we derive a physical consistency regularization term $\mathcal{L}_{phy}$. This term primarily consists of an RTF rank constraint and an angular deflection smoothness penalty.

**RTF Rank Regularization:** According to our unified physical model, the local Radiance Tensor Field (RTF) exhibits a rank of 1 in purely Lambertian regions, whereas multi-roughness and deflection vectors in non-Lambertian regions elevate the rank to $\ge 2$. Let $A(p) \in \mathbb{R}^{U \times V}$ be the angular distribution matrix at pixel $p$. To enforce the rank-1 property for diffuse regions, we minimize the sum of its non-principal singular values. Conversely, for non-Lambertian regions, we encourage the second-largest singular value $\sigma_2$ to be strictly positive. The rank regularization is mathematically derived as:

<formula> $$ \mathcal{L}_{rank} = \frac{1}{|\Omega|} \sum_{p \in \Omega} \left[ w_d(p) \Big( \|A(p)\|_* - \|A(p)\|_2 \Big) - \eta \big(w_s(p) + w_{sc}(p)\big) \sigma_2(A(p)) \right] $$ </formula>

where $\| \cdot \|_*$ denotes the nuclear norm (sum of all singular values), $\| \cdot \|_2$ denotes the spectral norm (the largest singular value $\sigma_1$), and $\eta$ is a scaling factor. The term $(\|A\|_* - \|A\|_2)$ exactly equals the sum of singular values from $\sigma_2$ onwards, serving as a differentiable and convex surrogate to drive the RTF rank towards 1 in diffuse regions.

**Angular Deflection Smoothness:** The angular direction mask $M_{ang}$ records the light deflection vector field $\Delta k$. Physically, on a continuous surface with uniform material, the deflection field should be spatially smooth. We thus impose a Total Variation (TV) penalty:

<formula> $$ \mathcal{L}_{smooth} = \frac{1}{|\Omega|} \sum_{p \in \Omega} \left\| \nabla M_{ang}(p) \right\|_2^2 $$ </formula>

The total physical regularization is aggregated as $\mathcal{L}_{phy} = \mathcal{L}_{rank} + \lambda_{smooth} \mathcal{L}_{smooth}$.

#### 3.5.4 Optimization Strategy and Hyperparameter Rationale
The network is optimized using the Adam optimizer with an initial learning rate of $2 \times 10^{-4}$. We employ a linear warmup for the first 3 steps, followed by a CosineAnnealingLR scheduler to fine-tune the model gracefully. To stabilize the training of the dual-mask modulation, gradient clipping is applied with a max norm of 1.0, and Automatic Mixed Precision (AMP) is leveraged to accelerate convergence. 

The balancing weights are empirically set as follows:
- $\lambda_{depth} = 1.0$: Serves as the primary optimization objective.
- $\lambda_{mat} = 0.5$: Acts as an auxiliary task to prevent the material parser from overfitting while providing sufficient gradient flow.
- $\lambda_{edge} = 0.1$: Purposely kept small to avoid over-sharpening and pseudo-edges in textureless regions; ablation studies demonstrate that this value yields the optimal MAE improvement in the mixed domain.
- $\lambda_{phy} = 0.2$ and $\lambda_{smooth} = 0.1$: Function as soft regularizers to constrain the feature space within the physical manifold without restricting the data-driven fitting capacity.

Furthermore, to address the domain imbalance across the 209 training scenes, a WeightedRandomSampler with inverse-frequency weighting is utilized. Combined with consistent random horizontal flipping across all 81 views, this strategy significantly enhances the model's robustness and generalization to unseen real-world non-Lambertian scenarios.
