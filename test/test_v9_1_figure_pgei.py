"""
v9.1 PGEI 图片生成闭环测试
测试目标: output/quick_test
流程: Plan → Generate → Evaluate → Iterate
"""

import sys
import os
import json
import time
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)

from tools.figure_planner import plan_figures_from_tex, _extract_from_tex
from tools.iterate_controller import run_pgei_pipeline


def main():
    tex_path = "output/quick_test/main.tex"
    output_dir = "output/quick_test"
    venue = "IEEE TCSVT"

    print("=" * 60)
    print("v9.1 PGEI Figure Pipeline Test")
    print(f"  tex:    {tex_path}")
    print(f"  output: {output_dir}")
    print(f"  venue:  {venue}")
    print("=" * 60)

    # Step 1: Plan (reuse existing if available)
    plan_path = os.path.join(output_dir, "figure_plan.json")
    if os.path.exists(plan_path) and "--replan" not in sys.argv:
        print(f"\n[Step 1] Loading existing plan from {plan_path}")
        with open(plan_path) as f:
            plan = json.load(f)
        print(f"  Loaded {len(plan.get('figures', []))} figures")
    else:
        print("\n[Step 1] Planning figures from LaTeX...")
        t0 = time.time()
        plan = plan_figures_from_tex(tex_path, venue)
        print(f"  Plan done in {time.time() - t0:.1f}s, {len(plan.get('figures', []))} figures planned")

    for fig in plan.get("figures", []):
        print(f"    {fig['fig_id']}: type={fig['fig_type']}, role={fig['fig_role']}, "
              f"modules={len(fig.get('modules', []))}, connections={len(fig.get('connections', []))}")

    # Step 2: Extract paper content for PGEI
    paper_content = _extract_from_tex(tex_path)

    # Step 3: Run PGEI pipeline
    print("\n[Step 2] Running PGEI pipeline (Generate → Evaluate → Iterate)...")
    t0 = time.time()
    result = run_pgei_pipeline(
        output_dir=output_dir,
        paper_content=paper_content,
        venue=venue,
        plan=plan,
    )
    elapsed = time.time() - t0

    # Step 4: Summary
    print("\n" + "=" * 60)
    print("PGEI Pipeline Results")
    print("=" * 60)
    for fig_result in result.get("figures", []):
        fig_id = fig_result.get("fig_id", "?")
        score = fig_result.get("final_score", 0)
        iters = fig_result.get("iterations", 0)
        passed = fig_result.get("passed", False)
        pdf = fig_result.get("pdf_path", "")
        print(f"  {fig_id}: score={score:.1f}, iters={iters}, passed={'Y' if passed else 'N'}")
        print(f"    PDF: {pdf}")

    print(f"\nTotal time: {elapsed:.1f}s")
    print(f"Summary: {result.get('summary', '')}")


if __name__ == "__main__":
    main()
