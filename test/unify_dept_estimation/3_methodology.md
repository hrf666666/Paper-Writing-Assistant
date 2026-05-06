## 3. Methodology

In this section, we present the Unified Dual-Mask Physical Model for non-Lambertian light field depth estimation. The proposed framework bridges the gap between rigorous electromagnetic wave optics and learnable geometric representations. As illustrated in the overall architecture, our method consists of four core modules: (1) a Dual-Mask Encoder that extracts the Medium Mask and Angular Direction Mask from multi-view light field inputs, explicitly decomposing the light-matter interaction into interaction-type classification and wave-vector deflection; (2) a Physical Interaction Module that routes features through physics-specific computation paths (Fresnel reflectance, Rayleigh/Mie scattering, and micro-facet BRDF) based on the classified interaction type; (3) a Depth Decoder that constructs a cost volume from physically-enhanced angular features to predict dense depth maps; and (4) a Differentiable Rendering Layer that enforces forward physical consistency by constraining the network outputs to adhere to Maxwell's equations and energy conservation principles. 

### 3.1 Dual-Mask Encoder

Traditional light field depth estimation methods typically rely on implicit angular feature concatenation or explicit epipolar plane image (EPI) analysis, both of which fundamentally assume Lambertian reflectance or fail to disentangle the physical causes of angular variations <citation>["LFNet", "EPI2F"]</citation>. Under non-Lambertian conditions, the angular deviation of light rays is governed by complex boundary conditions defined by Maxwell's equations. Simply mapping angular patches to depth ignores the underlying physics, leading to severe ambiguities in specular or scattering regions. To resolve this, we propose the Dual-Mask Encoder, which explicitly abstracts the electromagnetic light-matter interaction into two learnable, physically interpretable representations: the Medium Mask and the Angular Direction Mask.

The core intuition stems from the scale relationship between the wavelength of incident light $\lambda$ and the characteristic scale of the surface micro-structure $a(x,y)$. According to electromagnetic theory, the dominant interaction type—whether specular reflection, diffuse scattering, or resonant Mie scattering—is strictly determined by this ratio. We define the Medium Mask as $r(x,y) = a(x,y)/\lambda$. This mask serves as a physical routing indicator:
<formula>
r(x,y) = \frac{a(x,y)}{\lambda} = \begin{cases} 
\ll 1 & \text{Rayleigh scattering dominant} \\
\approx 1 & \text{Mie resonant scattering dominant} \\
\gg 1 & \text{Geometric optics (Specular/Diffuse) dominant}
\end{cases}
</formula>
Crucially, the Lambertian model is naturally reduced to a special case of our unified framework when $r(x,y) \gg 1$ and the angular distribution exhibits isotropic cosine weighting. By explicitly predicting $r(x,y)$, the network identifies the physical regime governing each pixel, replacing the blind feature extraction of standard CNNs with physics-guided routing.

While the Medium Mask classifies *what* type of interaction occurs, the Angular Direction Mask $V(x,y,\theta_i)$ describes *how* the wave vectors are deflected. Under phase matching conditions at the physical boundary, the tangential components of the incident and scattered wave vectors must be conserved. $V(x,y,\theta_i)$ captures the resulting angular deflection distribution for a given incident angle $\theta_i$. We formulate the extraction of $V(x,y,\theta_i)$ as an angular convolution problem over the sub-aperture views:
<formula>
V(x,y,\theta_i) = \sigma\left( \mathbf{W}_v * \left[ I_{\theta_1}(x,y), \dots, I_{\theta_N}(x,y) \right] + b_v \right)
</formula>
where $*$ denotes the angular convolution, $I_{\theta_k}$ represents the sub-aperture image at angular coordinate $\theta_k$, and $\mathbf{W}_v, b_v$ are the learnable parameters. Unlike existing methods that treat angular views as a simple sequence <citation>["EPINET"]</citation>, our formulation enforces that $V(x,y,\theta_i)$ explicitly represents the phase-matched wave vector distribution. Specifically, the angular convolution kernels are parameterized to extract the spatial frequency spectrum across views, which intrinsically corresponds to the tangential wave-vector components. The activation function $\sigma$ serves as a differentiable approximation of a step function that selects admissible wave-vectors satisfying the phase matching boundary condition ($k_{t,incident} = k_{t,scattered}$), thereby bridging the gap between CNN implementations and rigorous electromagnetic constraints. The Dual-Mask Encoder is implemented as a weight-sharing Siamese network processing the angular views, followed by separate prediction heads for $r(x,y)$ and $V(x,y,\theta_i)$, ensuring that the extracted features are strictly anchored to electromagnetic first principles.

### 3.2 Physical Interaction Module

Standard feed-forward networks struggle to simultaneously model the distinct boundary conditions of specular, scattering, and diffuse interactions due to the fundamentally different mathematical forms of their respective electromagnetic solutions. To address this, we introduce the Physical Interaction Module, which dynamically routes the spatial features $F_{in}(x,y)$ through physics-specific computation paths based on the Medium Mask $r(x,y)$ <citation>["dynamic_routing_dl", "physics_informed_nn"]</citation>. This design choice ensures that the feature representation strictly adheres to the governing physical laws of the identified interaction type, rather than attempting a compromised, ill-posed global approximation.

