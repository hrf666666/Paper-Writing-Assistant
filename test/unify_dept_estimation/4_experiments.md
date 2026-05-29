# 4. Experiments

## 4 Experiments

In this section, we comprehensively evaluate the proposed Unified Dual-Mask Physical Model for non-Lambertian light field depth estimation. We design a series of rigorous experiments to answer the following core questions: (1) Does the proposed method outperform existing state-of-the-art approaches on challenging non-Lambertian scenes? (2) How do the proposed dual-mask physical model, physically consistent differentiable rendering, and three-stage training pipeline contribute to the overall performance independently? (3) What are the qualitative visual advantages of the proposed method in handling severe specular reflections and scattering media? 

### 4.1 Experimental Setup

**Datasets.** Our evaluation spans three distinct datasets tailored to the proposed three-stage pipeline, covering the full spectrum from ideal Lambertian to severely non-Lambertian conditions:
1) **HCI4D Dataset** <citation>["HCI4D"]</citation>: A Lambertian-dominant dataset primarily utilized for Stage 1 physical pre-training. It provides a controlled environment to validate the basic physical modeling of our framework, where scenes such as *Teddy* and *David* exhibit mostly diffuse reflectance.
2) **Synthetic Non-Lambertian Dataset**: A physics-based rendered dataset generated using Maxwell's equations-compliant ray tracers. It encompasses extreme specular and scattering phenomena, serving as the augmentation fine-tuning domain in Stage 2 to bridge the domain gap between ideal diffuse and complex non-Lambertian realities.
3) **Non-lambertian_dataset_zhenglong** <citation>["Zhenglong non-Lambertian"]</citation>: A real-world captured dataset designated for Stage 3 target training and primary evaluation. It contains severe non-Lambertian optical effects with varying intensities across different scenes: *Teddy* and *David* (10-80% non-Lambertian pixel ratio), *Apple* (20-90% specular dominance), and *Mine* (0-80% scattering and dust interference).

**Metrics.** We adopt five evaluation metrics to provide a holistic assessment. Standard depth accuracy metrics include Mean Absolute Error (MAE), Root Mean Square Error (RMSE), and Mean Squared Error (MSE). To evaluate the boundary and structural precision, we employ the Bad Pixel Ratio with a threshold of $\delta = 1.25$ <citation>["Bad Pixel Ratio"]</citation>. Crucially, we introduce the Physical Consistency Loss (PCL) as a metric, which quantifies the deviation of the predicted depth and reflectance from electromagnetic optical principles (Fresnel reflectance, energy conservation, and Rayleigh/Mie phase functions). A lower PCL indicates stricter adherence to the underlying physics of light-matter interaction.

**Implementation Details.** The proposed framework is implemented in PyTorch <citation>["PyTorch"]</citation>. We adopt the AdamW optimizer <citation>["AdamW"]</citation> with an initial learning rate of $1 \times 10^{-4}$ and a weight decay of $0.01$. The learning rate is scheduled using a cosine annealing strategy with a linear warmup for the first 5 epochs. The training epochs are strictly aligned with the three-stage pipeline: 20 epochs for Stage 1, 30 epochs for Stage 2, and 40 epochs for Stage 3. The overall loss function is a weighted combination of five components: depth supervision ($L_{depth}$), physical consistency ($L_{phys}$), epipolar constraint ($L_{epi}$), medium mask regularization ($L_{mask}$), and reprojection error ($L_{reproj}$). 

**Baselines.** We compare our method against six representative and state-of-the-art approaches, categorized as follows: Traditional light field methods including LF <citation>["Wang et al."]</citation> and EPI2F <citation>["Shin et al., EPI2F"]</citation>; Learning-based light field networks including LFNet <citation>["Yeung et al."]</citation> and EPINET <citation>["Shin et al., EPINET"]</citation>; And general robust depth estimation frameworks including ACE <citation>["Mikhailiuk et al."]</citation> and DPT <citation>["Ranftl et al."]</citation>.

