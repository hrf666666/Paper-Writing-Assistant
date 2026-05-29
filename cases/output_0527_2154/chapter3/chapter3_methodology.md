# 3. Methodology

In this section, we present the overall architecture of the proposed Unified Dual-Mask Physical Model for non-Lambertian light field depth estimation. Different from previous works that primarily rely on single geometric cues and struggle with glossy or transparent surfaces, our framework explicitly decouples diffuse and specular reflections under a unified physical constraint. As illustrated in Fig. 1, the proposed architecture comprises five core components: an Angular FFT Feature Extractor, a Dual-Mask Generator, a Physical Reflection Separator, a Unified Depth Estimator, and a Depth Refinement Module. By integrating multi-directional epipolar plane image (EPI) processing with a domain-balanced training strategy, the model effectively addresses the challenge of depth estimation in complex mixed scenes, significantly improving robustness across Lambertian, non-Lambertian, and urban domains.

The input to our model consists of a light field sub-aperture image sequence (SAIs) and the central view image. Specifically, the SAIs are denoted as $\mathcal{I} \in \mathbb{R}^{N^2 \times 3 \times H \times W}$, where $N^2$ represents the total number of angular views, $3$ indicates the RGB channels, and $H \times W$ is the spatial resolution. The central view image is represented as $I_c \in \mathbb{R}^{3 \times H \times W}$. Before feeding into the network, we normalize the pixel intensities of $\mathcal{I}$ and $I_c$ to a standard range to stabilize the training process. These preprocessed inputs are then routed into parallel feature extraction branches to capture both angular frequency distributions and local spatial textures, providing a comprehensive representation for subsequent material classification and depth inference.

The overall data flow processes the inputs through a sequence of specialized modules to extract features and estimate depth. First, the SAIs $\mathcal{I}$ are simultaneously fed into the Angular FFT Feature Extractor and a shallow CNN. The Angular FFT Feature Extractor applies a 2D fast Fourier transform along the angular dimensions to obtain frequency features $F \in \mathbb{R}^{H \times W \times C_{out} \times F_u \times F_v}$, while the shallow CNN extracts spatial features $F_{spatial} \in \mathbb{R}^{H \times W \times C_{spatial}}$. Recognizing the resolution boundaries of pure angular frequency analysis, we concatenate these features in the Dual-Mask Generator to predict a pixel-wise diffuse mask $M_d$ and a specular mask $M_s$, both in $\mathbb{R}^{H \times W \times 1}$, regularized by a mutual exclusion loss. Subsequently, the Physical Reflection Separator utilizes $M_d$ and $M_s$ to decouple the original SAIs into a diffuse light field $L_d$ and a corrected specular light field $L_s$. Based on the Blinn-Phong rendering model, this decoupling is formulated as:
$$ L_d = M_d \odot \mathcal{I}, \quad L_s = M_s \odot (\mathcal{I} \cdot e^{-\alpha \cdot \Delta\theta}) $$
where $\odot$ denotes element-wise multiplication, and $\alpha$ is a view-dependent attenuation factor that corrects the specular highlights relative to the angular deviation $\Delta\theta$ to alleviate EPI slope discontinuities. These decoupled features, both in $\mathbb{R}^{N^2 \times C_{feat} \times H \times W}$, along with the dual masks, are then processed by the Unified Depth Estimator. This module constructs multi-directional EPIs to compute depth costs, leveraging physical constraints to regress an initial depth map $D_{init} \in \mathbb{R}^{H \times W \times 1}$ via a 3D CNN and soft-argmin operation.

To address the performance ceiling of EPI-based architectures in complex Lambertian regions and eliminate artifacts at depth discontinuities, we employ the Depth Refinement Module as the final post-processing stage. This module takes the initial depth map $D_{init}$ and the central view image $I_c$ as inputs. By leveraging the gradient information of $I_c$, it constructs edge-aware weights to perform local smoothing and edge sharpening through guided filtering. The refinement process for a target pixel $p$ is defined as:
$$ D_{final}(p) = \sum_{q \in \Omega} W(p, q) D_{init}(q) $$
where $\Omega$ is the local neighborhood, and the edge-aware weight $W(p, q)$ is proportional to $\exp(-\|I_c(p)-I_c(q)\|^2/\sigma_c^2 - \|p-q\|^2/\sigma_s^2)$, with $\sigma_c$ and $\sigma_s$ controlling the color and spatial variances, respectively. This process effectively suppresses structural distortions while preserving sharp object boundaries, outputting the final high-accuracy central view depth map $D_{final} \in \mathbb{R}^{H \times W \times 1}$. Through this unified pipeline, our model accurately recovers scene geometry, demonstrating substantial improvements in handling non-Lambertian reflections and complex texture-less areas.

