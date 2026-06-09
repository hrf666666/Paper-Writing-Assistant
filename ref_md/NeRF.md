---
title: "NeRF"
authors: "Ben Mildenhall, Pratul P. Srinivasan, Matthew Tancik, Jonathan T. Barron, Ravi Ramamoorthi, Ren Ng"
journal: "Communications of the ACM"
doi: "10.1145/3503250"
published: "2022-1"
source: "crossref_meta"
has_fulltext: false
content_kind: "abstract_only"
has_abstract: true
token_estimate: 268
---

# NeRF

**Abstract.** We present a method that achieves state-of-the-art results for synthesizing novel views of complex scenes by optimizing an underlying continuous volumetric scene function using a sparse set of input views. Our algorithm represents a scene using a fully connected (nonconvolutional) deep network, whose input is a single continuous 5D coordinate (spatial location ( x , y , z ) and viewing direction ( θ, ϕ )) and whose output is the volume density and view-dependent emitted radiance at that spatial location. We synthesize views by querying 5D coordinates along camera rays and use classic volume rendering techniques to project the output colors and densities into an image. Because volume rendering is naturally differentiable, the only input required to optimize our representation is a set of images with known camera poses. We describe how to effectively optimize neural radiance fields to render photorealistic novel views of scenes with complicated geometry and appearance, and demonstrate results that outperform prior work on neural rendering and view synthesis.

## References (25 total, showing 25)

- 10.1145/383259.383309
- Chang , A.X. , Fhnkhouser , T. , Guibas , L. , Hanrahan , P. , Huang , Q. , Li , Z. , Savarese , S. , Savva , M. , Song , S. , Su , H. , ShapeNet: An information-rich 3D model repository. arXiv:1512.03012 ( 2015 ). Chang, A.X., Fhnkhouser, T., Guibas, L., Hanrahan, P., Huang, Q., Li, Z., Savarese, S., Savva, M., Song, S., Su, H., et al. ShapeNet: An information-rich 3D model repository. arXiv:1512.03012 (2015).
- 10.1145/237170.237269
- 10.1145/237170.237191
- Kajiya J.T. Herzen B.P.V. Ray tracing volume densities. Comput. Graph. (SIGGRAPH) (1984). Kajiya J.T. Herzen B.P.V. Ray tracing volume densities. Comput. Graph. (SIGGRAPH) (1984).
- Kingma , D.P. , Ba , J. Adam: A method for stochastic optimization . In ICLR ( 2015 ). Kingma, D.P., Ba, J. Adam: A method for stochastic optimization. In ICLR (2015).
- Li , T.-M. , Aittala , M. , Durand , F. , Lehtinen , J. Differentiable monte carlo ray tracing through edge sampling. ACM Trans. Graph. (SIGGRAPH Asia) ( 2018 ). Li, T.-M., Aittala, M., Durand, F., Lehtinen, J. Differentiable monte carlo ray tracing through edge sampling. ACM Trans. Graph. (SIGGRAPH Asia) (2018).
- Lombardi , S. , Simon , T. , Saragih , J. , Schwartz , G. , Lehrmann , A. , Sheikh , Y. Neural volumes: Learning dynamic renderable volumes from images. ACM Trans. Graph. (SIGGRAPH) ( 2019 ). Lombardi, S., Simon, T., Saragih, J., Schwartz, G., Lehrmann, A., Sheikh, Y. Neural volumes: Learning dynamic renderable volumes from images. ACM Trans. Graph. (SIGGRAPH) (2019).
- 10.1007/978-3-319-10584-0_11
- Max N. Optical models for direct volume rendering. IEEE Trans. Visual. Comput. Graph. (1995). Max N. Optical models for direct volume rendering. IEEE Trans. Visual. Comput. Graph. (1995).
- 10.1109/CVPR.2019.00459
- Mildenhall , B. , Srinivasan , P.P. , Ortiz-Cayon , R. , Kalantari , N.K. , Ramamoorthi , R. , Ng , R. , Kar , A. Local light field fusion: Practical view synthesis with prescriptive sampling guidelines. ACM Trans. Graph. (SIGGRAPH) ( 2019 ). Mildenhall, B., Srinivasan, P.P., Ortiz-Cayon, R., Kalantari, N.K., Ramamoorthi, R., Ng, R., Kar, A. Local light field fusion: Practical view synthesis with prescriptive sampling guidelines. ACM Trans. Graph. (SIGGRAPH) (2019).
- 10.1007/978-3-030-58452-8_24
- Niemeyer , M. , Mescheder , L. , Oechsle , M. , Geiger , A. Differentiable volumetric rendering: Learning implicit 3D representations without 3D supervision . In CVPR ( 2019 ). Niemeyer, M., Mescheder, L., Oechsle, M., Geiger, A. Differentiable volumetric rendering: Learning implicit 3D representations without 3D supervision. In CVPR (2019).
- 10.1109/CVPR.2019.00025
- Porter , T. , Duff , T. Compositing digital images. Comput. Graph. (SIGGRAPH) ( 1984 ). Porter, T., Duff, T. Compositing digital images. Comput. Graph. (SIGGRAPH) (1984).
- Rahaman , N. , Baratin , A. , Arpit , D. , Dräxler , F. , Lin , M. , Hamprecht , F.A. , Bengio , Y. , Courville , A.C. On the spectral bias of neural networks . In ICML ( 2018 ). Rahaman, N., Baratin, A., Arpit, D., Dräxler, F., Lin, M., Hamprecht, F.A., Bengio, Y., Courville, A.C. On the spectral bias of neural networks. In ICML (2018).
- 10.1109/CVPR.2016.445
- Seitz , S.M. , Dyer , C.R. Photorealistic scene reconstruction by voxel coloring. Int. J. Comput. Vision ( 1999 ). Seitz, S.M., Dyer, C.R. Photorealistic scene reconstruction by voxel coloring. Int. J. Comput. Vision (1999).
- 10.1109/CVPR.2019.00254
- Sitzmann , V. , Zollhoefer , M. , Wetzstein , G. Scene representation networks: Continuous 3D-structure-aware neural scene representations . In NeurIPS ( 2019 ). Sitzmann, V., Zollhoefer, M., Wetzstein, G. Scene representation networks: Continuous 3D-structure-aware neural scene representations. In NeurIPS (2019).
- Tancik , M. , Srinivasan , P.P. , Mildenhall , B. , Fridovich-Keil , S. , Raghavan , N. , Singhal , U. , Ramamoorthi , R. , Barron , J.T. , Ng , R. Fourier features let networks learn high frequency functions in low dimensional domains . In NeurIPS ( 2020 ). Tancik, M., Srinivasan, P.P., Mildenhall, B., Fridovich-Keil, S., Raghavan, N., Singhal, U., Ramamoorthi, R., Barron, J.T., Ng, R. Fourier features let networks learn high frequency functions in low dimensional domains. In NeurIPS (2020).
- 10.1145/344779.344925
- 10.1109/CVPR.2018.00068
- Zhou , T. , Tucker , R. , Flynn , J. , Fyffe , G. , Snavely , N. Stereo magnification: Learning view synthesis using multiplane images. ACM Trans. Graph. (SIGGRAPH) ( 2018 ). Zhou, T., Tucker, R., Flynn, J., Fyffe, G., Snavely, N. Stereo magnification: Learning view synthesis using multiplane images. ACM Trans. Graph. (SIGGRAPH) (2018).