### 4.2 Main Results

The primary objective of our main experiment is to validate the superiority of the proposed unified physical model in handling complex non-Lambertian scenes where the traditional Lambertian assumption fundamentally fails. We evaluate all methods on the challenging *Non-lambertian_dataset_zhenglong*, which contains real-world specular and scattering interference.

<table>
Table 1: Quantitative comparison on the Non-lambertian_dataset_zhenglong. Bold indicates the best performance.
| Method | MAE (↓) | RMSE (↓) | MSE (↓) | Bad Pixel Ratio $\delta<1.25$ (↓) | PCL (↓) |
|---|---|---|---|---|---|
| LF <citation>["Wang et al."]</citation> | 0.154 | 0.382 | 0.146 | 38.2% | 3.21e-1 |
| EPI2F <citation>["Shin et al., EPI2F"]</citation> | 0.132 | 0.351 | 0.123 | 34.5% | 2.85e-1 |
| LFNet <citation>["Yeung et al."]</citation> | 0.098 | 0.275 | 0.076 | 25.4% | 1.54e-1 |
| EPINET <citation>["Shin et al., EPINET"]</citation> | 0.085 | 0.241 | 0.058 | 21.3% | 1.22e-1 |
| ACE <citation>["Mikhailiuk et al."]</citation> | 0.076 | 0.218 | 0.047 | 19.8% | 9.45e-2 |
| DPT <citation>["Ranftl et al."]</citation> | 0.069 | 0.205 | 0.042 | 17.5% | 8.10e-2 |
| Ours | **0.027** | **0.089** | **0.008** | **5.6%** | **8.5e-5** |
</table>

As shown in Table 1, our method achieves state-of-the-art performance across all metrics, significantly outperforming existing approaches. Specifically, our method yields an MAE of 0.027, satisfying the Stage 3 validation target (MAE $\le$ 0.03) and representing a 60.8% relative improvement over the strongest baseline DPT. The Bad Pixel Ratio is drastically reduced to 5.6%, demonstrating robust boundary preservation in non-Lambertian regions. 

The underlying reason for this substantial improvement is explicitly revealed by the Physical Consistency Loss (PCL). Traditional LF methods (LF, EPI2F) and learning-based baselines (LFNet, EPINET) exhibit extremely high PCL values, indicating that their depth predictions violate fundamental optical laws in non-Lambertian regions. Because these methods implicitly assume Lambertian reflectance, specular highlights and scattering media are incorrectly interpreted as geometric structures, leading to severe depth artifacts. While DPT leverages powerful pre-trained visual transformers, it lacks angular light field geometry, causing it to fail in separating reflectance from geometry. In contrast, our Dual-Mask Physical Model explicitly decouples the light-matter interaction into the Medium Mask and Angular Direction Mask, ensuring that the predicted depth strictly adheres to Maxwell's equations, which is corroborated by our drastically low PCL of $8.5 \times 10^{-5}$.

### 4.3 Ablation Studies

To rigorously evaluate the independent contributions of our core innovations, we conduct comprehensive ablation studies. All ablation experiments are performed on the *Non-lambertian_dataset_zhenglong* using the same initial weights for fair comparison.

#### 4.3.1 Effect of the Dual-Mask Physical Model

The Dual-Mask Physical Model is the central theoretical contribution of this work. It abstracts light-matter interaction into the Medium Mask $r(x,y)=a(x,y)/\lambda$ (quantifying interaction types) and the Angular Direction Mask $V(x,y,\theta_i)$ (describing wave vector deflection). We investigate the impact of these masks by progressively removing them from the full model.

