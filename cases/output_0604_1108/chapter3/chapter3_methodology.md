# 3. Methodology

In this section, we present the overall architecture of the proposed Unified Dual-Mask Physical Model, termed GeometricDualMask, for non-Lambertian light field depth estimation. Unlike previous works that predominantly rely on the idealized Lambertian reflectance assumption, our architecture explicitly addresses the physical boundary where Epipolar Plane Image (EPI) linear structures degrade due to complex material reflections. As illustrated in Fig. 1, the framework integrates a physics-driven signal decomposition mechanism with a dual-branch geometric routing network. By decoupling the angular signals into illumination, disparity, and material components, the model adaptively processes Lambertian and non-Lambertian regions through specialized branches, ultimately yielding a unified and highly accurate depth representation.

The network takes light field data as input, comprising a $9 \times 9$ angular sampling grid and the corresponding center view image. Let the spatial dimensions of the center view be $H \times W$. The angular patch for each spatial pixel $(x, y)$ is denoted as $I(u,v) \in \mathbb{R}^{9 \times 9 \times C}$, where $(u,v)$ represents the angular coordinates and $C$ is the number of color channels. Prior to entering the main network, the raw light field data undergoes standard preprocessing, including normalization and the extraction of 2D EPI slices along the horizontal and vertical angular dimensions. These EPI slices, alongside the center view, serve as the foundational geometric priors for subsequent feature extraction, ensuring that the intrinsic epipolar geometry is preserved for the network to exploit.

The data flow progresses through four primary modules, each designed to tackle specific physical characteristics of light field imaging. First, the **Three-Layer Angular Signal Decomposition** module physically decouples the discrete angular sampling signals. Motivated by the need to separate material-induced reflections from geometric disparities, this module decomposes $I(u,v)$ into a direct current (DC) component representing ambient illumination, linear coefficients $a$ and $b$ capturing disparity-induced EPI slopes, and a residual component $\varepsilon(u,v)$ encoding material-specific Bidirectional Reflectance Distribution Function (BRDF) properties. The decomposition is formulated as:
$$ I(u,v) = DC + a \cdot u + b \cdot v + \varepsilon(u,v) $$
Additionally, angular gradients are extracted as geometric pseudo-labels. This explicit physical decoupling prevents the entanglement of texture and depth cues, a common limitation in end-to-end learning approaches. Following decomposition, the features are routed into a dual-branch architecture. The **Lambertian EPI Branch** processes the EPI features, linear coefficients, and the center view. Since Lambertian surfaces satisfy the angular cone constraint, this branch employs convolutional layers to extract linear EPI structures and incorporates a continuous depth prior, such as the Plane Regular Sampling Operator (PRSO), to enforce piecewise smoothness. The depth prediction for Lambertian regions, $D_L \in \mathbb{R}^{H \times W \times C_{epi}}$, is regressed as:
$$ D_L = \text{PRSO}(\text{Conv}(\text{EPI\_Features})) $$
Conversely, the **Non-Lambertian Geometric Branch** handles regions where EPI assumptions fail, such as specular highlights and scattering. Instead of relying on corrupted frequency or linear features, this branch utilizes the residual $\varepsilon(u,v)$ and angular gradients to capture local geometric anomalies (e.g., X-shaped patterns in EPIs). The non-Lambertian depth prediction, $D_{NL} \in \mathbb{R}^{H \times W \times C_{geo}}$, is derived via:
$$ D_{NL} = \text{Conv}(\text{Geometric\_Features}(\varepsilon, \text{angular\_gradient})) $$
This specialized routing ensures that non-Lambertian regions are processed with appropriate geometric cues rather than being forced into an incompatible linear EPI model. Finally, the **Dual-Mask Generation and Fusion** module integrates the dual-branch outputs. To address the severe channel imbalance between the two branches (e.g., $C_{epi}=320$ vs. $C_{geo}=3$), both $D_L$ and $D_{NL}$ undergo a channel-balanced linear projection to a unified dimension ($\text{FUSE\_DIM}=96$), yielding projected features $F_L$ and $F_{NL}$. The projected features are concatenated and passed through convolutional layers to generate a pixel-level domain classification mask $M \in \mathbb{R}^{H \times W \times 1}$, which distinguishes Lambertian from non-Lambertian regions:
$$ M = \sigma(\text{Conv}(\text{Proj}(F_L) \oplus \text{Proj}(F_{NL}))) $$
where $\sigma$ denotes the sigmoid activation and $\oplus$ represents channel-wise concatenation. The final unified depth map $D_{final}$ is obtained by mask-weighted fusion:
$$ D_{final} = M \odot D_L + (1-M) \odot D_{NL} $$
where $\odot$ indicates element-wise multiplication. This fusion strategy dynamically adapts to mixed-material scenes, significantly enhancing depth accuracy across diverse surface types.

