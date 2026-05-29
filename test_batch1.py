#!/usr/bin/env python3
"""
Batch 1 & 2 修复验证脚本
检查：
1. #### 标题残留
2. 表格宽度
3. 作者信息
4. BibTeX 条目数
5. 星号残留
6. 异常字符
7. 摘要长度
8. table*/tabular* 环境
"""

import re
import os

OUTPUT_DIR = "/home/bigboss/code/paper-writing-assistant/output"
TEX_PATH = os.path.join(OUTPUT_DIR, "latex", "main.tex")
BIB_PATH = os.path.join(OUTPUT_DIR, "latex", "references.bib")

print("=" * 60)
print("Batch 1 修复验证")
print("=" * 60)

# 读取 main.tex
with open(TEX_PATH, 'r', encoding='utf-8') as f:
    tex_content = f.read()

# 1. 检查 #### 标题残留
hash_residuals = len(re.findall(r'\\#\#+|^\s*#{3,}', tex_content, re.MULTILINE))
print(f"\n1. #### 标题残留: {hash_residuals} 处")
if hash_residuals > 0:
    for match in re.finditer(r'\\#\#+|^\s*#{3,}', tex_content, re.MULTILINE):
        line_num = tex_content[:match.start()].count('\n') + 1
        print(f"   第 {line_num} 行: {match.group()[:50]}")

# 2. 检查表格宽度
tables = re.findall(r'\\begin\{tabular\*?\}\{([^}]+)\}', tex_content)
print(f"\n2. 表格检查: {len(tables)} 个表格")
for i, col_spec in enumerate(tables):
    col_count = col_spec.count('l') + col_spec.count('p') + col_spec.count('c') + col_spec.count('r')
    has_p_col = 'p{' in col_spec
    is_tabular_star = 'tabular*' in tex_content[max(0, tex_content.find(col_spec)-50):tex_content.find(col_spec)]
    print(f"   表格 {i+1}: {col_count} 列, p{{}} 列={has_p_col}, tabular*={is_tabular_star}")

# 3. 检查作者信息
has_anonymous = "Anonymous" in tex_content
has_ruifeng = "Ruifeng Huang" in tex_content
has_zhenglong = "Zhenglong Cui" in tex_content
has_buaa = "Beihang" in tex_content
print(f"\n3. 作者信息:")
print(f"   Anonymous: {has_anonymous}")
print(f"   Ruifeng Huang: {has_ruifeng}")
print(f"   Zhenglong Cui: {has_zhenglong}")
print(f"   Beihang University: {has_buaa}")

# 4. 检查 BibTeX 条目
if os.path.exists(BIB_PATH):
    with open(BIB_PATH, 'r', encoding='utf-8') as f:
        bib_content = f.read()
    bib_entries = len(re.findall(r'@article\{|@inproceedings\{', bib_content))
    print(f"\n4. BibTeX 条目: {bib_entries} 条")
    
    # 检查无效条目
    invalid_entries = re.findall(r'@article\{ref\d+\w*,', bib_content)
    print(f"   无效引用 (refNxxx): {len(invalid_entries)} 条")
else:
    print(f"\n4. BibTeX 文件不存在: {BIB_PATH}")

# 5. 检查星号残留
asterisk_residuals = len(re.findall(r'^\*\s+', tex_content, re.MULTILINE))
print(f"\n5. 星号残留: {asterisk_residuals} 处")

# 6. 检查异常字符
replacement_chars = len(re.findall(r'\ufffd', tex_content))
print(f"\n6. 异常字符 (U+FFFD): {replacement_chars} 个")

# 7. 检查摘要长度
abstract_match = re.search(r'\\begin\{abstract\}\s*(.*?)\s*\\end\{abstract\}', tex_content, re.DOTALL)
if abstract_match:
    abstract_text = abstract_match.group(1)
    abstract_words = len(abstract_text.split())
    print(f"\n7. 摘要长度: {abstract_words} 词")
else:
    print(f"\n7. 摘要未找到")

print("\n" + "=" * 60)
print("验证完成")
print("=" * 60)