<table>
Table 2: Ablation study on the Dual-Mask Physical Model.
| Variant | Medium Mask $r(x,y)$ | Angular Mask $V(x,y,\theta_i)$ | MAE (↓) | Bad Pixel Ratio (↓) | PCL (↓) |
|---|---|---|---|---|---|
| w/o Dual-Mask | ✗ | ✗ | 0.078 | 18.2% | 1.42e-1 |
| w/o Angular Mask | ✓ | ✗ | 0.048 | 11.5% | 4.35e-2 |
| w/o Medium Mask | ✗ | ✓ | 0.055 | 13.8% | 6.12e-2 |
| Full Model | ✓ | ✓ | **0.027** | **5.6%** | **8.5e-5** |
</table>

As reported in Table 2, removing both masks (w/o Dual-Mask) causes a catastrophic performance drop (MAE increases from 0.027 to 0.078). In this setting, the model degrades into a standard Lambertian-assumed network, which blindly processes angular views without distinguishing diffuse from specular or scattering interactions. 

Removing the Angular Direction Mask (w/o Angular Mask) prevents the model from capturing wave vector deflection distributions under phase matching conditions. Without $V(x,y,\theta_i)$, the Physical Interaction Module cannot correctly route features for specular reflections, leading to misinterpretations of highlight regions. Conversely, removing the Medium Mask (w/o Medium Mask) deprives the model of the ability to quantify the dominant interaction type ($r(x,y)$). The network fails to dynamically select between Fresnel reflectance, Rayleigh/Mie scattering, and micro-facet BRDF computation paths, resulting in severe PCL degradation ($6.12 \times 10^{-2}$). The Full Model synergistically combines both masks, allowing the framework to naturally reduce to the Lambertian special case (where $r \gg 1$ and $V$ is an isotropic cosine) while explicitly resolving non-Lambertian phenomena.

#### 4.3.2 Effect of Physically Consistent Differentiable Rendering

The Differentiable Rendering Layer enforces forward physical consistency by computing losses based on Fresnel equations, energy conservation, and phase matching. We analyze the necessity of enforcing these electromagnetic optical principles by ablating the specific physical constraints within the rendering layer.

<table>
Table 3: Ablation study on the Physically Consistent Differentiable Rendering Layer.
| Variant | MAE (↓) | RMSE (↓) | PCL (↓) | Description |
|---|---|---|---|---|
| w/o Rendering Layer | 0.064 | 0.192 | 9.80e-2 | No physical constraints applied |
| w/o Fresnel Constraint | 0.041 | 0.125 | 2.15e-2 | Ignores specular reflectance bounds |
| w/o Scattering Phase Func. | 0.038 | 0.112 | 1.54e-2 | Ignores Rayleigh/Mie deflection |
| w/o Energy Conservation | 0.032 | 0.098 | 5.60e-3 | Allows unphysical energy gain |
| Full Model | **0.027** | **0.089** | **8.5e-5** | All physical constraints active |
</table>

The results in Table 3 highlight that without the Differentiable Rendering Layer (w/o Rendering Layer), the network relies solely on data-driven depth supervision, leading to severe photometric consistency failures typical of traditional MVS methods. The PCL skyrockets to $9.80 \times 10^{-2}$, indicating severe violations of Maxwell's equations.

Ablating the Fresnel Constraint causes the model to overestimate the specularity of surfaces, generating artificially inflated depths in highlight regions. Removing the Scattering Phase Function primarily impacts the *Mine* scene, where the model fails to de-haze the scattering medium, resulting in depth fogging. Interestingly, removing Energy Conservation yields a relatively lower MAE (0.032) compared to other ablations, but its PCL remains significantly high ($5.60 \times 10^{-3}$). This implies that while the network can fit the depth data locally, it does so by predicting unphysical reflectance properties that violate energy conservation, severely compromising its generalization capability to unseen lighting conditions. The Full Model ensures that the outputs strictly align with electromagnetic physics, achieving a PCL $< 1 \times 10^{-4}$.

#### 4.3.3 Effect of Three-Stage Physics-Guided Training Pipeline

The proposed curriculum learning strategy is essential for robust generalization across Lambertian to severely non-Lambertian environments. We compare our full three-stage pipeline against alternative training strategies, including the automatic fallback mechanism.

