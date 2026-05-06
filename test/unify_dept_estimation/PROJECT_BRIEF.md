# PROJECT_BRIEF: Unified Dual-Mask Physical Model for Non-Lambertian Light Field Depth Estimation

## Core Objective
- Primary Goal: Implement and validate the proposed dual-mask (Medium Mask + Angular Direction Mask) physical model, which unifies Lambertian and non-Lambertian imaging under Maxwell's equations, to achieve robust light field depth estimation.
- Quantitative Target: Achieve validation Mean Absolute Error (val MAE) ≤ 0.03 on non-Lambertian test datasets, with physical consistency loss < 1e-4 to ensure the model strictly aligns with electromagnetic optical principles.
- Secondary Goal: Verify the model's generalization ability on challenging scenes including specular reflection, scattering, and real-world mine dust non-Lambertian environments.

## Project Core Background
This project is built on a physics-inspired computational imaging framework, which abstracts light-matter interaction governed by Maxwell's equations into two learnable, physically interpretable core masks:
1.  **Medium Mask**: A continuous-valued map `r(x,y) = a(x,y)/λ`, where `a(x,y)` is local medium roughness, `λ` is the optical wavelength. It quantifies the dominant light-matter interaction type at each spatial location:
    - `r ≪ 1 (a ≪ λ)`: Specular reflection/refraction (Fresnel-dominated smooth interface interaction)
    - `r ≈ 1 (a ≈ λ)`: Volume/surface scattering (Rayleigh/Mie scattering for wavelength-scale structures)
    - `r ≫ 1 (a ≫ λ)`: Diffuse Lambertian reflection (statistical average of micro-facet mirror reflections)
2.  **Angular Direction Mask**: A deflection vector field `V(x,y,θ_i)` that describes the statistical distribution of light wave vector changes under different interaction types, strictly following the phase matching condition in classical electromagnetics.

### Core Unification Logic
Ideal Lambertian scenes are a special case of the model (full spatial domain `r ≫ 1`, isotropic cosine deflection distribution), while non-Lambertian scenes are the weighted superposition of multiple interaction types from the dual-mask model. This framework solves the core pain point of photometric consistency failure in traditional MVS methods under non-Lambertian scenes.

## Code & Data Specification
### Code Requirements
- Agent will build the full PyTorch-based training, validation, and evaluation pipeline from scratch, strictly following the proposed dual-mask physical model.
- Mandatory modular code structure:
  - `./models/`: Dual-mask encoder, physical interaction module, depth decoder, and differentiable rendering layer
  - `./datasets/`: Dataloaders for all specified datasets with configurable view and patch settings
  - `./scripts/`: `train.py`, `eval.py`, and `inference.py` for full pipeline execution
  - `./configs/`: Hydra config files for each training stage with editable hyperparameters
- Model checkpoints will be saved to `./artifacts/checkpoints/{stage}/`
- Training logs (TensorBoard + CSV format) will be written to `./artifacts/logs/{stage}/`
- Evaluation metrics and visualization results will be saved to `./artifacts/eval/`

### Dataset Specification
- Dataset Paths & Categories:
  1.  Stage 1 (Physical Pre-training): External dataset `data/HCI4D/` (standard light field dataset, Lambertian-dominant, for physical model validation and pre-training)
  2.  Stage 2 (Physical Augmentation Fine-tuning): Hybrid data from HCI4D + synthetic non-Lambertian data generated via physics-based rendering
  3.  Stage 3 (Target Non-Lambertian Training): Local dataset `data/Non-lambertian_dataset_zhenglong/`
- Labeled Data (supervised training/validation): `Teddy`, `David 10/30/50/70/80%`
- Unlabeled Data (generalization inference test): `Apple 20/30/50/70/90%`, `Mine 0/10/30/50/70/80%`
- Critical Runtime Note: `data/HCI4D/` is not guaranteed to be available in the current environment; the pipeline must include complete fallback logic without manual intervention.

