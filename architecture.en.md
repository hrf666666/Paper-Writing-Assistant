# Paper Writing Assistant — Architecture Design v17.0

> **[中文](architecture.md)** | English | Version: v17.0

This document describes the **current architecture of v17.0**. Version history is in Appendix A.

---

## 0. Layered Governance Architecture (Core)

To fix "review without revise, revise without verify, repeated review without arbitration" exposed in real PDF runs, v16.3 governance batches + v17.0 G1/G4 built a government-metaphor six-layer architecture. **The reform fixes 12 breakpoints in the review-revise-verify flow, not adds features.**

### 0.1 Six Layers

| Layer | Role | Module | Boundary |
|-------|------|--------|----------|
| **L1** | Provincial | `chapter_agent.py` ChapterAgent | One chapter: generate→review→revise→audit cohesion; no cross-chapter |
| **L2** | Ministry (vertical) | `vertical_checkers.py` 5 Checkers | Review only: emit Finding to FindingBus; one specialty each (bib/formula/table/figure/language) |
| **L3** | Central (full-text) | `output_evaluator.py` GlobalReviewer | Full-text arbitration: chapter quality≥80 but full L3<70 → full-text wins |
| **L4a** | Executor | `fix_executor.py` FixExecutor | Revise only: route fixes by Finding, deterministic first |
| **L4b** | Inspector | `verifier.py` ContentVerifier | Verify only: re-check after fix, resolve only on pass |
| **L5** | Decision hub | `loop.py` + `quality_gate.py` | Dispatch + independent regression guard after revise |

**Principles**: (1) review-revise-verify separation, (2) Finding as sole carrier, (3) one-way decision chain, (4) provincial autonomy + central arbitration.

### 0.2 12 Breakpoints (all fixed, code-verified)

| BP | Definition | Fix Layer | Status |
|----|-----------|-----------|--------|
| B1 broken-link | phase6_5 findings recorded but never consumed | L1 ChapterAgent → FindingBus | ✅ |
| B2 ghost-fix | L3 revise regenerates tex but not PDF | L5 recompile + re-run Checker | ✅ |
| B3 self-review | quality_gate reviews and verifies same fn | L5 independent regression guard | ✅ |
| B4 no-recheck | overwrite after revise, no re-review | L4a resolve + L4b Verifier recheck | ✅ |
| B5 figure-no-loop | figure_review reports but no re-render | L2 FigureInspector + L4a | ✅ |
| B6 formula-gap | formula 0 review 0 fix 0 verify | L2 FormulaChecker + L4a | ✅ |
| B7 table-content | table structure-only check | L2 TableChecker | ✅ |
| B8 no-chapter-agent | 5 chapters same undifferentiated flow | L1 ChapterAgent per-chapter | ✅ |
| C1 dup-review | auditor & quality_gate both review cites | L1 ChapterAgent audit cohesion | ✅ |
| C2 dup-review | auditor runs twice in 5.6/6.5 | L1 cohesion + phase6_5 lightweight | ✅ |
| C3 no-arbitration | G4 structure vs L3 semantic conflict | L3 GlobalReviewer arbitration | ✅ |
| C4 no-resolve | clear by source, critical not downgraded | FindingBus.resolve(id) by ID | ✅ |

### 0.3 v17.0 G4: FactBase Owner Three-Way

Old `_classify_owner` (binary: non-baseline=ours) collapsed third-category numbers (cross-validation / physical-feature ratios / diagnostic classification) into ours, polluting `_compute_comparison`. Fixed to three-way: **baseline / auxiliary / ours**. Auxiliary excluded from pairing but kept in metrics for lookup. `as_fact_sheet` renders three sections.

Also fixed field-extraction keys (hardware in `training_strategy.hardware_limit`, datasets in `composition_and_types`, loss named `optimization_target`, singular Epoch).

### 0.4 v17.0 G1: Venue-Driven Per-Chapter

chapter_elements moved from hardcoded to `venue_profile.content_patterns[section_name].chapter_elements` (zero new profile fields). Non-numeric chapters (`has_formula=False` and not Experiments) skip `_judge_metric_attribution` LLM call. Audit overclaim guard narrowed (ch1 Introduction skipped).

---

## 1. System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        pipeline.py (entry)                      │
│                          ↓ --no-resume                          │
│                    ResearchLoop.run()                            │
│              THINK → EXECUTE → VERIFY → REFLECT                 │
└──────────────────────┬──────────────────────────────────────────┘
                       │
       ┌───────────────┼───────────────┐
       ↓               ↓               ↓
  ┌─────────┐   ┌─────────────┐  ┌──────────┐
  │ Phase 0 │→→│ Phase 1~5   │→→│ Phase 6~9│
  │ Analysis│   │ Chapter gen │  │ Post-proc│
  │         │   │(ChapterAgent)│  │(Governance)│
  └─────────┘   └─────────────┘  └──────────┘