The architecture outputs two primary tensors: the unified high-precision depth map $D_{final} \in \mathbb{R}^{H \times W \times 1}$ and the pixel-level domain classification mask $M \in \mathbb{R}^{H \times W \times 1}$. During training, the mask $M$ is supervised using the extracted angular gradient pseudo-labels via a domain classification loss ($\mathcal{L}_{domain}$), replacing less effective scene-level binary cross-entropy supervision. Simultaneously, the depth map is optimized using a depth regression loss ($\mathcal{L}_{depth}$). The total objective function is formulated as $\mathcal{L}_{total} = \lambda_d \mathcal{L}_{depth} + \lambda_m \mathcal{L}_{domain}$, where the loss weights $\lambda_d$ and $\lambda_m$ are both set to 1.0 to balance the optimization. In the post-processing and training sampling stage, a weighted random sampler and domain-balanced sampling strategy are employed to maintain multi-domain exposure balance. This mechanism specifically oversamples scarce non-Lambertian training instances (with an oversampling factor of 10), ensuring robust generalization and preventing the network from biasing towards dominant Lambertian regions in complex mixed scenes.

## 3.2 三层角信号分解模块 (Three-Layer Angular Signal Decomposition)

Conventional light field depth estimation methods predominantly rely on the Lambertian reflectance assumption, where the angular signal of a spatial point remains constant or forms linear structures in Epipolar Plane Images (EPIs). However, in real-world scenes, non-Lambertian materials such as specular highlights and translucent surfaces violate this assumption, causing severe distortions in the angular domain. Existing deep learning approaches typically process these distorted angular patches using black-box convolutional networks, which implicitly entangle illumination, geometry, and material properties, leading to depth ambiguities in complex regions. To address this physical boundary, we introduce the Three-Layer Angular Signal Decomposition module. Different from previous works that directly feed raw angular patches into feature extractors, our module explicitly decouples the discrete angular samples into illumination, disparity, and material components based on a physical lighting model, providing physically meaningful priors for the subsequent dual-branch network.

Let the input angular patch for a specific spatial pixel be denoted as $I(u,v) \in \mathbb{R}^{9 \times 9 \times C}$, where $(u,v)$ represents the discrete angular coordinates within the $9 \times 9$ micro-lens array, and $C$ is the number of color channels. According to the physical image formation model under varying viewpoints, the observed angular intensity can be approximated by a first-order Taylor expansion around the center viewpoint, combined with a residual term capturing high-frequency material reflections. We formulate the angular signal decomposition as:
$$
I(u,v) = I_{dc} + a \cdot u + b \cdot v + \varepsilon(u,v)
$$
where $I_{dc} \in \mathbb{R}^C$ represents the direct current (DC) component, corresponding to the ambient illumination and the base albedo of the surface. The coefficients $a, b \in \mathbb{R}^C$ denote the linear gradients along the horizontal and vertical angular dimensions, respectively. These linear coefficients are intrinsically linked to the local EPI slopes, thereby serving as direct geometric cues for disparity and depth. The term $\varepsilon(u,v) \in \mathbb{R}^{9 \times 9 \times C}$ is the residual component, which captures the non-linear angular variations induced by the Bidirectional Reflectance Distribution Function (BRDF) of non-Lambertian materials.

