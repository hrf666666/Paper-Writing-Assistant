# 5. Conclusion

# 5. Conclusion

In this paper, we propose a unified dual-mask physical model for light field depth estimation to address the severe geometric degradation caused by non-Lambertian reflectance and complex textures. Moving beyond the conventional Epipolar Plane Image (EPI) linearity assumption, our framework explicitly models the physical degradation of angular signals to recover accurate depth maps in heterogeneous environments. By integrating reflectance priors with geometric constraints, the proposed method effectively resolves the depth ambiguities inherent in multi-view imaging systems deployed in unconstrained urban and indoor scenes.

The specific contributions and findings of this work are summarized as follows:
* **Geometry-based three-layer angular signal decomposition and non-Lambertian detection:** We decouple mixed angular signals into diffuse, specular, and scattering components. This mechanism accurately identifies non-Lambertian regions by analyzing geometric deviations, preventing the erroneous depth assignments typically caused by dynamic highlight shifts and volumetric scattering that violate standard EPI assumptions.
* **Unified dual-mask physical model:** We construct a dual-mask architecture that processes Lambertian and non-Lambertian regions simultaneously. By embedding physical reflectance constraints into the mask generation process, the model mitigates the slope ambiguity inherent in traditional EPI methods, particularly in complex textured scenes where photo-consistency is compromised.
* **Multi-domain balanced training strategy:** We introduce an optimization scheme designed to counteract the extreme data scarcity in non-Lambertian scenarios. This strategy stabilizes gradient updates across heterogeneous material domains, achieving an overall MAE of 0.133 and a Mixed (Urban) MAE of 0.081, validating the system's robustness in diverse real-world environments.

The established physical modeling paradigm provides a solid foundation for dense geometry recovery in scenes with heterogeneous materials. Extending these reflectance-aware mechanisms to dynamic light field video systems will further advance real-time 3D scene understanding and immersive rendering applications.