```

**Principles**: LLM direct LaTeX / code=judge LLM=player / review-revise-verify separation / zero-trust / full-chain fallback.

---

## 2. Directory Structure

```
paper-writing-assistant/
├── pipeline.py                  # Entry
├── run_with_log.py              # Log Tee wrapper
├── config/                      # Config layer
│   ├── project_config.py  api_config.py  venue_profiles/ (11)
├── api/                         # API clients
│   ├── openai_compatible.py  mcp_http_client.py  web_search_api.py  paper_search.py
├── agent/                       # Agent core
│   ├── core/                    # Kernel contracts (5 blocks, zero cyclic deps)
│   │   ├── errors.py  factbase.py  finding.py  figure_manifest.py  citation_base.py
│   ├── loop.py                  # Engine (heart)
│   ├── chapter_agent.py         #   🔄 L1 provincial (venue-driven)
│   ├── auditor.py  quality_gate.py  verifier.py  fix_executor.py
│   ├── cross_chapter_checker.py  venue_adapter.py  hierarchical_planner.py
│   ├── api_client.py  dispatcher.py  skill_orchestrators/  checkpoint.py
├── tools/                       # Tools
│   ├── vertical_checkers.py     #   🔄 L2 vertical Checkers
│   ├── output_evaluator.py      #   🔄 L3 eval + GlobalReviewer
│   ├── latex_converter.py  bibtex_builder.py  arch_diagram_renderer.py
│   ├── figure_generator.py  pdf_compiler.py  pdf_validator.py
├── figure/style_templates.py    # Only active dep
├── skills/academic_writing_style/  test/  data/reference_packs/
```

---

## 3. Core Loop: THINK → EXECUTE → VERIFY → REFLECT

| Stage | Duty | LLM |
|-------|------|-----|
| THINK | Plan next task | No (rule engine) |
| EXECUTE | Dispatch to workers | Yes |
| VERIFY | Pure-code checks (cites/data/formula/dedup/markers/structure/symbols) | No |
| REFLECT | LLM quality eval, update memory | Yes |

---

## 4. Pipeline

### 4.1 Phase 0 — Analysis

| Phase | Name | Module | Function |
|-------|------|--------|----------|
| 0.1 | Code analysis | `project_analyzer.py` | Scan PROJECT_CODE_PATH, extract novelty/model/experiments |
| 0.2 | Reference papers | `ref_pdf_analyzer.py` | Load ref_md/ (md first) or ref_pdf/, extract style/organization |
| 0.3 | Novelty verify | `innovation_verifier.py` | Novelty check + progressive design |
| 0.5 | Ref pool + outline | `structure_planner.py` | Offline + OpenAlex → pool (51+) + outline.json |
| 0.6 | Motivation | `motivation_engine.py` | Force-confirm motivation (flag ENABLE_MOTIVATION_ENGINE) |
| 0.65 | Style + strategy | `content_strategist.py` | Venue style + content strategy |
| 0.7 | ~~Exemplar~~ | — | ⚠️ Removed v14 (idle placeholder) |
| 0.8 | Citation bank | `citation_injector.py` | claims → chapter prompts |
| 0.9 | ~~Rationale~~ | — | ⚠️ Removed v14 (idle placeholder) |
| 0.95 | Ablation | `ablation_designer.py` | Ablation automation (flag RUN_ABLATION) |
| 0.98 | FactBase | `loop._build_paper_context` | Build single truth source, owner three-way, persist factbase.json |
| 0.99 | Figure pre-plan | `loop._plan_figures_early` | Figure-text linkage before chapters |

### 4.2 Phase 1~5 — Chapter Generation (🔄 via ChapterAgent)

| Phase | Chapter | Notes |
|-------|---------|-------|
| 1 | Introduction | ChapterAgent.run(1): generate→quality loop→subsection verify→audit |
| 2 | Related Work | ChapterAgent.run(2) |
| 3 | Methodology | ChapterAgent.run(3) (has_formula=True, triggers numeric judge) |
| 4 | Experiments | ChapterAgent.run(4) (has_table=True) |
| 5 | Conclusion | ChapterAgent.run(5) |

**Per-chapter run**: generate → `_quality_ensure` (max 3 rounds) → `_verify_with_awareness` (venue-driven short-circuit) → `_audit_chapter` cohesion → FindingBus record → store.

**Extensions**: 5.1 Discussion / 5.2 Limitations (venue-configured) / 5.5 abstract+keywords / 5.6 pre-lock audit.

### 4.3 Phase 6~9 — Post-processing (governance loop)

| Phase | Name | Layer | Function |
|-------|------|-------|----------|
| 6 | Reference review | — | Verify citation retrievability |
| 6.5 | cross_chapter | L1 horizontal | ⚠️ Lightweighted (audit moved to ChapterAgent), cross-chapter consistency only |
| 7.x | Output assembly | — | Global polish→figures→LaTeX→BibTeX→constraint pre-check |
| **8** | **Compile + pre-review** | **L2+L4a+L4b** | run_all_vertical_checks → execute_fixes → Verifier → PDF compile |
| **8.5** | **PDF validation** | — | Structure + visual (max 3 fix rounds) |
| **8.8** | **Layered acceptance** | — | Atomic/abstract/global acceptance |
| **9** | **Eval + loop** | **L3+L5** | L3 adversarial review → issues → closed-loop rewrite → recompile (B2 fix) |

### 4.4 Governance → Phase Mapping

| Layer | Phase | Call site |
|-------|-------|-----------|
| L1 ChapterAgent | Phase 1-5 | `loop.py chapter_agent.run(ch_num)` |
| L2 Checkers | Phase 8 + Phase 9 post-loop | `loop.py run_all_vertical_checks` |
| L3 GlobalReviewer | Phase 9 | `loop.py run_output_evaluator` |
| L4a FixExecutor | Phase 8 + Phase 9 post-loop | `loop.py execute_fixes` |
| L4b Verifier | Phase 8 | `loop.py` Verifier recheck |
| L5 Regression | Phase 1-5 post-revise + Phase 9 | `quality_gate.py _check_revise_regression` |

---

## 5. Core Module Design

### 5.1 API Client (fallback chain)

`glm-5.2 → glm-5.1 → glm-4.7 → glm-5 → glm-4.5v → glm-4.6v` (2 retries each, AllModelsExhausted on total failure).

**Three tiers**: generation (glm-5.2/5.1) / reasoning (glm-5.2/5.1/4.7 thinking) / light (glm-4.6v/5/4.5v).

**Eval isolation**: eval model preferred cross-provider (avoid self-review blind spot), resolved by `resolve_eval_models()`.

### 5.2 LaTeX Assembly

Chapter Prompt (native LaTeX) → `_minimal_cleanup` (remove [?], empty sections, Markdown residue) → Phase 7.x (polish→figures→assemble) → `output/latex/main.tex` → Phase 8 (XeLaTeX) → `output/full_paper.pdf`.

### 5.3 Citation Pipeline

```
Phase 0.5a: offline packs + OpenAlex → reference_pool.json (51+)
Phase 0.8:  build_citation_bank() → claims
Phase 1-5:  LLM → <citation> markers
Phase 7.8:  [N] → \cite{key} + BibTeX (CitationBase.build_bib single entry)
Phase 8:    XeLaTeX → PDF
```

**v17.0 cite conservation**: cite keys conserved end-to-end, single-source injection, 100% traceable.

### 5.4 FactBase Single Source of Truth

FactBase is the **single source of truth** for numbers/facts (`agent/core/factbase.py`). Old PaperContext had auditor/verifier re-deriving from project_data independently → numeric divergence. v13 unified to FactBase.

```
Phase 0.98: loop._build_paper_context()
       ↓ extract from project_data + experiment_design (G4-b real key aliases)