To solve for the physical components from the discrete $9 \times 9$ samples, we employ a least-squares plane fitting approach. We first construct the design matrix $\mathbf{U} \in \mathbb{R}^{81 \times 3}$ for the angular coordinates, where each row corresponds to a specific $(u,v)$ pair formatted as $[1, u, v]$. The angular patch $I(u,v)$ is reshaped into a matrix $\mathbf{I} \in \mathbb{R}^{81 \times C}$. The optimal parameters $\mathbf{\Theta} = [I_{dc}, a, b]^T \in \mathbb{R}^{3 \times C}$ are obtained by minimizing the squared error:
$$
\mathbf{\Theta} = \arg\min_{\mathbf{\Theta}} \| \mathbf{U}\mathbf{\Theta} - \mathbf{I} \|_F^2
$$
The closed-form solution is derived using the Moore-Penrose pseudoinverse:
$$
\mathbf{\Theta} = (\mathbf{U}^T \mathbf{U})^{-1} \mathbf{U}^T \mathbf{I}
$$
Since the angular grid is fixed and symmetric, the matrix $(\mathbf{U}^T \mathbf{U})^{-1} \mathbf{U}^T$ is a constant projection matrix, allowing for highly efficient implementation via fixed $1 \times 1$ convolutions across the spatial dimensions. Once $\mathbf{\Theta}$ is computed, the DC component $I_{dc}$ and the linear coefficients $a$ and $b$ are extracted. The residual component is subsequently calculated as:
$$
\varepsilon(u,v) = I(u,v) - (I_{dc} + a \cdot u + b \cdot v)
$$

In addition to the decomposed physical components, extracting explicit geometric descriptors is necessary to guide the processing of non-Lambertian regions. While the linear coefficients $a$ and $b$ capture the global slope of the EPI, local angular variations require fine-grained gradient information. We compute the angular gradient map, denoted as $G_{ang} \in \mathbb{R}^{H \times W \times 2}$, by applying gradient operators along the $u$ and $v$ dimensions of the residual component $\varepsilon(u,v)$. This angular gradient highlights the local structural anomalies, such as the X-shaped patterns and bimodal distributions characteristic of specular reflections, providing a robust geometric pseudo-label for the subsequent non-Lambertian processing.

The outputs of the Three-Layer Angular Signal Decomposition module comprise the illumination feature $I_{dc}$, the disparity cues $a$ and $b$, the material reflection feature $\varepsilon(u,v)$, and the angular gradient map $G_{ang}$. These outputs establish a clear data flow for the dual-branch architecture. Specifically, the linear coefficients $a$ and $b$, concatenated with the raw EPI slices, are routed to the Lambertian EPI Branch to enforce angular cone constraints and regress depth for diffuse surfaces. Concurrently, the residual $\varepsilon(u,v)$ and the angular gradient $G_{ang}$ are directed to the Non-Lambertian Geometric Branch to capture local geometric anomalies and recover depth in reflective regions. By explicitly factorizing the angular signal at the input stage, our module prevents the entanglement of material and geometric features, substantially improving the depth estimation accuracy in challenging non-Lambertian scenarios compared to implicit end-to-end learning baselines.

## 3.3 Lambertian EPI 分支 (Lambertian EPI Branch)

Following the physical decoupling of angular signals, the Lambertian regions in the scene exhibit distinct linear structures in Epipolar Plane Images (EPIs), strictly adhering to the angular cone constraint. The primary objective of the Lambertian EPI Branch is to exploit these line structures while enforcing the piecewise smoothness of the depth surface, which is an inherent geometric property of Lambertian manifolds. Conventional deep learning approaches typically process EPIs using standard 3D convolutions, treating depth estimation as an unconstrained regression task. This paradigm often neglects the physical continuity of Lambertian surfaces, leading to depth fluctuations in textureless areas and boundary bleeding near occlusions. To address this limitation, we design a specialized branch that integrates continuous depth priors into the feature regression process.

The input to this branch is the EPI feature map $F_{EPI} \in \mathbb{R}^{H \times W \times 320}$, which is constructed by concatenating the linear coefficients (disparity cues) derived from the preceding Three-Layer Angular Signal Decomposition module with the central view image features. Let the spatial coordinates be denoted as $\mathbf{x} = (x, y)$. We first employ a series of convolutional layers to extract the intrinsic line structures from $F_{EPI}$. This feature extraction process is formulated as:
$$ F_{line}(\mathbf{x}) = \phi_{conv}(F_{EPI}(\mathbf{x})) $$
where $\phi_{conv}$ represents the convolutional mapping, and $F_{line} \in \mathbb{R}^{H \times W \times C_{mid}}$ is the intermediate feature map capturing the local EPI slopes.

