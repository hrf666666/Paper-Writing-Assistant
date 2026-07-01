# Paper Writing Assistant v17.0

> **[中文](README.md)** | English

An intelligent academic paper writing system powered by multiple LLMs. Given **article type + paper title + project source code**, it generates a complete 5-chapter + abstract academic paper (LaTeX) as a writing reference or starting point.

**v17.0 Highlights**: Layered governance architecture (six-layer review-revise-verify loop) + FactBase owner three-way classification + venue-driven per-chapter differentiation. Built on the **THINK → EXECUTE → VERIFY → REFLECT** autonomous loop.

---

## What It Does

| Capability | Description |
|------------|-------------|
| **End-to-end paper generation** | From project code + reference papers → complete 5-chapter + abstract IEEE-format PDF |
| **Six-layer governance loop** | Review (L1/L2) → Revise (L4a) → Verify (L4b) → Arbitrate (L3) → Gatekeep (L5), separation of concerns |
| **Numerical credibility** | FactBase truth injection + post-write detection + evidence-grounded paragraph rewrite; owner three-way classification prevents baseline mislabeled as ours |
| **Citation subsystem** | cite-key conservation guard + single-source-of-truth injection, 100% traceable citations |
| **Write-while-revising loop** | Pipeline evolved from linear (generate→detect→report) to closed-loop (inline revision + full-text check) |
| **Venue-adaptive** | 11 venue profiles (TCSVT/TIP/TPAMI/CVPR...), chapter elements venue-driven |
| **China-network friendly** | Offline data packs + MCP Zhipu + OpenAlex, no dependency on China-blocked academic APIs |

---

## Core Architecture: Six-Layer Governance

A government-governance-metaphor six-layer architecture, built to fix "review without revise, revise without verify, repeated review without arbitration" problems exposed in real PDF runs.

| Layer | Role | Module | Boundary |
|-------|------|--------|----------|
| **L1** | Provincial | `chapter_agent.py` ChapterAgent | One chapter only: generate→review→revise→audit cohesion |
| **L2** | Ministry (vertical) | `vertical_checkers.py` 5 Checkers | Review only: bib/formula/table/figure/language |
| **L3** | Central (full-text) | `output_evaluator.py` GlobalReviewer | Full-text arbitration: chapter ok but full-text fails → full-text wins |
| **L4a** | Executor | `fix_executor.py` FixExecutor | Revise only: route fixes by Finding, deterministic first |
| **L4b** | Inspector | `verifier.py` ContentVerifier | Verify only: re-check after fix, resolve only on pass |
| **L5** | Decision hub | `loop.py` + `quality_gate.py` | Dispatch + independent regression guard after revise |

**Principles**: review-revise-verify separation / Finding as sole carrier / one-way decision chain / provincial autonomy + central arbitration.

> See [architecture.en.md §0](architecture.en.md)

---

## Tech Stack

- **Python 3.11+** (conda py311 env required)
- **LLM**: Zhipu GLM series (glm-5.2/5.1/4.7/5/4.5v/4.6v, 6-level fallback chain)
- **Academic search**: Offline packs → MCP Zhipu Web Search → OpenAlex (300M+ papers)
- **BibTeX**: metadata template generation (100% success, <1s/entry)
- **LaTeX**: XeLaTeX + bibtex, overflow detection and self-healing
- **Figures**: matplotlib + TikZ + pdflatex compile validation
- **PDF validation**: PyMuPDF (fitz) structural + visual checks

---

## Quick Start

### 1. Install

```bash
git clone <repository-url>
cd paper-writing-assistant
conda create -n py311 python=3.11
conda activate py311
pip install -r requirements.txt
```

### 2. Configure

```bash
cp env.example .env
```

Edit `.env`:

| Variable | Required | Description |
|----------|----------|-------------|
| `GLM_CODING_PLAN_API_KEY` | **Yes** | Zhipu GLM (main generation + MCP search + zai SDK) |
| `ALI_TOKEN_PLAN_API_KEY` | Optional | Alibaba Token Plan (backup provider) |
| `ALI_BAILIAN_API_KEY` | Optional | Alibaba Bailian Qwen (backup) |
| `OPENAI_API_KEY` | Optional | OpenAI (needs proxy) |
| `CLAUDE_API_KEY` | Optional | Claude (needs proxy) |