## 3.2 角度FFT特征提取模块 (Angular FFT Feature Extractor)

The preprocessed SAIs are subsequently fed into the Angular FFT Feature Extractor to disentangle reflection components. Conventional light field depth estimation methods predominantly rely on geometric cues in the spatial or epipolar plane image domains. However, these methods encounter significant degradation when processing non-Lambertian surfaces. Physically, diffuse reflection exhibits smooth intensity variations across different viewpoints, whereas specular reflection demonstrates abrupt intensity changes due to view-dependent highlights. This physical distinction implies that diffuse and specular components occupy different frequency bands in the angular domain. Motivated by this observation, we design the Angular FFT Feature Extractor to explicitly transform angular signals into the frequency domain, thereby decoupling low-frequency diffuse characteristics from high-frequency specular properties.

The input to this module is the preprocessed SAI sequence, denoted as $\mathcal{I} \in \mathbb{R}^{N^2 \times 3 \times H \times W}$. To facilitate angular frequency analysis, we first reshape $\mathcal{I}$ into a 5D tensor $I \in \mathbb{R}^{H \times W \times 3 \times N \times N}$, where $(x, y)$ represents the spatial coordinates, $c \in \{0, 1, 2\}$ denotes the color channel, and $(u, v)$ indicates the angular coordinates with $u, v \in \{0, \dots, N-1\}$. 

For each spatial location $(x, y)$ and color channel $c$, we apply a 2D Fast Fourier Transform along the angular dimensions $(u, v)$. This operation converts the angular intensity variations into the frequency domain. The 2D FFT is mathematically formulated as:
$$ F(x, y, c, f_u, f_v) = \sum_{u=0}^{N-1} \sum_{v=0}^{N-1} I(x, y, c, u, v) e^{-i 2\pi \left( \frac{f_u u}{N} + \frac{f_v v}{N} \right)} $$
where $f_u, f_v \in \{0, \dots, N-1\}$ are the angular frequency coordinates, and $i$ is the imaginary unit. The resulting complex tensor $F$ contains both magnitude and phase information. Since the magnitude spectrum effectively captures the energy distribution of angular variations, we compute the magnitude $M(x, y, c, f_u, f_v) = |F(x, y, c, f_u, f_v)|$ to represent the angular frequency features.

To extract multi-scale frequency features and suppress noise, we introduce a set of learnable frequency filters. Different from standard spatial convolutions, these filters operate directly on the frequency coordinates to selectively amplify or attenuate specific frequency bands. The filtered frequency feature is computed as:
$$ \hat{F}(x, y, c, f_u, f_v) = M(x, y, c, f_u, f_v) \odot W_{freq}(f_u, f_v) $$
where $\odot$ denotes the element-wise multiplication, and $W_{freq} \in \mathbb{R}^{N \times N}$ is the learnable frequency weight matrix.

Subsequently, we project the filtered features into a higher-dimensional space to obtain the final angular frequency feature map. This projection is achieved through a linear transformation across the color channels:
$$ \mathcal{F}(x, y, k, f_u, f_v) = \sum_{c=0}^{2} \hat{F}(x, y, c, f_u, f_v) W_{k, c} + b_k $$
where $k \in \{0, \dots, C_{out}-1\}$ is the output channel index, $W_{k, c}$ represents the learnable projection weights, and $b_k$ is the bias term. The output of the Angular FFT Feature Extractor is the angular frequency feature map $\mathcal{F} \in \mathbb{R}^{H \times W \times C_{out} \times F_u \times F_v}$, where $F_u = N$ and $F_v = N$ are the angular frequency dimensions.

The extracted feature map $\mathcal{F}$ is then forwarded to the Dual-Mask Generator, which utilizes the distinct frequency distributions to predict pixel-level diffuse and specular masks. Different from previous works that implicitly learn reflection properties through deep spatial or EPI convolutions, our module explicitly leverages the physical frequency discrepancy between Lambertian and non-Lambertian reflections. By operating in the angular frequency domain, the proposed extractor provides a robust and physically grounded feature representation, significantly enhancing the subsequent reflection separation and depth estimation in complex mixed scenes.

## 3.3 双掩码生成模块 (Dual-Mask Generator)

