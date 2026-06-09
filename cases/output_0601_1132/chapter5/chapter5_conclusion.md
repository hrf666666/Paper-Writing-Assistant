# 5. Conclusion

# 5. Conclusion

In this paper, we have proposed a unified dual-mask physical model to address the persistent challenge of depth estimation for non-Lambertian surfaces in light field imaging, where the fundamental Epipolar Plane Image (EPI) linearity assumption is severely violated. By explicitly modeling the physical degradation of angular signals, our framework decouples material-specific reflections from geometric structures, enabling robust depth inference in complex mixed-reflectance environments. 

The main contributions of this work are summarized as follows:
* **Geometry-based Material Classification via Angular Signal Decomposition:** We introduced a three-layer decomposition mechanism that overcomes frequency aliasing caused by discrete low-resolution angular sampling, providing a robust and efficient material identification scheme that lays the foundation for dual-branch depth estimation.
* **Unified Dual-Mask Depth Estimation Architecture:** We developed a dual-branch framework that effectively mitigates the depth collapse typically encountered by single-EPI methods when facing specular or translucent surfaces due to physical assumption failures.
* **Mask Routing for Mixed-Scene Generalization:** By integrating a dynamic mask routing mechanism within a unified architecture, the proposed model achieves high-precision depth estimation across both mixed and holistic scenes, significantly improving the generalization capability and practical applicability of the system.

Although the proposed unified architecture achieves robust performance in mixed scenarios, it remains fundamentally constrained by the extreme scarcity of non-Lambertian training data and the inherent blurring of EPI slopes in complex textured regions. To transcend these intrinsic bottlenecks of epipolar geometry, future research will shift towards non-EPI paradigms, such as Neural Radiance Fields (NeRF), leveraging substantially expanded multi-reflectance datasets to achieve comprehensive depth estimation across all material domains.
