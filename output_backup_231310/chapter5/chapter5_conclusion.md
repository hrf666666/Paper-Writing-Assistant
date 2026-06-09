# 5. Conclusion

# 5. Conclusion

This paper presented the Unified Dual-Mask Physical Model, a comprehensive framework designed to address the limitations of Epipolar Plane Image (EPI) assumptions in light field depth estimation, particularly for Non-Lambertian surfaces and complex textures. By integrating physical reflectance properties with geometric feature analysis, the proposed approach systematically mitigates the slope ambiguity and structural degradation typically encountered in mixed and urban environments. 

The specific contributions and findings are summarized as follows:
1. **Three-Layer Angular Signal Decomposition and Geometric Material Perception**: We developed a material perception mechanism that extracts geometric features to replace traditional frequency-domain representations. This design overcomes the resolution limits of discrete angular sampling and provides a robust routing basis, effectively identifying the physical causes of EPI assumption failures on Non-Lambertian surfaces.
2. **Dual-Mask Routing Mechanism for EPI Structure Preservation**: We introduced a dual-mask architecture that dynamically routes and processes EPI features. This mechanism reduces slope blurring caused by complex textures and structural disruptions induced by specular reflections, achieving an overall Mean Absolute Error (MAE) of 0.133 and a Mixed (Urban) scene MAE of 0.081.
3. **Domain-Balanced Sampling and Physical Boundary Validation**: We formulated a domain-balanced training strategy that maximizes generalization under severe data scarcity, specifically addressing the constraint of only four Non-Lambertian training scenes. Through 132 experiments across 16 research directions, we established the terminal physical boundaries of EPI-based unified models, proving that architectural modifications cannot overcome the dual barriers of physical assumption breakdown and extreme data deficiency in Non-Lambertian and complex-texture Lambertian scenarios.

The established physical boundaries and the proposed dual-mask routing paradigm provide a definitive theoretical and empirical reference for computational photography. These findings indicate that advancing light field 3D reconstruction necessitates a paradigm shift from pure EPI reliance toward hybrid representations capable of modeling complex light transport.