Following the extraction of angular frequency features, we introduce the Dual-Mask Generator to predict pixel-level reflection attributes. Conventional light field depth estimation methods typically assume Lambertian surfaces or employ heuristic thresholding to detect specular highlights. These approaches often yield inaccurate masks, which subsequently degrades reflection separation and depth calculation. Different from previous works that rely on handcrafted spatial cues, our module explicitly leverages the decoupled angular frequency representations to generate physically plausible diffuse and specular masks. The primary objective of this module is to provide accurate, pixel-wise weighting maps that guide the subsequent physical reflection separation.

The Dual-Mask Generator takes two inputs: the angular frequency feature map $\mathcal{F} \in \mathbb{R}^{H \times W \times C_{out} \times F_u \times F_v}$ from the preceding Angular FFT Feature Extractor, and a spatial feature map $\mathcal{F}_{spatial} \in \mathbb{R}^{H \times W \times C_{spatial}}$. The spatial features are extracted from the sub-aperture images via a shallow convolutional neural network to supplement local geometric context. To align the dimensionalities and aggregate the frequency information, we first apply a global average pooling operation on $\mathcal{F}$ along the angular frequency dimensions. This operation compresses the 5D tensor into a 3D spatial-channel representation, formulated as:
$$
\mathcal{F}_{pool}(x, y, c) = \frac{1}{F_u F_v} \sum_{f_u=0}^{F_u-1} \sum_{f_v=0}^{F_v-1} \mathcal{F}(x, y, c, f_u, f_v)
$$
where $\mathcal{F}_{pool} \in \mathbb{R}^{H \times W \times C_{out}}$ denotes the pooled frequency feature, $(x, y)$ represents the spatial coordinates, $c \in \{0, \dots, C_{out}-1\}$ indicates the channel index, and $(f_u, f_v)$ are the angular frequency coordinates. 

Subsequently, we concatenate $\mathcal{F}_{pool}$ and $\mathcal{F}_{spatial}$ along the channel dimension to fuse the global angular frequency cues with local spatial context. The fused feature map is defined as $\mathcal{F}_{fuse} = [\mathcal{F}_{pool}, \mathcal{F}_{spatial}] \in \mathbb{R}^{H \times W \times (C_{out} + C_{spatial})}$. To predict the reflection masks, we pass $\mathcal{F}_{fuse}$ through multiple convolutional layers followed by a Sigmoid activation function. The diffuse mask $M_d$ and the specular mask $M_s$ are computed as:
$$
M_d = \sigma(\mathcal{W}_d * \mathcal{F}_{fuse} + b_d)
$$
$$
M_s = \sigma(\mathcal{W}_s * \mathcal{F}_{fuse} + b_s)
$$
where $*$ denotes the 2D convolution operation, $\mathcal{W}_d$ and $\mathcal{W}_s$ are the learnable convolutional weights, $b_d$ and $b_s$ are the corresponding biases, and $\sigma(\cdot)$ is the Sigmoid function that constrains the output values to the range $[0, 1]$. Both $M_d$ and $M_s$ have the dimension of $H \times W \times 1$.

To ensure the physical plausibility of the generated masks, we introduce a mutual exclusivity constraint. In physical rendering, diffuse and specular reflections at a specific pixel are typically mutually exclusive or exhibit an inverse relationship. We enforce this property by adding a mutual exclusivity loss $\mathcal{L}_{mutual}$ during training, defined as:
$$
\mathcal{L}_{mutual} = \frac{1}{HW} \sum_{x=0}^{H-1} \sum_{y=0}^{W-1} M_d(x, y) \cdot M_s(x, y)
$$
This loss penalizes the simultaneous activation of both masks at the same spatial location, thereby encouraging the network to learn distinct and physically consistent reflection regions.

The output masks $M_d$ and $M_s$ are then fed into the Physical Reflection Separator. By utilizing these explicit masks, the subsequent module can accurately decouple the original light field into diffuse and specular components. Compared to existing methods that process mixed reflections directly, our Dual-Mask Generator significantly enhances the disentanglement capability by integrating angular frequency analysis with spatial context, ultimately improving the robustness of depth estimation on non-Lambertian surfaces.

## 3.4 物理反射分离模块 (Physical Reflection Separator)