The module consists of three parallel branches, each implementing a distinct physical model:
1.  **Specular Path:** Governed by Fresnel's equations for smooth surfaces ($r \gg 1$, coherent reflection). The feature update is modulated by the Fresnel reflectance $F(\theta_i)$, preserving high-frequency angular coherence. To maintain mathematical rigor, rather than treating the high-dimensional feature tensor $F_{in}(x,y)$ as a literal electromagnetic amplitude, we interpret its channels as encoding latent variables representing the spatial energy distribution of the interaction. The scalar $F(\theta_i)$ thus acts as a channel-wise physical gate that scales the latent energy distribution according to the physical reflectance:
    <formula>
    F_{spec}(x,y) = F_{in}(x,y) \cdot F(\theta_i) = F_{in}(x,y) \cdot \frac{1}{2}\left( \left|\frac{n_1\cos\theta_i - n_2\cos\theta_t}{n_1\cos\theta_i + n_2\cos\theta_t}\right|^2 + \left|\frac{n_2\cos\theta_i - n_1\cos\theta_t}{n_2\cos\theta_i + n_1\cos\theta_t}\right|^2 \right)
    </formula>
    where the scalar multiplication is broadcast across feature channels, $n_1, n_2$ are the refractive indices estimated from the latent features, and $\theta_t$ is the transmitted angle derived from Snell's law.
2.  **Scattering Path:** Governed by Rayleigh ($r \ll 1$) and Mie ($r \approx 1$) phase functions. We model the feature scattering as an angular diffusion process weighted by the phase function $P(\theta_i, \theta_o)$:
    <formula>
    F_{scat}(x,y) = \int_{\Omega} F_{in}(x,y) \cdot P(\theta_i, \theta_o) V(x,y,\theta_o) d\theta_o
    </formula>
    This path explicitly utilizes the Angular Direction Mask to aggregate features along the physically plausible scattering lobes, effectively filtering out angular noise inconsistent with the scattering phase function.
3.  **Diffuse Path:** Governed by micro-facet BRDF statistical averaging ($r \gg 1$, incoherent reflection). The Lambertian baseline is expanded using a micro-facet normal distribution $D(\theta_h)$ and shadowing-masking function $G(\theta_i, \theta_o)$:
    <formula>
    F_{diff}(x,y) = F_{in}(x,y) \cdot \frac{F(\theta_i)D(\theta_h)G(\theta_i,\theta_o)}{4\cos\theta_i\cos\theta_o}
    </formula>

The final physically-enhanced feature representation is obtained through a soft routing mechanism weighted by the Medium Mask. To ensure differentiability, we compute the continuous mapping from $r(x,y)$ to routing weights $w_s, w_{scat}, w_d$ using a softmax activation over physically constrained thresholds:
<formula>
F_{out}(x,y) = w_s(r) F_{spec}(x,y) + w_{scat}(r) F_{scat}(x,y) + w_d(r) F_{diff}(x,y)
</formula>
This routing mechanism is fundamentally distinct from standard attention or dynamic convolution <citation>["ACE"]</citation>, as the weights are not purely data-driven but are strictly bounded by the physical ratio $r(x,y) = a(x,y)/\lambda$, guaranteeing that the feature computation path is physically consistent with the local light-matter interaction regime.

### 3.3 Depth Decoder

The Depth Decoder takes the physically-enhanced angular features $F_{out}(x,y)$ and constructs a cost volume to predict the dense depth map. We adapt a standard multi-scale cost volume construction <citation>["cost_volume_deep_learning"]</citation> by weighting the angular correlation with the Angular Direction Mask $V(x,y,\theta_i)$. For a given depth hypothesis $d$, the angular correlation cost $C(x,y,d)$ is computed by aggregating features across angular views, masked by $V(x,y,\theta_i)$ to suppress physically inconsistent angular deviations:
<formula>
C(x,y,d) = \sum_{\theta_i} V(x,y,\theta_i) \cdot \langle F_{out}(x,y), F_{out}(x+\Delta x(d,\theta_i), y+\Delta y(d,\theta_i)) \rangle
</formula>
where $\Delta x, \Delta y$ are the warping offsets derived from the depth hypothesis $d$ and angular coordinate $\theta_i$, and $\langle \cdot, \cdot \rangle$ denotes the dot product. By masking the correlation with $V(x,y,\theta_i)$, only phase-matched and physically plausible angular correspondences contribute to the cost volume. The cost volume is then processed by a 3D convolutional encoder-decoder network to regress the final dense depth map $D(x,y)$.

### 3.4 Differentiable Rendering Layer

To enforce forward physical consistency and bridge the gap between the predicted depth and the input light field, we introduce a Differentiable Rendering Layer. This layer reconstructs the sub-aperture images $\hat{I}_{\theta_i}$ from the predicted depth map $D(x,y)$ and the physically-enhanced features $F_{out}(x,y)$, constraining the network outputs to adhere to energy conservation principles derived from Maxwell's equations.

The rendering equation is formulated as a differentiable physical integration over the angular domain, utilizing the soft routing weights and the Angular Direction Mask:
<formula>
\hat{I}_{\theta_i}(x,y) = \sum_{k \in \{s, scat, d\}} w_k(r) \int_{\Omega} L_{in}(x,y,\theta_i) \cdot f_k(\theta_i, \theta_o) V(x,y,\theta_o) \cos\theta_o d\theta_o
</formula>
where $L_{in}$ is the incident radiance derived from the central view, and $f_k$ corresponds to the Fresnel reflectance, scattering phase function, or micro-facet BRDF applied in the respective routing path. The differentiability of this layer allows the network to be trained end-to-end using a photometric reconstruction loss:
<formula>
\mathcal{L}_{render} = \sum_{\theta_i} \left\| I_{\theta_i}(x,y) - \hat{I}_{\theta_i}(x,y) \right\|_1
</formula>
This loss ensures that the predicted depth map and the intermediate physical masks ($r(x,y)$ and $V(x,y,\theta_i)$) are not only geometrically optimal but also strictly conform to the underlying electromagnetic wave optics and energy conservation laws.