Edit `config/project_config.py` to set `TARGET_VENUE`, `PAPER_TITLE`, `PROJECT_CODE_PATH`.

### 3. Run

```bash
python pipeline.py              # Auto-resume from checkpoint (default)
python pipeline.py --no-resume  # Start from scratch
python pipeline.py --debug      # Debug mode
python pipeline.py --title "My Paper Title"        # Override title
python pipeline.py --output ./my_output            # Override output dir
python pipeline.py --code-path /path/to/project    # Override code path
```

> China network: `SKIP_ONLINE_VERIFICATION=1` is on by default, skipping timed-out S2/CrossRef/DBLP online verification.

---

## Pipeline

| Phase | Task | Notes |
|-------|------|-------|
| **0.1-0.3** | Project analysis | Scan code + reference papers + novelty verification |
| **0.5** | Ref pool + outline | Offline packs + OpenAlex → reference_pool (51+) + outline |
| **0.6-0.65** | Motivation + style | Motivation confirmation + venue style learning + content strategy |
| **0.8** | Citation bank | claims → injected into chapter prompts |
| **0.95** | Ablation | Ablation automation (optional) |
| **0.98** | FactBase | Build single source of truth, owner three-way classification |
| **0.99** | Figure pre-planning | Figure-text linkage before chapters |
| **1-5** | **Chapter generation** | 🔄 Via ChapterAgent (L1): generate→quality loop→subsection verify→audit |
| **5.1-5.6** | Extensions + abstract | Discussion/Limitations/abstract+keywords/pre-lock audit |
| **6-6.5** | Reference review | Reference verification + cross_chapter (6.5 lightweighted) |
| **7.x** | Output assembly | Global polish→figures→LaTeX→BibTeX→constraint pre-check |
| **8** | Compile | PDF compilation (XeLaTeX) |
| **8.5** | PDF validation | Structural + visual validation (max 3 fix rounds) |
| **8.8** | Layered acceptance | Atomic/abstract/global acceptance |
| **9** | **Evaluation** | 🔄 L3 adversarial review (paperjury) + L3 closed-loop rewrite |

> **Note**: Phase 0.7 (exemplar_learner) / 0.9 (rationale_matrix) were removed in v14, now idle placeholders.

### Governance Layers → Phase Mapping

| Layer | Runs in Phase |
|-------|---------------|
| L1 ChapterAgent | Phase 1-5 (per chapter run) |
| L2 Vertical Checkers | Phase 8 pre-compile + Phase 9 post-loop |
| L3 GlobalReviewer | Phase 9 evaluation |
| L4a FixExecutor | Phase 8 pre-compile + Phase 9 post-loop |
| L4b Verifier | Phase 8 (re-check before resolve) |
| L5 Regression guard | Phase 1-5 post-revise + Phase 9 recompile |

---

## Scoring

```
Grade = L1 × 0.10 + L2 × 0.35 + L3 × 0.55
A ≥ 80, B ≥ 65, C ≥ 50, D < 50

L1 Format validity (12 checks): IEEE template / no Markdown / no placeholders / valid cites / ...
L2 Content completeness (6 checks): sections / word count / cites≥25 / formulas / tables≥3 / no placeholders
L3 Academic quality: paperjury adversarial review (two rounds: Fatal-flaw + Forensic)

Forced D: critical_fails exist OR L1 < 60
Each critical_fail deducts 10 from L3 score
```

---

## Project Structure

```
paper-writing-assistant/
├── agent/                        # Agent core
│   ├── core/                     #   Kernel contract layer (5 blocks)
│   │   ├── errors.py  factbase.py  finding.py  figure_manifest.py  citation_base.py
│   ├── loop.py                   #   Pipeline engine (heart)
│   ├── chapter_agent.py          #   🔄 L1 provincial chapter agent (venue-driven)
│   ├── auditor.py                #   Anti-hallucination audit (L1 cohesion)
│   ├── quality_gate.py           #   Quality gate + L5 regression guard
│   ├── verifier.py               #   🔄 L4b inspector
│   ├── fix_executor.py           #   🔄 L4a executor
│   ├── cross_chapter_checker.py  #   Cross-chapter consistency (reads FactBase)
│   └── skill_orchestrators/      #   Chapter orchestrators
├── tools/
│   ├── vertical_checkers.py      #   🔄 L2 vertical Checkers (5 specialties)
│   ├── output_evaluator.py       #   🔄 L3 evaluation + GlobalReviewer
│   ├── latex_converter.py        #   LaTeX assembly
│   ├── figure_generator.py       #   TikZ figure generation
│   └── pdf_compiler.py           #   XeLaTeX compilation
├── config/
│   ├── project_config.py         #   Project config
│   └── venue_profiles/           #   11 venue profiles
├── api/                          # API client layer
├── test/                         # pytest tests (92 + test_unit/ 449, gitignored)
├── pipeline.py                   # Entry point
└── requirements.txt
```