Following the generation of pixel-level reflection attributes, we introduce the Physical Reflection Separator to decouple the raw light field signals. In light field depth estimation, the geometric consistency relies heavily on the slope continuity of Epipolar Plane Images (EPIs). However, non-Lambertian surfaces, particularly specular highlights, violate the photo-consistency assumption. The reflection intensity varies significantly across different viewpoints, causing severe slope discontinuities and pseudo-textures in EPIs. Existing methods typically address this by masking out specular regions or treating them as noise, which inevitably leads to missing or inaccurate depth predictions in these areas. To address this limitation, the primary objective of our module is to explicitly separate the light field into diffuse and specular components and physically rectify the specular distortions, thereby restoring the geometric consistency required for accurate depth estimation.

The Physical Reflection Separator takes three inputs: the original light field sub-aperture images (SAIs) $\mathbf{I} \in \mathbb{R}^{N^2 \times 3 \times H \times W}$, the diffuse mask $\mathcal{M}_d \in \mathbb{R}^{H \times W \times 1}$, and the specular mask $\mathcal{M}_s \in \mathbb{R}^{H \times W \times 1}$ predicted by the preceding Dual-Mask Generator. Here, $N^2$ denotes the total number of viewpoints, $3$ represents the RGB channels, and $H \times W$ is the spatial resolution. We first process the diffuse component. According to the Lambertian reflection model, the diffuse radiance remains constant regardless of the viewing direction. Therefore, we extract the diffuse light field by applying the diffuse mask as a spatial weight to the original SAIs. This operation is formulated as:
$$
\mathbf{L}_d^{raw} = \mathcal{M}_d \odot \mathbf{I}
$$
where $\mathbf{L}_d^{raw} \in \mathbb{R}^{N^2 \times 3 \times H \times W}$ is the separated diffuse light field, and $\odot$ denotes the element-wise multiplication with $\mathcal{M}_d$ broadcasted across the angular and channel dimensions. This step effectively isolates the view-invariant geometric structures from the raw input.

For the specular component, the reflection behavior is governed by the Blinn-Phong physical rendering model, where the specular intensity depends on the angle between the viewing direction and the half-vector. In a light field, as the viewpoint shifts away from the optimal reflection angle, the specular highlight exhibits a physical attenuation. To compensate for this view-dependent intensity variation and alleviate the EPI slope discontinuity, we introduce a physical correction mechanism. Let $(u, v)$ denote the angular coordinates of a specific viewpoint, and $(u_c, v_c)$ denote the coordinates of the central viewpoint. We first calculate the angular displacement $\Delta\theta_{u,v}$ for each view:
$$
\Delta\theta_{u,v} = \sqrt{(u - u_c)^2 + (v - v_c)^2}
$$
Based on this displacement, we construct a view-dependent attenuation factor to model the specular decay. The corrected specular light field is then computed as:
$$
\mathbf{L}_s^{raw} = \mathcal{M}_s \odot \left( \mathbf{I} \cdot e^{-\alpha \cdot \Delta\theta} \right)
$$
where $\mathbf{L}_s^{raw} \in \mathbb{R}^{N^2 \times 3 \times H \times W}$ is the physically corrected specular light field. The term $e^{-\alpha \cdot \Delta\theta}$ represents the attenuation factor applied along the angular dimension, and $\alpha$ is a learnable decay parameter that controls the attenuation rate, effectively representing the surface roughness in the Blinn-Phong model. By multiplying the original SAIs with this factor before applying the specular mask $\mathcal{M}_s$, we explicitly rectify the intensity inconsistencies caused by viewpoint shifts.

To align the separated physical components with the subsequent depth estimation network, we pass $\mathbf{L}_d^{raw}$ and $\mathbf{L}_s^{raw}$ through a shared feature embedding network, denoted as $\Phi(\cdot)$, which consists of shallow convolutional layers. This transforms the 3-channel RGB signals into high-dimensional feature representations:
$$
\mathcal{L}_d = \Phi(\mathbf{L}_d^{raw}), \quad \mathcal{L}_s = \Phi(\mathbf{L}_s^{raw})
$$
where $\mathcal{L}_d$ and $\mathcal{L}_s$ are the final diffuse and specular light field features, both possessing the dimension of $\mathbb{R}^{N^2 \times C_{feat} \times H \times W}$, with $C_{feat}$ being the feature channel size. 

Different from previous works that simply discard specular regions or rely on heuristic thresholding to suppress highlights, our module explicitly leverages the Blinn-Phong physical rendering model to decouple and rectify the light field signals. This physics-driven separation ensures that the geometric structures within specular regions are preserved and corrected, rather than being treated as invalid outliers. The resulting decoupled features $\mathcal{L}_d$ and $\mathcal{L}_s$, along with the dual masks $\mathcal{M}_d$ and $\mathcal{M}_s$, are subsequently fed into the Unified Depth Estimator. This seamless data flow enables the downstream module to construct distinct cost volumes for diffuse and specular regions, ultimately facilitating robust and comprehensive depth estimation across complex non-Lambertian surfaces.