To enforce the piecewise smoothness dictated by the angular cone constraint, we introduce a Plane-Regularized Sampling Operator (PRSO). Unlike standard spatial pooling that aggregates features isotropically, PRSO dynamically aligns the receptive field with the local depth plane. Specifically, for each pixel $\mathbf{x}$, the network predicts a local plane parameter vector $\mathbf{p}(\mathbf{x}) = [n_x, n_y, d]^T$, representing the surface normal components and the depth offset. The PRSO then aggregates the line features along this predicted plane. The mathematical formulation of the PRSO is given by:
$$ D_L(\mathbf{x}) = \text{PRSO}(F_{line}(\mathbf{x})) = \sum_{\mathbf{q} \in \mathcal{N}(\mathbf{x})} \omega(\mathbf{x}, \mathbf{q}; \mathbf{p}) \cdot F_{line}(\mathbf{q}) $$
where $D_L \in \mathbb{R}^{H \times W \times C_{epi}}$ is the output depth feature map for the Lambertian regions, $\mathcal{N}(\mathbf{x})$ denotes the local spatial neighborhood, and $\omega(\mathbf{x}, \mathbf{q}; \mathbf{p})$ is the plane-aware attention weight. The weight $\omega$ is computed based on the geometric consistency between the neighbor $\mathbf{q}$ and the local plane defined by $\mathbf{p}(\mathbf{x})$:
$$ \omega(\mathbf{x}, \mathbf{q}; \mathbf{p}) = \frac{\exp\left(-\gamma | (\mathbf{q} - \mathbf{x})^T [n_x, n_y]^T | \right)}{\sum_{\mathbf{k} \in \mathcal{N}(\mathbf{x})} \exp\left(-\gamma | (\mathbf{k} - \mathbf{x})^T [n_x, n_y]^T | \right)} $$
where $\gamma$ is a temperature parameter controlling the sharpness of the plane alignment. By weighting the feature aggregation according to the local surface orientation, the PRSO effectively suppresses noise and preserves sharp depth discontinuities at object boundaries.

Different from previous works that rely on black-box 3D CNNs to implicitly learn depth smoothness from data, our module explicitly incorporates the continuous depth prior through the PRSO. This design physically grounds the feature extraction, ensuring that the regression of $D_L$ strictly respects the piecewise planar assumption of Lambertian surfaces. The resulting Lambertian depth feature map $D_L$ is subsequently forwarded to the Dual-Mask Generation and Fusion module. In that subsequent stage, $D_L$ will be channel-balanced and fused with the features from the Non-Lambertian Geometric Branch, guided by the pixel-level domain classification masks, to yield the final unified depth estimation.

## 3.4 Non-Lambertian 几何分支 (Non-Lambertian Geometric Branch)

While the Lambertian EPI Branch effectively models surfaces adhering to the angular cone constraint, real-world scenes extensively contain non-Lambertian materials, such as specular highlights, translucent objects, and diffuse interreflections. These materials violate the linear epipolar constraint, manifesting as X-shaped patterns, dual-peak distributions, or curved trajectories in Epipolar Plane Images (EPIs). Conventional light field depth estimation methods predominantly rely on frequency-domain analysis or global EPI line structures, which inevitably suffer from spectral aliasing and structural distortion when processing these non-linear angular variations. To address this limitation, we design the Non-Lambertian Geometric Branch, which explicitly leverages geometric anomalies rather than spectral features to regress depth cues for non-Lambertian regions.

The input to this branch comprises the residual component $\epsilon(\mathbf{x}) \in \mathbb{R}^{C_\epsilon}$, the angular gradient feature $\nabla_{ang} I(\mathbf{x}) \in \mathbb{R}^2$, and the central view image $I_c(\mathbf{x}) \in \mathbb{R}^3$, all derived from the preceding Three-Layer Angular Signal Decomposition module. Here, $\mathbf{x} = (x,y)$ denotes the spatial coordinates, and the original concatenated input dimension is $H \times W \times C_{in}$, where $C_{in} = C_\epsilon + 2 + 3$. The residual $\epsilon(\mathbf{x})$ captures the deviation from the Lambertian linear model, serving as a direct indicator of material-induced reflectance variations. The angular gradient $\nabla_{ang} I(\mathbf{x})$ measures the intensity variation rate across different viewpoints, which is highly sensitive to specularities and scattering effects.

