# Writing Rationale Matrix

| Design Decision | Motivation | SOTA Gap | Scenario | Evidence | Section | Priority |
|---|---|---|---|---|---|---|
| 采用三层角信号分解物理模型 I(u,v) = DC + a·u + b·v +  | 非朗伯体材质（如高光、散射）会破坏传统EPI斜率约束，导致基于朗伯体假设的深度估计在复杂表面失效 | 摒弃了在9x9低角度分辨率光场下失效的2D-DFT频域分析方法，转为时域几何显式物理分解，避免频域混 | 包含复杂混合材质（朗伯体与非朗伯体共存）的真实世界城市场景（如UrbanLF-S | 理论验证引用Wang 2017角锥约束，证明残差项ε有效捕获非朗伯体反射特性，支 | Methodology (Physical Model) | must |
| 提取角梯度(angular gradient)等5个核心几何特征，并使用随机森林 | 离散低分辨率光场无法提供足够的频域信息，需要鲁棒的几何特征来精准区分朗伯体和非朗伯体像素 | 相比依赖CNN隐式学习材质特征的方法，基于物理先验的几何特征结合RF分类器具有更强的可解释性和小样本 | 非朗伯体数据极度稀缺的场景（如Non-Lambertian Dataset仅有4 | Phase 1实验中RF分类器准确率达89.6%，AUC达0.962；角梯度特征 | Methodology (Non-Lambertian Detection) | must |
| 构建GeometricDualMask双分支架构，利用双掩码对Lambertia | 单一网络在处理异质材质时容易发生特征混淆，导致非朗伯体区域的深度预测出现严重伪影和结构坍塌 | 相比于单分支全局回归网络（如基础EPINet），双分支机制在统一模型内隔离了不同反射特性的深度估计难 | 包含大面积高光和复杂纹理的Mixed (Urban)场景 | GeometricDualMask模型的mask gap降至0.041（优于0. | Methodology (Network Architecture) | must |
| 实施领域平衡采样(Domain-balanced sampling)与Weigh | 多源光场数据集（如HCInew和UrbanLF-Syn）分布严重不均，且非朗伯体数据稀缺，导致模型梯 | 克服了传统随机采样在长尾分布数据集上导致特定领域（如非朗伯体）梯度被淹没的问题，无需收集额外数据 | 跨域泛化评估，特别是在训练集与测试集领域分布不一致的设定下 | 132次实验记录证实该策略在多领域下保持了稳定的训练收敛，Overall MAE | Experiments (Training Strategy) | should |
| 采用平衡投影(Balanced Projection)和掩码加权融合(Mask- | 双分支独立预测后直接拼接会在朗伯体与非朗伯体掩码边界处产生深度不连续和接缝伪影 | 相比简单的掩码硬切换（Hard-switching）或通道拼接（Concatenation），加权融 | 朗伯体与非朗伯体交界的高频边缘区域（如金属物体与背景交界处） | 最终模型Lambertian MAE < 0.16，证明融合机制未损害主干朗伯体 | Methodology (Feature Fusion) | should |
| 采用4方向EPI输入(EPINet4Dir V3)作为基础特征提取器，结合连续深 | 9x9全角度输入会导致极高的计算冗余和显存消耗，且相邻视角间存在高度信息冗余，阻碍高分辨率处理 | 相比于9x9全视角输入或单方向EPI，4方向EPI在保留充足视差几何信息的同时，大幅降低了计算复杂度 | 高分辨率（512x512）光场图像的深度估计，对推理速度和显存有严格要求的场景 | 在HCInew（81视角）和UrbanLF-Syn数据集上实现了精度与效率的最佳 | Methodology (Feature Extraction) | nice |