## 3.5 统一深度估计模块 (Unified Depth Estimator)

Following the decoupling and physical rectification of light field signals, we introduce the Unified Depth Estimator to compute the initial depth map. As illustrated in the overall architecture, this module bridges the physical reflection separation and the final depth refinement. In light field depth estimation, conventional methods heavily rely on the photo-consistency assumption, which holds for Lambertian surfaces but fails for non-Lambertian regions. Existing approaches typically mask out specular highlights or treat them as outliers, inevitably resulting in missing or inaccurate depth predictions in these areas. Different from previous works that discard specular information, our module explicitly leverages both diffuse and specular components to achieve robust depth estimation across the entire scene. The primary objective of this module is to construct a unified cost volume that integrates the traditional photo-consistency for diffuse regions and the physically constrained disparity consistency for specular regions.

The Unified Depth Estimator takes four inputs: the diffuse light field features $\mathbf{L}_d \in \mathbb{R}^{N^2 \times C_{feat} \times H \times W}$, the rectified specular light field features $\mathbf{L}_s \in \mathbb{R}^{N^2 \times C_{feat} \times H \times W}$, the diffuse mask $\mathcal{M}_d \in \mathbb{R}^{H \times W \times 1}$, and the specular mask $\mathcal{M}_s \in \mathbb{R}^{H \times W \times 1}$. Here, $N^2$ is the total number of viewpoints, $C_{feat}$ denotes the feature channels, and $H \times W$ represents the spatial resolution. 

We first construct Epipolar Plane Images from the input features. For a given spatial coordinate $(x, y)$ and a hypothetical depth $d$, the corresponding disparity is calculated as $p = f \cdot B / d$, where $f$ is the focal length and $B$ is the baseline distance. We sample the features along the epipolar lines to form the diffuse and specular feature volumes, denoted as $\mathbf{V}_d(d)$ and $\mathbf{V}_s(d)$, respectively. 

For the diffuse regions, we compute the depth cost $C_{diffuse}(d)$ based on the traditional photo-consistency assumption. Since the diffuse reflection exhibits stable intensity across different viewpoints, we evaluate the variance of the sampled features along the angular dimension:
$$
C_{diffuse}(d) = \frac{1}{N^2} \sum_{u=1}^{N} \sum_{v=1}^{N} \left\| \mathbf{V}_d(u, v, d) - \bar{\mathbf{V}}_d(d) \right\|_2^2
$$
where $\mathbf{V}_d(u, v, d)$ represents the feature vector at viewpoint $(u, v)$ for depth $d$, and $\bar{\mathbf{V}}_d(d) = \frac{1}{N^2} \sum_{u,v} \mathbf{V}_d(u, v, d)$ is the mean feature vector across all viewpoints. A lower variance indicates higher photo-consistency, thus a higher probability of the correct depth.

For the specular regions, the photo-consistency assumption is inherently violated due to view-dependent reflection. However, benefiting from the physical rectification in the preceding module, the slope discontinuities in the specular Epipolar Plane Images are significantly mitigated. To further enforce geometric consistency, we compute the specular depth cost $C_{specular}(d)$ using a physically constrained disparity consistency metric. Specifically, we incorporate a view-dependent weight $\mathbf{W}_{spec}$ derived from the physical reflection model to penalize deviations:
$$
C_{specular}(d) = \frac{1}{N^2} \sum_{u=1}^{N} \sum_{v=1}^{N} \mathbf{W}_{spec}(u, v) \odot \left\| \mathbf{V}_s(u, v, d) - \bar{\mathbf{V}}_s(d) \right\|_2^2
$$
where $\mathbf{W}_{spec}(u, v)$ is the physical attenuation weight for viewpoint $(u, v)$, and $\bar{\mathbf{V}}_s(d)$ is the mean specular feature vector. This formulation ensures that viewpoints with severe specular distortions contribute less to the cost aggregation, thereby enhancing the robustness of the depth estimation in highlight areas.

