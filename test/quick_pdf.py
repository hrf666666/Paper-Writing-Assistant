#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速 PDF 生成脚本 — LLM 直译版
使用 LLM 直接将 Markdown 翻译为 LaTeX（跳过正则转换）
"""
import sys, os, re, subprocess, shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.latex_converter import assemble_latex_paper

# ── 1. 读取所有章节 markdown ──
chapters = []
for i in range(1, 6):
    path = f"output/chapter{i}/chapter{i}_" + [
        "introduction", "related_work", "methodology",
        "experiments", "conclusion"
    ][i-1] + ".md"
    if not os.path.exists(path):
        print(f"[WARN] {path} 不存在，跳过")
        chapters.append("")
        continue
    with open(path, 'r') as f:
        chapters.append(f.read())
    print(f"[OK] 读取章节 {i}: {len(chapters[-1])} 字符")

# ── 2. 读取/修复 TikZ ──
tikz_path = "output/chapter3/architecture_figure.tex"
tikz_code = ""
if os.path.exists(tikz_path):
    with open(tikz_path, 'r') as f:
        tikz_code = f.read()
    # 修复非法锚点
    for wrong, correct in {'.bottom': '.south', '.top': '.north', '.left': '.west', '.right': '.east'}.items():
        tikz_code = tikz_code.replace(wrong, correct)
    print(f"[OK] TikZ 已修复: {len(tikz_code)} 字符")

# ── 3. 读取 abstract ──
abstract = ""
abstract_path = "output/abstract/abstract.md"
if os.path.exists(abstract_path):
    with open(abstract_path, 'r') as f:
        abstract = f.read()

# ── 4. 组装 LaTeX（使用 LLM 直译） ──
print("\n[...] 使用 LLM 直接翻译 MD → LaTeX ...")
latex_paper = assemble_latex_paper(chapters, tikz_code, abstract, "")

# ── 5. 最小后处理 ──
# 移除中文字符
latex_paper = re.sub(r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]', '', latex_paper)
# 确保有 \end{document}
if '\\end{document}' not in latex_paper:
    latex_paper = latex_paper.rstrip() + '\n\n\\end{document}\n'

# ── 6. 保存 + 编译 ──
out_dir = "output/quick_test"
os.makedirs(out_dir, exist_ok=True)

tex_path = os.path.join(out_dir, "main.tex")
with open(tex_path, 'w') as f:
    f.write(latex_paper)
print(f"\n[OK] LaTeX 已保存到 {tex_path} ({len(latex_paper)} 字符)")

# 复制 references.bib
bib_src = "output/latex/references.bib"
if os.path.exists(bib_src):
    shutil.copy2(bib_src, os.path.join(out_dir, "references.bib"))

# 复制 figures
figures_dir = os.path.join(out_dir, "figures")
os.makedirs(figures_dir, exist_ok=True)
for src in ["output/latex/figures", "output/figures"]:
    if os.path.isdir(src):
        for f in os.listdir(src):
            src_path = os.path.join(src, f)
            if os.path.isfile(src_path):
                shutil.copy2(src_path, os.path.join(figures_dir, f))

# 编译
env = os.environ.copy()
env['PATH'] = env.get('PATH', '') + ':/usr/local/texlive/2026/bin/x86_64-linux'

print("\n[...] 编译 LaTeX ...")
for run in range(2):
    result = subprocess.run(
        ['pdflatex', '-interaction=nonstopmode', '-output-directory', out_dir, tex_path],
        capture_output=True, timeout=60, env=env
    )

errors = re.findall(rb'^! (.+)', result.stdout, re.MULTILINE)
warnings_count = result.stdout.count(b'Warning')
pages_match = re.search(rb'Output written on .+?(\d+) pages', result.stdout)

print(f"\n{'='*50}")
if errors:
    print(f"编译错误: {len(errors)}")
    for e in errors[:8]:
        print(f"  ! {e.decode('utf-8', errors='replace')[:100]}")
else:
    print("编译错误: 0 ✅")

print(f"警告: {warnings_count}")
if pages_match:
    print(f"页数: {pages_match.group(1).decode()}")

pdf_path = os.path.join(out_dir, "main.pdf")
if os.path.exists(pdf_path):
    size = os.path.getsize(pdf_path)
    print(f"\nPDF 已生成: {pdf_path} ({size//1024}KB)")

    # 检查结构完整性
    with open(tex_path, 'r') as f:
        tex = f.read()
    sections = re.findall(r'\\section\{([^}]+)\}', tex)
    tables = tex.count('\\begin{table')
    equations = tex.count('\\begin{equation')
    print(f"\n--- 结构检查 ---")
    print(f"  Sections: {sections}")
    print(f"  Tables: {tables}")
    print(f"  Equations: {equations}")
else:
    print("\nPDF 生成失败!")
    log_path = os.path.join(out_dir, "main.log")
    if os.path.exists(log_path):
        with open(log_path, 'rb') as f:
            data = f.read()
        lines = data.decode('utf-8', errors='replace').splitlines()
        print("--- log 末尾 ---")
        for l in lines[-15:]:
            print(l)