Rather than applying standard 3D convolutions that tend to blur these distinct geometric anomalies, we first construct a geometric anomaly representation. We compute the angular gradient magnitude $M_{ang}(\mathbf{x})$ and the residual energy $E_{\epsilon}(\mathbf{x})$ to quantify the local non-linearity:
$$ M_{ang}(\mathbf{x}) = \|\nabla_{ang} I(\mathbf{x})\|_2 $$
$$ E_{\epsilon}(\mathbf{x}) = \|\epsilon(\mathbf{x})\|_2^2 $$
These scalar maps are then concatenated with the original inputs to form the initial geometric feature tensor $F_{geo}^{(0)}(\mathbf{x}) \in \mathbb{R}^{C_{in} + 2}$:
$$ F_{geo}^{(0)}(\mathbf{x}) = \text{Concat}\left( \epsilon(\mathbf{x}), \nabla_{ang} I(\mathbf{x}), M_{ang}(\mathbf{x}), E_{\epsilon}(\mathbf{x}), I_c(\mathbf{x}) \right) $$
where $\text{Concat}(\cdot)$ denotes the channel-wise concatenation operation. This formulation explicitly encodes the physical deviations caused by non-Lambertian reflectance, providing the network with strong geometric priors.

To capture the local structural anomalies, such as the intersection points of X-shaped patterns in EPIs, we employ a hierarchical convolutional network. Let $F_{geo}^{(l)}(\mathbf{x})$ be the feature map at the $l$-th layer. The feature extraction process is formulated as:
$$ F_{geo}^{(l)}(\mathbf{x}) = \sigma \left( \sum_{\mathbf{k} \in \mathcal{K}} \mathcal{W}^{(l)}_{\mathbf{k}} F_{geo}^{(l-1)}(\mathbf{x} + \mathbf{k}) + \mathbf{b}^{(l)} \right) $$
where $\mathcal{W}^{(l)}$ and $\mathbf{b}^{(l)}$ represent the learnable convolutional weights and biases at layer $l$, respectively. $\mathcal{K}$ defines the spatial receptive field of the convolution kernel, and $\sigma(\cdot)$ is the ReLU activation function. By stacking $L$ convolutional layers, the network progressively aggregates local geometric contexts and suppresses noise in textureless non-Lambertian regions.

The final output of the Non-Lambertian Geometric Branch is the depth feature map for non-Lambertian regions, denoted as $F_{NL}(\mathbf{x})$:
$$ F_{NL}(\mathbf{x}) = F_{geo}^{(L)}(\mathbf{x}) $$
where $F_{NL} \in \mathbb{R}^{H \times W \times C_{geo}}$, and $C_{geo}$ is the channel dimension of the output features. 

Unlike prior approaches that treat non-Lambertian depth estimation as an unconstrained regression problem or rely on heavy global attention mechanisms, our module explicitly isolates and utilizes the physical geometric anomalies (angular gradients and residuals) decoupled by the signal decomposition module. This targeted feature extraction prevents the degradation of depth accuracy typically caused by spectral mixing in EPIs. The generated feature map $F_{NL}$, along with the Lambertian feature map $F_{line}$ from the parallel branch, is subsequently forwarded to the Dual-Mask Generation and Fusion module. In the subsequent module, the distinct channel dimensions ($C_{epi}$ and $C_{geo}$) are balanced via linear projection, and a pixel-wise domain classification mask is generated to adaptively fuse the depth predictions from both branches, ensuring a unified and accurate depth map across diverse material surfaces.

## 3.5 双掩码生成与融合模块 (Dual-Mask Generation and Fusion)

While the Lambertian EPI branch and the Non-Lambertian geometric branch independently regress depth cues for their respective surface types, real-world light field scenes consist of a complex mixture of both materials. An effective mechanism is required to dynamically and adaptively integrate the dual-branch predictions into a unified depth map. Existing light field depth estimation methods typically employ scene-level binary cross-entropy (BCE) losses or heuristic thresholding to distinguish material domains. Such approaches neglect pixel-level material transitions and local geometric anomalies, resulting in blurred boundaries and fusion artifacts at the interfaces of different materials. A significant architectural challenge also arises from the severe channel imbalance between the two branches; the Lambertian branch extracts high-dimensional EPI structural features (e.g., $C_L = 320$), whereas the Non-Lambertian branch relies on low-dimensional geometric cues (e.g., $C_{NL} = 3$). Direct concatenation biases the subsequent fusion network toward the high-dimensional features, degrading the contribution of the geometric branch. To address these limitations, we design the Dual-Mask Generation and Fusion module, which explicitly formulates a physically grounded, pixel-wise domain classification and balanced feature integration strategy.