To unify the depth cues from both reflection components, we fuse the diffuse and specular costs using the predicted dual masks. The unified raw cost volume $C(d)$ is formulated as:
$$
C(d) = \mathcal{M}_d \odot C_{diffuse}(d) + \mathcal{M}_s \odot C_{specular}(d)
$$
where $\odot$ denotes the element-wise multiplication. This adaptive fusion strategy explicitly assigns the appropriate cost metric to each pixel based on its physical reflection attribute, avoiding the interference between diffuse and specular signals.

Subsequently, we employ a 3D Convolutional Neural Network to regularize the raw cost volume. The network aggregates contextual information across spatial and depth dimensions, yielding the regularized cost volume $C_{reg}(d)$:
$$
C_{reg}(d) = \text{3DCNN}(C(d))
$$
Finally, we regress the initial depth map $\mathbf{D}_{init} \in \mathbb{R}^{H \times W \times 1}$ using the differentiable Soft-Argmin operation. This operation computes the expected depth value by taking the softmax-weighted sum over all hypothetical depth candidates:
$$
\mathbf{D}_{init} = \sum_{d=d_{min}}^{d_{max}} d \cdot \frac{e^{-C_{reg}(d)}}{\sum_{d'=d_{min}}^{d_{max}} e^{-C_{reg}(d')}}
$$
where $d_{min}$ and $d_{max}$ define the predefined depth search range. The Soft-Argmin regression allows for sub-pixel depth accuracy and facilitates end-to-end training.

The output of this module, the initial depth map $\mathbf{D}_{init}$, provides a comprehensive geometric representation of the scene, including both Lambertian and non-Lambertian regions. This initial estimation is then forwarded to the subsequent Depth Refinement Module, which utilizes the central view image to perform edge-preserving smoothing and output the final high-precision depth map. By explicitly integrating physical reflection properties into the cost volume construction, our Unified Depth Estimator substantially improves depth accuracy in challenging specular regions compared to conventional photo-consistency-based methods.

## 3.6 深度细化模块 (Depth Refinement Module)

Following the depth regression in the Unified Depth Estimator, the initial depth map $\mathbf{D}_{init}$ often exhibits blurred boundaries and local artifacts at depth discontinuities. This degradation primarily stems from the discrete nature of light field viewpoints and the inherent smoothing effect during cost volume regularization. To address this issue, we introduce the Depth Refinement Module to recover sharp edges and high-precision depth details. Different from previous works that apply generic post-processing filters which often cause depth bleeding in non-Lambertian regions, our module explicitly leverages the structural gradients of the central view image to construct an edge-aware weighting mechanism. Since the preceding Physical Reflection Separator effectively mitigates highlight-induced texture corruption, the central view image provides reliable structural cues, enabling accurate alignment of depth discontinuities with true object boundaries.

The Depth Refinement Module takes two inputs: the initial depth map $\mathbf{D}_{init} \in \mathbb{R}^{H \times W \times 1}$ generated by the Unified Depth Estimator, and the central view image $\mathbf{I}_c \in \mathbb{R}^{H \times W \times 3}$. The primary objective is to refine $\mathbf{D}_{init}$ into the final high-precision depth map $\mathbf{D}_{final} \in \mathbb{R}^{H \times W \times 1}$ by performing local smoothing while preserving sharp edges. We formulate this process as an edge-aware graph convolution operation, which generalizes traditional guided filtering into a differentiable framework. For each pixel $p$ in the spatial domain, the refined depth value $D_{final}(p)$ is computed by aggregating the initial depth values from its local neighborhood $\Omega_p$:
$$ D_{final}(p) = \sum_{q \in \Omega_p} W(p, q) D_{init}(q) $$
where $p$ and $q$ denote 2D spatial coordinates, and $\Omega_p$ represents a local spatial window centered at $p$. The term $W(p, q)$ is the edge-aware weight that measures the structural similarity between pixel $p$ and its neighbor $q$.

To explicitly utilize the gradient information of the central view image, we define the weight $W(p, q)$ by combining both photometric similarity and spatial proximity. The weight is mathematically formulated as:
$$ W(p, q) = \frac{1}{Z_p} \exp\left( - \frac{\| \mathbf{I}_c(p) - \mathbf{I}_c(q) \|^2}{\sigma_c^2} - \frac{\| p - q \|^2}{\sigma_s^2} \right) $$
where $Z_p = \sum_{q \in \Omega_p} \exp\left( - \frac{\| \mathbf{I}_c(p) - \mathbf{I}_c(q) \|^2}{\sigma_c^2} - \frac{\| p - q \|^2}{\sigma_s^2} \right)$ is the normalization factor ensuring that the weights sum to one. The parameters $\sigma_c$ and $\sigma_s$ are bandwidth variables that control the sensitivity to photometric differences and spatial distances, respectively. The operator $\| \cdot \|$ denotes the Euclidean norm. In our implementation, to enhance edge perception, the central view image $\mathbf{I}_c$ is augmented with its spatial gradients before computing the photometric distance, allowing the weight to strongly penalize depth interpolation across high-gradient boundaries. Furthermore, instead of using fixed empirical values, we parameterize $\sigma_c$ and $\sigma_s$ as learnable variables, enabling the network to adaptively adjust the filtering strength for different texture regions during end-to-end training.