## Experiment Pipeline & Try Directions
### Stage 1: Physical Model Validation & Lambertian Pre-training
- First Run Command: `python scripts/train.py --config-name stage1_physical_pretrain`
- Core Target: Verify the physical correctness of the dual-mask model on standard Lambertian light field data, achieve val MAE ≤ 0.05
- Decision Tree:
  - If `val MAE > 0.07`:
    1. Validate the implementation of physical consistency loss (ensure Fresnel, scattering, and Lambertian deflection constraints are correctly coded)
    2. Tune base learning rate, add gradient clipping, and verify optimizer configuration
    3. Check data loading pipeline, light field view alignment, and depth label normalization
  - If `0.05 < val MAE ≤ 0.07`:
    1. Add cosine annealing learning rate scheduler with 5-epoch warmup
    2. Add basic light field data augmentation (random view cropping, brightness/contrast jitter)
    3. Extend training up to the maximum 20 epochs
  - If `val MAE ≤ 0.05`:
    1. Save the best-performing checkpoint to `./artifacts/checkpoints/stage1/best.pt`
    2. Proceed directly to Stage 2

### Stage 2: Physical Augmentation & Non-Lambertian Generalization Fine-tuning
- First Run Command: `python scripts/train.py --config-name stage2_physaug_finetune --resume_from ./artifacts/checkpoints/stage1/best.pt`
- Core Target: Fine-tune the model on hybrid non-Lambertian synthetic data, achieve val MAE ≤ 0.04
- Critical Fallback Logic: If `data/HCI4D/` is unavailable, skip Stage 1 and initialize Stage 2 with random weights, using only synthetic non-Lambertian data for physical validation
- Decision Tree:
  - If `val MAE > 0.06`:
    1. Re-verify the dual-mask decomposition module (ensure correct separation of specular, scattering, and diffuse components)
    2. Adjust the weight of the physical consistency loss term in the total loss function
    3. Validate the correctness of synthetic non-Lambertian data rendering and label generation
  - If `0.04 < val MAE ≤ 0.06`:
    1. Resume training from the best checkpoint of the current stage
    2. Fine-tune loss weights for reprojection error, epipolar constraint, and medium mask physical regularization
    3. Extend training up to the maximum 30 epochs
  - If `val MAE ≤ 0.04`:
    1. Save the best-performing checkpoint to `./artifacts/checkpoints/stage2/best.pt`
    2. Proceed directly to Stage 3

### Stage 3: Target Non-Lambertian Dataset Training & Final Optimization
- First Run Command: `python scripts/train.py --config-name stage3_nonlambertian --resume_from ./artifacts/checkpoints/stage2/best.pt`
- Fallback Run Command (if Stage 1/2 are skipped): `python scripts/train.py --config-name stage3_nonlambertian`
- Core Target: Achieve final val MAE ≤ 0.03 on the target non-Lambertian dataset
- Decision Tree:
  - If `val MAE > 0.07`:
    1. If the HCI4D dataset is available, re-run the full Stage 1 → Stage 2 → Stage 3 pipeline with pre-trained weights
    2. If HCI4D is unavailable, check data loading paths, view cropping settings, and depth label alignment of the target dataset
    3. Re-validate the implementation of the dual-mask forward differentiable rendering model
  - If `0.03 < val MAE ≤ 0.07`:
    1. Resume training from `./artifacts/checkpoints/stage3/best.pt`
    2. Fine-tune loss weights for reprojection loss, epipolar constraint, and medium mask regularization
    3. Add mixup/cutout data augmentation for non-Lambertian dominant regions
    4. Extend training up to the maximum 40 epochs
  - If `val MAE ≤ 0.03`:
    1. Run full evaluation: `python scripts/eval.py ckpt=./artifacts/checkpoints/stage3/best.pt`
    2. Save final quantitative metrics to `./artifacts/eval/metrics.json`
    3. Save depth predictions, medium mask, and angular direction mask visualization results to `./artifacts/eval/predictions/`
    4. Run generalization inference on unlabeled Mine/Apple scenes, save all results to the evaluation directory

## Hard Constraints
- GPU: Auto-detect available CUDA device, single-device training by default (no distributed training unless explicitly enabled)
- Max Training Epochs: Hard limit of 20 epochs for Stage 1, 30 epochs for Stage 2, 40 epochs for Stage 3