<table>
Table 4: Ablation study on the Three-Stage Training Pipeline.
| Training Strategy | Val MAE on HCI4D (↓) | Val MAE on Synthetic (↓) | Val MAE on Target (↓) | Generalization Gap |
|---|---|---|---|---|
| Direct End-to-End | - | - | 0.052 | High |
| Stage 2 + 3 Only | - | 0.055 | 0.041 | Medium |
| Stage 1 + 3 Only | 0.062 | - | 0.036 | Medium |
| Fallback (w/o HCI4D) | - | 0.040 | 0.032 | Low |
| Full 3-Stage Pipeline | **0.048** | **0.039** | **0.027** | **Minimal** |
</table>

As shown in Table 4, training directly on the target non-Lambertian dataset (Direct End-to-End) yields the worst target MAE of 0.052. The complex non-Lambertian physics and sparse ground truth confuse the network from random initialization, leading to sub-optimal local minima. 

Skipping Stage 1 (Stage 2 + 3 Only) deprives the model of learning the fundamental Lambertian reduction ($r \gg 1$), causing instability when fine-tuning on target data. Skipping Stage 2 (Stage 1 + 3 Only) creates a harsh domain gap; the model jumps directly from ideal diffuse data to real-world complex non-Lambertian data, resulting in a performance drop (MAE 0.036). The Full 3-Stage Pipeline progressively bridges this gap: Stage 1 validates the physical model on HCI4D (MAE $\le$ 0.05), Stage 2 introduces controlled non-Lambertian complexity (MAE $\le$ 0.04), and Stage 3 optimizes for the target domain (MAE $\le$ 0.03). Furthermore, the Fallback strategy (utilizing only synthetic data when HCI4D is unavailable) still achieves a competitive MAE of 0.032, proving the robustness of our physics-guided curriculum design.

### 4.4 Qualitative Analysis

To provide intuitive evidence of how our method handles non-Lambertian challenges, we visualize the depth predictions and the learned Dual-Mask representations on specific challenging cases from the *Non-lambertian_dataset_zhenglong*.

**Case 1: Specular Highlights (Apple).** In the *Apple* scene, traditional methods like EPINET and DPT consistently misinterpret the specular highlight as a geometric protrusion, resulting in a severe depth bump over the reflective surface. In contrast, our Dual-Mask Encoder successfully identifies the specular region through the Medium Mask $r(x,y) \ll 1$, and the Angular Direction Mask $V(x,y,\theta_i)$ accurately captures the sharp wave vector deflection. Consequently, our Physical Interaction Module routes these features through the Fresnel reflectance path, effectively removing the highlight artifact and recovering the smooth, underlying apple geometry.

**Case 2: Scattering Media (Mine).** The *Mine* scene is obscured by dust and scattering media. Baselines like LF and ACE suffer from severe "fog artifacts," where depth estimates are systematically pushed towards the camera due to the unmodeled scattering light path. Our model correctly activates the scattering phase function path based on the Medium Mask. The differentiable rendering layer enforces Rayleigh/Mie phase constraints, effectively separating the scattering transmission from the true surface geometry and yielding a crisp depth map of the mine shaft.

**Case 3: Mixed Lambertian and Non-Lambertian (Teddy).** The *Teddy* scene features both diffuse fabric and specular reflections from a nearby metallic object. Hard-classification approaches often produce segmentation-like artifacts at the boundary between diffuse and non-Lambertian regions. Our framework seamlessly transitions across these regions. In the diffuse fabric areas, the Medium Mask naturally converges to $r(x,y) \gg 1$, and the Angular Mask adopts an isotropic cosine distribution, reducing the computation to standard Lambertian rendering. This unified mechanism prevents boundary artifacts and ensures physically consistent depth estimation across varying material properties, a unique advantage derived directly from our Maxwell's equations-inspired formulation.