Through this edge-aware aggregation, the Depth Refinement Module effectively eliminates pseudo-artifacts at depth discontinuities and sharpens object boundaries. The output is the final refined depth map $\mathbf{D}_{final} \in \mathbb{R}^{H \times W \times 1}$, which exhibits significantly improved accuracy and structural fidelity compared to the initial prediction. By tightly coupling the physical reflection separation with the edge-aware refinement, our overall architecture successfully addresses the depth estimation challenges in complex non-Lambertian scenes.

## 3.7 Training Objective

### 3.7 Training Objective and Loss Function

**Intuition and Motivation**
Light field depth estimation aims to recover precise disparity maps from multi-view images. However, non-Lambertian surfaces (e.g., specular and glossy materials) violate the photo-consistency assumption, leading to significant depth distortions. Furthermore, our unified framework processes multi-directional Epipolar Plane Images (EPIs) and employs a dual-mask mechanism to handle diverse material properties. Therefore, the training objective must not only minimize the pixel-wise disparity error but also enforce geometric consistency across different EPI directions and respect the physical boundaries defined by the dual masks. Different from previous works that rely solely on standard regression losses, our loss function explicitly incorporates mask-aware regularization and multi-directional geometric constraints to unify the optimization across Lambertian, non-Lambertian, and mixed domains.

**Formalism and Overall Architecture**
Let $\mathcal{D} = \{(\mathcal{L}_i, \mathbf{M}^{med}_i, \mathbf{M}^{ang}_i, \mathbf{D}^{gt}_i)\}_{i=1}^N$ denote the training dataset, where $\mathcal{L}_i$ is the input light field, $\mathbf{M}^{med}_i$ and $\mathbf{M}^{ang}_i$ are the medium mask and angular direction mask, respectively, and $\mathbf{D}^{gt}_i$ is the ground truth disparity map. The predicted disparity map is denoted as $\mathbf{D}^{pred}_i = f_\theta(\mathcal{L}_i, \mathbf{M}^{med}_i, \mathbf{M}^{ang}_i)$, where $f_\theta$ represents the EPINet4Dir V3 network with parameters $\theta$.

The overall training objective $\mathcal{L}_{total}$ is formulated as a weighted sum of four distinct components:
$$ \mathcal{L}_{total} = \lambda_{data} \mathcal{L}_{data} + \lambda_{smooth} \mathcal{L}_{smooth} + \lambda_{mask} \mathcal{L}_{mask} + \lambda_{epi} \mathcal{L}_{epi} $$
where $\lambda_{data}$, $\lambda_{smooth}$, $\lambda_{mask}$, and $\lambda_{epi}$ are the balancing weights. We detail each component below.

**1. Data Fidelity Loss ($\mathcal{L}_{data}$)**
*Motivation:* The primary goal is to accurately regress the disparity values. While L2 loss is commonly used, it is sensitive to outliers, which are prevalent in non-Lambertian regions due to specular highlights.
*Design:* We employ the L1 loss to measure the pixel-wise discrepancy between the predicted and ground truth disparity maps. For a single sample, it is defined as:
$$ \mathcal{L}_{data} = \frac{1}{|\Omega|} \sum_{p \in \Omega} \left| \mathbf{D}^{pred}(p) - \mathbf{D}^{gt}(p) \right| $$
where $\Omega$ denotes the set of valid spatial pixels, and $p$ represents the spatial coordinate.
*Expected Effect:* The L1 norm provides robust gradient updates in the presence of disparity outliers, ensuring stable convergence across mixed domains.