---

## Configuration

### Venue Profiles (11)

| Type | Venues |
|------|--------|
| Journals | IEEE TCSVT / TIP / TPAMI / IJCV / Pattern Recognition / Displays |
| Conferences | CVPR / ICCV / ECCV / AAAI / NeurIPS |

Falls back to IEEE TIP if unmatched. Each profile has section budgets / figure requirements / content patterns / `chapter_elements` (venue-driven per-chapter differentiation).

### Model Fallback Chain (6 levels, GLM only after v15.3 connectivity tests)

```
glm-5.2 → glm-5.1 → glm-4.7 → glm-5 → glm-4.5v → glm-4.6v
```

Execution-evaluation model isolation (cross-provider preferred). Vision models: glm-4.6v → glm-4.5v.

---

## Output Files

| File | Description |
|------|-------------|
| `output/full_paper.pdf` | Final PDF paper |
| `output/latex/main.tex` | LaTeX source |
| `output/latex/references.bib` | BibTeX references (25+) |
| `output/factbase.json` | FactBase truth store (owner three-way) |
| `output/experiment_design.json` | Experiment design |
| `output/figure_plan.json` | Figure plan |
| `output/reference_pool.json` | Reference pool (51+) |
| `output/citation_map.json` | [N] → \cite{key} mapping |

---

## Extending Offline Reference Packs

Add JSON files to `data/reference_packs/`:

```json
{
  "domain": "your_research_domain",
  "papers": [
    {
      "title": "Paper Title",
      "authors": ["Author"],
      "year": 2024,
      "venue": "Venue Name",
      "doi": "10.xxxx/xxxxx",
      "tags": ["keywords"]
    }
  ]
}
```

---

## CHANGELOG

| Version | Key Changes |
|---------|-------------|
| **v17.0** | Six-layer governance loop (review-revise-verify separation) + FactBase owner three-way + venue-driven per-chapter + dead code cleanup + bilingual docs |
| v16.3 | Citation subsystem fix (cite conservation) + numeric validation LLM downgrade + resume sync |
| v16.2 | Write-while-revising + full-text check loop (linear→closed-loop) |
| v16.1 | Evidence-grounded paragraph rewrite (3rd defense line) |
| v16 | Numeric credibility three defense lines |
| v15.9 | FixAction executor + warning visibility |
| v15.8 | Weakness consistency loop + FactBase comparison |
| v15.7 | Figure-text linkage fix (planning forward + comm loop) |
| v15.6 | Post-run root-cause fixes (4 bugfixes) |
| v15.5 | Citation pre-check gate + figure plan persistence |
| v15.3 | Evaluation credibility + numeric owner truth + forward loop |
| v14 | Kernel contract layer (errors/FactBase/Finding/FigureManifest/CitationBase) + paperjury |
| v13 | Kernel rebuild + wiring + Wave 1-6 slimming |
| v12 | Architecture fix (generality/feature separation) + citation pipeline + PipelineContext |
| v11 | China-network adaptation + reference system rebuild (offline-first) |
| v10.1 | Venue adaptation + content strategy |
| v9.0 | First complete paper output (LaTeX direct + overflow self-heal) |

> Detailed architecture evolution: [architecture.en.md](architecture.en.md) Appendix A.

---

## Disclaimer

This tool is for academic research and educational purposes only. Users must:
- Comply with academic integrity and institutional codes of conduct
- Use outputs for writing study, structural analysis, or content planning reference
- Thoroughly review, modify, and verify generated content
- Accurately cite all sources, never fabricate data or results

**The authors are not responsible for any academic misconduct arising from use of this tool.**