The inputs to this module are the Lambertian feature map $F_L \in \mathbb{R}^{H \times W \times C_L}$, the Non-Lambertian feature map $F_{NL} \in \mathbb{R}^{H \times W \times C_{NL}}$, and the angular gradient prior $\nabla_{ang} I \in \mathbb{R}^{H \times W \times 2}$ derived from the Three-Layer Angular Signal Decomposition module. To mitigate the optimization bias caused by the extreme channel asymmetry ($C_L \gg C_{NL}$), we first apply a channel-balanced linear projection to map both feature representations into a unified latent space of dimension $C_{proj}$. This operation is formulated as:
$$ \hat{F}_L = \text{Proj}_L(F_L) = W_L * F_L + b_L $$
$$ \hat{F}_{NL} = \text{Proj}_{NL}(F_{NL}) = W_{NL} * F_{NL} + b_{NL} $$
where $W_L \in \mathbb{R}^{1 \times 1 \times C_L \times C_{proj}}$ and $W_{NL} \in \mathbb{R}^{1 \times 1 \times C_{NL} \times C_{proj}}$ denote the learnable convolutional kernels for the linear projections, $b_L \in \mathbb{R}^{C_{proj}}$ and $b_{NL} \in \mathbb{R}^{C_{proj}}$ are the corresponding bias terms, and $*$ represents the 2D convolution operation. The projected features $\hat{F}_L, \hat{F}_{NL} \in \mathbb{R}^{H \times W \times C_{proj}}$ have identical channel dimensions, ensuring that both the structural EPI cues and the geometric anomaly cues contribute equally to the subsequent mask generation process.

Following the projection, we generate a pixel-wise probability mask to identify the local material domain. Different from previous works that rely on sparse scene-level labels or heuristic rules, our module explicitly leverages the angular gradient $\nabla_{ang} I$ as a dense physical pseudo-label for supervision. The angular gradient inherently captures the local variation of the bidirectional reflectance distribution function (BRDF), providing a precise indicator of non-Lambertian reflections at the pixel level. We concatenate the projected features with the angular gradient prior and pass them through a multi-layer convolutional block to predict the domain classification mask $M$:
$$ M = \sigma \left( \text{Conv}_{mask} \left( [\hat{F}_L, \hat{F}_{NL}, \nabla_{ang} I] \right) \right) $$
where $[\cdot, \cdot]$ denotes the channel-wise concatenation operation, $\text{Conv}_{mask}$ represents a sequence of convolutional layers with ReLU activations that refine the spatial context, and $\sigma(\cdot)$ is the sigmoid activation function that constrains the output values to the range $[0, 1]$. The resulting mask $M \in \mathbb{R}^{H \times W \times 1}$ assigns a continuous probability to each pixel, indicating the likelihood of the surface being Lambertian. During training, $M$ is supervised by a pixel-wise binary cross-entropy loss computed against the binarized angular gradient magnitude, which enforces the network to learn sharp and physically consistent material boundaries without requiring expensive pixel-level ground truth material annotations.

With the pixel-wise domain mask $M$ established, the module performs a soft, adaptive fusion of the depth predictions from the two branches. Let $D_L \in \mathbb{R}^{H \times W \times 1}$ and $D_{NL} \in \mathbb{R}^{H \times W \times 1}$ denote the intermediate depth maps regressed by the Lambertian EPI branch and the Non-Lambertian geometric branch, respectively. The final unified depth map $D_{final}$ is computed via an element-wise weighted summation:
$$ D_{final} = M \odot D_L + (1 - M) \odot D_{NL} $$
where $\odot$ denotes the Hadamard (element-wise) product. In this formulation, pixels identified as Lambertian (where $M \to 1$) predominantly inherit the depth values from the EPI branch, which excels at modeling linear epipolar constraints. Conversely, pixels exhibiting strong non-Lambertian characteristics (where $M \to 0$) rely on the geometric branch, which robustly handles X-shaped patterns and dual-peak distributions. The module ultimately outputs the fused high-accuracy depth map $D_{final} \in \mathbb{R}^{H \times W \times 1}$ alongside the pixel-wise domain classification mask $M \in \mathbb{R}^{H \times W \times 1}$. 

This design yields significant improvements in handling complex mixed-material scenes. By explicitly balancing the feature channels and utilizing dense physical priors for mask supervision, the proposed module effectively eliminates the boundary blurring and depth discontinuities typically observed in conventional fusion strategies. The module effectively connects the dual-branch feature extraction to the final depth regression, ensuring that the physical decomposition performed in the initial stages is fully exploited during the final prediction. Consequently, the network not only achieves enhanced depth estimation accuracy across diverse material types but also provides an interpretable, pixel-level material segmentation as a useful byproduct, enhancing the capability of light field systems in understanding complex 3D environments.