**2. Mask-Aware Edge-Preserving Smoothness Loss ($\mathcal{L}_{smooth}$)**
*Motivation:* Depth maps should be piecewise smooth, with sharp discontinuities only at object boundaries. Standard smoothness losses often blur edges. Moreover, non-Lambertian reflections can introduce false edges in the image domain that do not correspond to physical depth boundaries.
*Design:* We introduce a mask-aware edge-preserving smoothness loss. The medium mask $\mathbf{M}^{med}$ guides the smoothing process to prevent penalizing depth gradients across different material boundaries. It is formulated as:
$$ \mathcal{L}_{smooth} = \frac{1}{|\Omega|} \sum_{p \in \Omega} \left( \left| \nabla_x \mathbf{D}^{pred}(p) \right| e^{-\left| \nabla_x \mathbf{I}_{cen}(p) \right| \cdot \mathbf{M}^{med}(p)} + \left| \nabla_y \mathbf{D}^{pred}(p) \right| e^{-\left| \nabla_y \mathbf{I}_{cen}(p) \right| \cdot \mathbf{M}^{med}(p)} \right) $$
where $\nabla_x$ and $\nabla_y$ denote the spatial gradients, and $\mathbf{I}_{cen}$ is the central view image.
*Expected Effect:* By modulating the image gradients with the medium mask, the network explicitly preserves depth discontinuities at true physical boundaries while suppressing false depth edges caused by specular reflections.

**3. Dual-Mask Consistency Regularization ($\mathcal{L}_{mask}$)**
*Motivation:* The proposed dual-mask mechanism provides explicit physical priors. The network's intermediate features should align with these physical priors to avoid overfitting to domain-specific artifacts.
*Design:* We enforce a consistency constraint between the predicted disparity gradients and the angular direction mask $\mathbf{M}^{ang}$. The angular mask highlights reliable EPI directions for each pixel. The regularization is defined as:
$$ \mathcal{L}_{mask} = \frac{1}{|\Omega|} \sum_{p \in \Omega} \left\| \nabla \mathbf{D}^{pred}(p) \odot (\mathbf{1} - \mathbf{M}^{ang}(p)) \right\|_2^2 $$
where $\odot$ denotes the Hadamard product, and $\mathbf{1}$ is a matrix of ones.
*Expected Effect:* This term penalizes depth variations in angular directions deemed unreliable by the angular mask, effectively forcing the model to rely on geometrically consistent EPI structures for depth inference.

**4. Multi-Directional EPI Geometric Consistency Loss ($\mathcal{L}_{epi}$)**
*Motivation:* Our EPINet4Dir V3 architecture processes EPIs from multiple directions. Disparity predictions derived from different directional EPIs should be geometrically consistent, as they represent the same 3D scene.
*Design:* Let $\mathbf{D}^{pred}_d$ be the intermediate disparity prediction from the $d$-th directional branch, where $d \in \{h, v, d_1, d_2\}$. We compute the variance among these directional predictions to enforce consensus:
$$ \mathcal{L}_{epi} = \frac{1}{|\Omega|} \sum_{p \in \Omega} \frac{1}{N_d} \sum_{d} \left( \mathbf{D}^{pred}_d(p) - \bar{\mathbf{D}}^{pred}(p) \right)^2 $$
where $N_d$ is the number of directions, and $\bar{\mathbf{D}}^{pred}(p) = \frac{1}{N_d} \sum_{d} \mathbf{D}^{pred}_d(p)$ is the mean prediction.
*Expected Effect:* This geometric constraint mitigates directional biases and ensures that the final fused depth map is physically plausible, significantly improving robustness in texture-less and non-Lambertian regions.

**Weight Settings and Justification**
The balancing weights are empirically set to $\lambda_{data} = 1.0$, $\lambda_{smooth} = 0.1$, $\lambda_{mask} = 0.05$, and $\lambda_{epi} = 0.2$. We assign the highest value to $\lambda_{data}$ to prioritize accurate disparity regression, which directly optimizes the primary evaluation metric. The parameters $\lambda_{smooth}$ and $\lambda_{mask}$ are assigned smaller values to act as auxiliary regularizers, preventing the suppression of valid high-frequency depth details. Furthermore, $\lambda_{epi}$ is set to 0.2 to provide a substantial geometric constraint without overwhelming the primary data fidelity term, ensuring stable multi-directional feature fusion.

**Integration with Domain-Balanced Sampling**
To address the severe data imbalance among the Lambertian, non-Lambertian, and mixed domains, the loss computation is integrated with our domain-balanced sampling strategy. During each training iteration, batches are constructed to ensure equal representation from each domain. Consequently, the gradients derived from $\mathcal{L}_{total}$ are uniformly distributed across different material properties. This integration prevents the model from biasing towards the majority domain and enables robust generalization to the scarce non-Lambertian scenes.
