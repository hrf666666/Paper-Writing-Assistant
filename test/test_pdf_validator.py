#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 PDF 编译验证器 (Phase 8.5)

测试场景：
1. 解析现有编译日志
2. 验证 PDF 结构
3. 验证元素完整性
4. 测试自动修复功能
"""

import os
import sys
import json
import logging

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from tools.pdf_validator import PDFValidator, run_pdf_validator

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_parse_compile_log():
    """测试编译日志解析"""
    print("\n" + "="*60)
    print("测试 1: 解析编译日志")
    print("="*60)

    output_dir = os.path.join(project_root, "output")
    validator = PDFValidator(output_dir)

    log_path = os.path.join(output_dir, "latex", "main.log")
    if not os.path.exists(log_path):
        print(f"⚠️  编译日志不存在: {log_path}")
        print("跳过此测试")
        return

    issues = validator._parse_compile_log()

    print(f"\n发现 {len(issues)} 个问题:")
    for i, issue in enumerate(issues, 1):
        print(f"\n{i}. [{issue['severity'].upper()}] {issue['type']}")
        print(f"   消息: {issue['message']}")
        if issue.get('line'):
            print(f"   行号: {issue['line']}")
        print(f"   建议: {issue['suggestion']}")

    # 统计严重程度
    critical = sum(1 for issue in issues if issue['severity'] == 'critical')
    warnings = sum(1 for issue in issues if issue['severity'] == 'warning')
    info = sum(1 for issue in issues if issue['severity'] == 'info')

    print(f"\n统计: {critical} 个严重, {warnings} 个警告, {info} 个信息")


def test_validate_pdf_structure():
    """测试 PDF 结构验证"""
    print("\n" + "="*60)
    print("测试 2: PDF 结构验证")
    print("="*60)

    output_dir = os.path.join(project_root, "output")
    validator = PDFValidator(output_dir)

    pdf_path = os.path.join(output_dir, "full_paper.pdf")
    if not os.path.exists(pdf_path):
        print(f"⚠️  PDF 文件不存在: {pdf_path}")
        print("跳过此测试")
        return

    structure = validator._validate_pdf_structure(pdf_path)

    print(f"\nPDF 结构:")
    print(f"  页数: {structure.get('pages', 0)}")
    print(f"  空白页: {structure.get('blank_pages', [])}")
    print(f"  文本覆盖率: {structure.get('text_coverage', 0):.2%}")
    print(f"  验证结果: {'✅ 通过' if structure.get('valid') else '❌ 失败'}")

    if structure.get('pages_too_few'):
        print("  ⚠️  页数过少")
    if structure.get('pages_too_many'):
        print("  ⚠️  页数过多")


def test_validate_elements():
    """测试元素验证"""
    print("\n" + "="*60)
    print("测试 3: 元素完整性验证")
    print("="*60)

    output_dir = os.path.join(project_root, "output")
    validator = PDFValidator(output_dir)

    tex_path = os.path.join(output_dir, "latex", "main.tex")
    bib_path = os.path.join(output_dir, "latex", "references.bib")
    pdf_path = os.path.join(output_dir, "full_paper.pdf")

    if not os.path.exists(tex_path):
        print(f"⚠️  .tex 文件不存在: {tex_path}")
        print("跳过此测试")
        return

    elements = validator._validate_elements(tex_path, bib_path, pdf_path)

    print(f"\n元素验证结果:")
    print(f"  引用匹配: {'✅' if elements['citations_match'] else '❌'}")
    print(f"  .tex 引用数: {elements.get('citations_in_tex', 0)}")
    print(f"  .bib 条目数: {elements.get('citations_in_bib', 0)}")

    if elements.get('missing_citations'):
        print(f"  ⚠️  缺失引用 ({len(elements['missing_citations'])} 个):")
        for cite in elements['missing_citations'][:5]:
            print(f"    - {cite}")

    print(f"  表格渲染: {elements['tables_rendered']}")
    print(f"  表格截断: {elements['tables_truncated']}")
    print(f"  图片渲染: {elements['figures_rendered']}")
    print(f"  图片缺失: {elements['figures_missing']}")
    print(f"  公式数量: {elements['formulas_count']}")


def test_full_validation():
    """测试完整验证流程"""
    print("\n" + "="*60)
    print("测试 4: 完整验证流程")
    print("="*60)

    output_dir = os.path.join(project_root, "output")

    result = run_pdf_validator(output_dir, max_retries=2)

    print(f"\n验证报告:")
    print(f"  通过: {'✅ 是' if result['passed'] else '❌ 否'}")
    print(f"  重试次数: {result['retry_count']}")

    print(f"\n编译日志问题 ({len(result['compile_log_issues'])} 个):")
    for issue in result['compile_log_issues'][:5]:
        print(f"  [{issue['severity']}] {issue['type']}: {issue['message'][:80]}")

    print(f"\nPDF 结构:")
    struct = result.get('pdf_structure', {})
    print(f"  页数: {struct.get('pages', 0)}")
    print(f"  有效: {struct.get('valid', False)}")

    print(f"\n元素验证:")
    elem = result.get('element_validation', {})
    print(f"  引用匹配: {elem.get('citations_match', 'N/A')}")
    print(f"  缺失引用: {len(elem.get('missing_citations', []))}")

    print(f"\n自动修复:")
    fix = result.get('auto_fix_attempts', {})
    print(f"  总问题: {fix.get('total_issues', 0)}")
    print(f"  已修复: {fix.get('fixed', 0)}")
    print(f"  剩余: {fix.get('remaining', 0)}")

    # 保存详细报告
    report_path = os.path.join(output_dir, "test_validation_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n详细报告已保存: {report_path}")


def main():
    """运行所有测试"""
    print("PDF 编译验证器测试 (Phase 8.5)")
    print(f"项目根目录: {project_root}")

    # 检查输出目录
    output_dir = os.path.join(project_root, "output")
    if not os.path.exists(output_dir):
        print(f"❌ 输出目录不存在: {output_dir}")
        print("请先运行 pipeline 生成输出文件")
        return

    latex_dir = os.path.join(output_dir, "latex")
    if not os.path.exists(latex_dir):
        print(f"❌ LaTeX 目录不存在: {latex_dir}")
        print("请先运行 pipeline 生成 LaTeX 文件")
        return

    # 运行测试
    try:
        test_parse_compile_log()
    except Exception as e:
        print(f"❌ 测试 1 失败: {e}")
        import traceback
        traceback.print_exc()

    try:
        test_validate_pdf_structure()
    except Exception as e:
        print(f"❌ 测试 2 失败: {e}")
        import traceback
        traceback.print_exc()

    try:
        test_validate_elements()
    except Exception as e:
        print(f"❌ 测试 3 失败: {e}")
        import traceback
        traceback.print_exc()

    try:
        test_full_validation()
    except Exception as e:
        print(f"❌ 测试 4 失败: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*60)
    print("测试完成")
    print("="*60)


if __name__ == "__main__":
    main()