FactBase = { hardware, training_params, loss_terms, datasets, metrics, model_name }
       ├─→ persist output/factbase.json
       ├─→ G4-a: owner three-way (ours / baseline / auxiliary), auxiliary excluded from pairing
       └─→ inject into cross_chapter_checker / citation_injector / auditor
```

### 5.5 Style System

P0 writing_discipline.md (10 universal rules) → P1 venue_profile (content patterns + chapter_elements) → P2 ieee_trans_style_profile.py (IEEE hard rules) → P3 style_guide.md (IEEE-specific).

### 5.6 Scoring (L1/L2/L3)

```
Grade = L1 × 0.10 + L2 × 0.35 + L3 × 0.55
A ≥ 80, B ≥ 65, C ≥ 50, D < 50

L1 format (12 checks): IEEE template / no Markdown / no placeholders / valid cites / ...
L2 content (6 checks): sections / word count / cites≥25 / formulas / tables≥3 / no placeholders
L3 academic: paperjury adversarial review (Fatal-flaw + Forensic, 2 rounds)

Forced D: critical_fails OR L1 < 60
GlobalReviewer (L3): chapter quality≥80 but full L3<70 → full-text final say
```

---

## 6. Fallback Chains

- **API**: `glm-5.2 → glm-5.1 → glm-4.7 → glm-5 → glm-4.5v → glm-4.6v`
- **Search**: `offline packs(32) → MCP Zhipu → OpenAlex(300M+)` (China: SKIP_ONLINE_VERIFICATION=1)
- **BibTeX**: metadata template (100%, <1s/entry)
- **References**: `ref_md/*.md (first) → ref_pdf/*.pdf`

---

## 7. Key Design Decisions

- **7.1 LLM direct LaTeX**: no Markdown→LaTeX intermediate
- **7.2 Code=judge, LLM=player**: all LLM output code-verified
- **7.3 Unified dispatch**: Phase 1-5 via `chapter_agent.run(ch_num)` (venue-driven)
- **7.4 Context mgmt**: no bounded_context module; FactBase persistence + citation_context inline fingerprint + previous_summary

---

## 8. Configuration

### 8.1 Venue Profiles (11)

6 journals (IEEE TCSVT/TIP/TPAMI/IJCV/Pattern Recognition/Displays) + 5 conferences (CVPR/ICCV/ECCV/AAAI/NeurIPS). Falls back to IEEE TIP. Each profile: thresholds/budgets/content patterns/`chapter_elements`.

> **⚠️ Tech debt**: Profile is Python class (~1650 lines), should migrate to Markdown.

### 8.2 Key Thresholds (base_profile defaults)

| Param | Value | Use |
|-------|-------|-----|
| `quality_pass_threshold` | 70.0 | Quality gate pass |
| `quality_max_retries` | 3 | Max chapter revision rounds |
| `min_references` | 25 | L2 min citations |

---

## 9. Data Flow

```
PROJECT_CODE_PATH/          ref_md/ + ref_pdf/
         │                          │
         ↓                          ↓
   Phase 0.1 code scan       Phase 0.2 ref analysis
         └──────────┬───────────────┘
                    ↓
         Phase 0.5~0.99 (planning + FactBase + figure pre-plan)
                    ↓
         Phase 1-5 (ChapterAgent generation)
                    ↓
         Phase 7 (assembly) + Phase 8 (compile)
                    ↓
       main.tex    references.bib   full_paper.pdf
                    ↓
         Phase 9 (L1/L2/L3 eval + L3 closed-loop rewrite)
                    ↓
          evaluation_report.json
```

---

## 10. Operations

### Start

```bash
python pipeline.py              # Auto-resume (default)
python pipeline.py --no-resume  # From scratch
python pipeline.py --debug      # Debug
python pipeline.py --title "Title"  --output ./out  --code-path /path
```

### Checkpoint Resume

Checkpoints in `output/.checkpoints/` (index.json + state/ per-key files). Saved after each phase; failed/interrupted on error. Resume skips completed phases.

### Output

```
output/
├── full_paper.pdf  latex/main.tex  latex/references.bib
├── factbase.json  experiment_design.json  figure_plan.json  reference_pool.json
├── chapter1~5/  evaluation_report.json  .checkpoints/
```

---

## 11. PaperJury Unified Evaluation

One paradigm (paperjury), two moments (generation + final), one revision loop (QualityGate). Generation-phase QualityGate uses paperjury two-round review (issues + evidence_anchor + close_criterion). Final Phase 9 uses same paradigm full-text. L3 major issues trigger evidence-grounded paragraph rewrite (`_run_l3_revision_loop`), then recompile PDF (B2 ghost-fix).

---

## Appendix A: Architecture Evolution

| Version | Key Changes |
|---------|-------------|
| **v17.0** | Six-layer governance loop + FactBase owner three-way + venue-driven per-chapter + dead code cleanup + bilingual docs |
| v16.3 | Citation subsystem (cite conservation) + LLM numeric downgrade + resume sync + governance 5 batches (12 BPs) |
| v16.2 | Write-while-revising + full-text check (linear→loop) |
| v16.1 | Evidence-grounded rewrite `_revise_with_evidence` |
| v16 | Numeric credibility 3 defense lines |
| v15.9 | FixAction executor + warning visibility |
| v15.8 | Weakness consistency + FactBase comparison |
| v15.7 | Figure-text linkage (planning forward) |
| v15.6 | Post-run root-cause fixes (4 bugfixes) |
| v15.5 | Citation pre-check + figure plan persist |
| v15.3 | Eval credibility + numeric owner + forward loop |
| v14 | Kernel contracts (errors/FactBase/Finding/FigureManifest/CitationBase) + paperjury |
| v13 | Kernel rebuild + wiring + Wave 1-6 |
| v12 | Architecture fix + citation pipeline + PipelineContext |
| v11 | China-network adaptation + reference rebuild |
| v10.1 | Venue adaptation + content strategy |
| v9.0 | First complete paper (LaTeX direct + overflow self-heal) |