## 3.6 Training Objective

### 3.6 Training Objective and Loss Function

The training objective of the proposed Unified Dual-Mask Physical Model is formulated to jointly optimize depth estimation and material-aware mask generation while enforcing physical consistency derived from the tri-layer angular signal decomposition. Unlike conventional light field depth estimation methods that apply uniform supervision across all angular variations, our formulation explicitly decouples the optimization process based on the underlying surface reflectance properties. This section details the mathematical derivation of the composite loss function, encompassing the dual-mask routed depth loss, the domain-aware mask classification loss, and the physical consistency regularization.

#### 3.6.1 Overall Formulation

The total training objective $\mathcal{L}_{total}$ is defined as a weighted sum of three distinct components:

$$
\mathcal{L}_{total} = \lambda_d \mathcal{L}_{depth} + \lambda_m \mathcal{L}_{mask} + \lambda_p \mathcal{L}_{phy}
$$

where $\mathcal{L}_{depth}$ represents the dual-mask routed depth estimation loss, $\mathcal{L}_{mask}$ denotes the domain-aware mask classification loss, and $\mathcal{L}_{phy}$ is the physical consistency regularization derived from the tri-layer decomposition model. The scalars $\lambda_d$, $\lambda_m$, and $\lambda_p$ are hyperparameters that balance the contributions of each term. This composite design ensures that the network simultaneously learns accurate geometric disparities and robust material boundaries.

#### 3.6.2 Dual-Mask Routed Depth Estimation Loss

**Motivation:** Standard depth regression losses apply uniform penalties across all pixels, which is suboptimal when the Epipolar Plane Image (EPI) geometric assumptions fail in non-Lambertian regions. Forcing a single branch to fit both strict EPI line structures and complex scattering patterns leads to gradient conflicts and degraded performance. 

**Design:** To address this, we employ a dual-mask routing mechanism that restricts the gradient flow to the corresponding specialized branch. The depth loss is formulated as a mask-weighted Mean Absolute Error (MAE):

$$
\mathcal{L}_{depth} = \frac{1}{N} \sum_{i=1}^{N} \Big[ M_L(i) \big| \hat{d}_{L,i} - d_i \big| + M_{NL}(i) \big| \hat{d}_{NL,i} - d_i \big| \Big]
$$

where $N$ is the total number of pixels in the training batch, and $i$ indexes the spatial pixel location. $d_i$ denotes the ground truth depth. $\hat{d}_{L,i}$ and $\hat{d}_{NL,i}$ are the depth predictions from the Lambertian and non-Lambertian branches, respectively. $M_L(i)$ and $M_{NL}(i)$ are the binary masks generated by the Geometric Dual-Mask module, satisfying $M_L(i) + M_{NL}(i) = 1$. 

**Expected Effect:** This formulation effectively decouples the gradient updates. The Lambertian branch focuses exclusively on minimizing errors in regions with valid EPI geometries, while the non-Lambertian branch learns to infer depth from defocus and scattering cues without being penalized for the inherent structural violations in specular regions.

#### 3.6.3 Domain-Aware Mask Classification Loss

**Motivation:** The extreme scarcity of non-Lambertian training data (e.g., only 4 scenes in the Non-Lambertian dataset compared to 170 in UrbanLF-Syn) introduces a severe class imbalance. Standard cross-entropy losses tend to degenerate into predicting the majority Lambertian class, resulting in poor recall for specular and scattering regions.

**Design:** We utilize a Focal Loss formulation to down-weight the contribution of easily classified Lambertian pixels and force the mask generator to prioritize hard-to-classify non-Lambertian regions:

$$
\mathcal{L}_{mask} = - \frac{1}{N} \sum_{i=1}^{N} \Big[ \alpha y_i (1 - p_i)^\gamma \log(p_i) + (1 - \alpha) (1 - y_i) p_i^\gamma \log(1 - p_i) \Big]
$$

where $y_i \in \{0, 1\}$ is the ground truth material label ($1$ for non-Lambertian, $0$ for Lambertian). $p_i$ represents the predicted probability of pixel $i$ belonging to the non-Lambertian class. The parameter $\alpha \in [0, 1]$ balances the importance between the two classes, and $\gamma > 0$ is the focusing parameter that modulates the rate at which easy examples are down-weighted.

**Expected Effect:** By dynamically scaling the loss based on prediction confidence, this objective substantially improves the mask generator's sensitivity to non-Lambertian boundaries, ensuring that the dual-branch architecture receives accurate routing signals even under severe data scarcity.

#### 3.6.4 Physical Consistency Regularization via Tri-Layer Decomposition

**Motivation:** Previous data-driven approaches struggle to generalize when EPI assumptions are physically violated. Different from previous works that rely solely on implicit feature learning, our tri-layer angular signal decomposition model explicitly separates the light field signal into physical components. We leverage this decomposition to construct differentiable physical priors that constrain the network within the valid physical boundaries of light field imaging.

**Design:** Based on the tri-layer decomposition model, the angular signal $I(u,v)$ at a specific spatial location is decomposed as:

$$
I(u,v) = I_{DC} + a \cdot u + b \cdot v + \epsilon(u,v)
$$

where $I_{DC}$ represents the ambient illumination (DC component), $(a, b)$ denotes the linear angular gradient corresponding to the EPI slope, and $\epsilon(u,v)$ is the residual component capturing material-specific reflectance or high-frequency texture. 

For a strictly Lambertian surface, the angular radiance is theoretically constant. Consequently, the residual component $\epsilon(u,v)$ should approach zero, and the linear components $(a, b)$ must fully describe the parallax. We formulate the residual regularization loss $\mathcal{L}_{res}$ to enforce this physical prior on the Lambertian regions identified by $M_L$:

$$
\mathcal{L}_{res} = \frac{1}{|\Omega_L|} \sum_{i \in \Omega_L} \big\| \epsilon^{(i)} \big\|_F^2
$$

where $\Omega_L = \{i \mid M_L(i) = 1\}$ is the set of Lambertian pixels, and $\|\cdot\|_F$ denotes the Frobenius norm of the residual angular map.

Simultaneously, the linear component dictates the EPI slope magnitude $k_i = \sqrt{a_i^2 + b_i^2}$, which is geometrically linked to the physical depth $d_i$. In the two-plane parameterization, the disparity is inversely proportional to depth. Let $\Psi(k_i)$ be the calibrated mapping function from the EPI slope to depth. We define the geometric consistency loss $\mathcal{L}_{geo}$ to align the network's depth prediction with the physically derived slope:

$$
\mathcal{L}_{geo} = \frac{1}{|\Omega_L|} \sum_{i \in \Omega_L} \big| \hat{d}_{L,i} - \Psi(k_i) \big|
$$

The total physical consistency regularization is the combination of these two constraints:

$$
\mathcal{L}_{phy} = \mathcal{L}_{res} + \beta \mathcal{L}_{geo}
$$

where $\beta$ balances the residual minimization and geometric alignment.

**Expected Effect:** This full derivation anchors the network predictions to the physical light field imaging model. By explicitly minimizing the residual energy in Lambertian regions and enforcing slope-depth geometric consistency, the regularization mitigates overfitting in data-scarce domains and provides a theoretically grounded mechanism to handle complex textures where EPI slopes become ambiguous.

#### 3.6.5 Optimization Strategy and Hyperparameter Settings

**Motivation:** The heterogeneous distribution of scenes across the HCInew (Lambertian), UrbanLF-Syn (Mixed/Urban), and Non-Lambertian datasets requires careful optimization strategies to prevent domain dominance and ensure stable convergence.

**Design:** The hyperparameters for the total loss are empirically set to $\lambda_d = 1.0$, $\lambda_m = 0.5$, and $\lambda_p = 0.1$, reflecting the primary importance of depth accuracy while maintaining sufficient gradient signals for mask generation and physical constraints. Within the Focal Loss, we set $\alpha = 0.75$ and $\gamma = 2.0$ to aggressively penalize misclassified non-Lambertian pixels. The geometric balance parameter is set to $\beta = 0.5$.

To complement the loss function, we integrate a `WeightedRandomSampler` during the data loading phase. This sampler assigns inverse-frequency weights to each domain, implementing domain-balanced sampling. The optimizer utilizes the AdamW algorithm with an initial learning rate of $9.99 \times 10^{-5}$ and a cosine annealing decay schedule. 

**Expected Effect:** The combination of the composite loss function and domain-balanced sampling maintains cross-domain exposure balance. This configuration prevents the model from overfitting to the abundant Lambertian and Urban scenes, thereby enhancing the cross-domain generalization capability and yielding robust depth estimates across mixed and non-Lambertian scenarios.
