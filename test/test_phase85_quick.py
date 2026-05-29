#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 8.5 快速验证测试
使用现有归档输出进行完整验证测试
"""

import os
import sys
import json
import logging
from datetime import datetime

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


def run_comprehensive_test():
    """运行综合测试"""
    print("="*80)
    print("Phase 8.5: PDF 编译验证器 - 综合测试报告")
    print("="*80)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"项目路径: {project_root}")
    print()

    # 查找可用的输出目录
    output_dirs = []
    
    # 1. 检查当前 output 目录
    current_output = os.path.join(project_root, "output")
    if os.path.exists(os.path.join(current_output, "latex", "main.tex")):
        output_dirs.append(("current", current_output))
    
    # 2. 检查归档目录
    cases_dir = os.path.join(project_root, "cases")
    if os.path.exists(cases_dir):
        for dirname in sorted(os.listdir(cases_dir), reverse=True)[:3]:
            dirpath = os.path.join(cases_dir, dirname)
            if os.path.exists(os.path.join(dirpath, "latex", "main.tex")):
                output_dirs.append((dirname, dirpath))

    if not output_dirs:
        print("❌ 未找到可用的输出目录")
        print("请先运行 pipeline 生成输出文件")
        return

    # 对每个输出目录运行测试
    for name, output_dir in output_dirs:
        print("\n" + "="*80)
        print(f"测试输出: {name}")
        print(f"目录路径: {output_dir}")
        print("="*80)

        test_single_directory(output_dir, name)


def test_single_directory(output_dir: str, test_name: str):
    """测试单个输出目录"""
    
    latex_dir = os.path.join(output_dir, "latex")
    
    # 检查必要文件
    tex_path = os.path.join(latex_dir, "main.tex")
    bib_path = os.path.join(latex_dir, "references.bib")
    log_path = os.path.join(latex_dir, "main.log")
    
    print("\n📋 文件检查:")
    print(f"  main.tex: {'✅' if os.path.exists(tex_path) else '❌'}")
    print(f"  references.bib: {'✅' if os.path.exists(bib_path) else '❌'}")
    print(f"  main.log: {'✅' if os.path.exists(log_path) else '❌'}")

    if not os.path.exists(tex_path):
        print("⚠️  跳过此目录（缺少 main.tex）")
        return

    # 创建验证器
    validator = PDFValidator(output_dir)

    # 测试 1: 解析编译日志
    print("\n" + "-"*80)
    print("测试 1: 编译日志解析")
    print("-"*80)
    
    if os.path.exists(log_path):
        issues = validator._parse_compile_log()
        print(f"\n发现 {len(issues)} 个问题")
        
        # 按严重程度统计
        severity_count = {}
        type_count = {}
        for issue in issues:
            sev = issue.get('severity', 'unknown')
            severity_count[sev] = severity_count.get(sev, 0) + 1
            
            typ = issue.get('type', 'unknown')
            type_count[typ] = type_count.get(typ, 0) + 1
        
        print("\n严重程度分布:")
        for sev, count in sorted(severity_count.items()):
            print(f"  {sev}: {count}")
        
        print("\n问题类型分布:")
        for typ, count in sorted(type_count.items(), key=lambda x: -x[1]):
            print(f"  {typ}: {count}")
        
        # 显示前 10 个关键问题
        critical_issues = [i for i in issues if i.get('severity') == 'critical']
        if critical_issues:
            print(f"\n前 10 个严重问题:")
            for i, issue in enumerate(critical_issues[:10], 1):
                print(f"  {i}. [{issue['type']}] {issue['message'][:100]}")
                if issue.get('line'):
                    print(f"     行号: {issue['line']}")
                print(f"     建议: {issue['suggestion'][:80]}")
    else:
        print("⚠️  编译日志不存在，跳过")
        issues = []

    # 测试 2: 元素验证
    print("\n" + "-"*80)
    print("测试 2: 元素完整性验证")
    print("-"*80)
    
    pdf_path = os.path.join(output_dir, "full_paper.pdf")
    elements = validator._validate_elements(tex_path, bib_path, pdf_path)
    
    print(f"\n引用验证:")
    print(f"  .tex 引用数: {elements.get('citations_in_tex', 0)}")
    print(f"  .bib 条目数: {elements.get('citations_in_bib', 0)}")
    print(f"  匹配状态: {'✅' if elements['citations_match'] else '❌'}")
    if elements.get('missing_citations'):
        print(f"  缺失引用: {len(elements['missing_citations'])} 个")
        for cite in elements['missing_citations'][:5]:
            print(f"    - {cite}")
    
    print(f"\n表格验证:")
    print(f"  渲染数量: {elements['tables_rendered']}")
    print(f"  截断数量: {elements['tables_truncated']}")
    
    print(f"\n图片验证:")
    print(f"  渲染数量: {elements['figures_rendered']}")
    print(f"  缺失数量: {elements['figures_missing']}")
    
    print(f"\n公式验证:")
    print(f"  公式数量: {elements['formulas_count']}")
    print(f"  标签数量: {elements.get('formula_labels', 0)}")

    # 测试 3: PDF 结构验证（如果 PDF 存在）
    print("\n" + "-"*80)
    print("测试 3: PDF 结构验证")
    print("-"*80)
    
    if os.path.exists(pdf_path):
        structure = validator._validate_pdf_structure(pdf_path)
        print(f"\nPDF 结构:")
        print(f"  页数: {structure.get('pages', 0)}")
        print(f"  空白页: {structure.get('blank_pages', [])}")
        print(f"  文本覆盖率: {structure.get('text_coverage', 0):.2%}")
        print(f"  验证结果: {'✅ 通过' if structure.get('valid') else '❌ 失败'}")
        
        if structure.get('file_size_kb'):
            print(f"  文件大小: {structure['file_size_kb']} KB")
    else:
        print("⚠️  PDF 文件不存在，跳过结构验证")

    # 测试 4: 完整验证流程（含编译）
    print("\n" + "-"*80)
    print("测试 4: 完整验证流程（编译→验证→修复）")
    print("-"*80)
    
    print("\n开始完整验证流程（最多 3 次重试）...")
    result = run_pdf_validator(output_dir, max_retries=2)
    
    print(f"\n✅ 验证结果:")
    print(f"  通过状态: {'✅ 通过' if result['passed'] else '❌ 未通过'}")
    print(f"  重试次数: {result['retry_count']}")
    
    print(f"\n📊 编译日志问题:")
    print(f"  总问题数: {len(result['compile_log_issues'])}")
    
    print(f"\n📄 PDF 结构:")
    struct = result.get('pdf_structure', {})
    print(f"  页数: {struct.get('pages', 0)}")
    print(f"  有效性: {struct.get('valid', False)}")
    
    print(f"\n🔍 元素验证:")
    elem = result.get('element_validation', {})
    print(f"  引用匹配: {elem.get('citations_match', 'N/A')}")
    print(f"  缺失引用: {len(elem.get('missing_citations', []))}")
    print(f"  表格: {elem.get('tables_rendered', 0)}")
    print(f"  图片: {elem.get('figures_rendered', 0)}")
    
    print(f"\n🔧 自动修复:")
    fix = result.get('auto_fix_attempts', {})
    print(f"  总问题: {fix.get('total_issues', 0)}")
    print(f"  已修复: {fix.get('fixed', 0)}")
    print(f"  剩余: {fix.get('remaining', 0)}")

    # 保存详细报告
    report_path = os.path.join(output_dir, f"pdf_validation_{test_name}.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n💾 详细报告已保存: {report_path}")

    return result


def main():
    """主函数"""
    try:
        run_comprehensive_test()
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*80)
    print("测试完成")
    print("="*80)


if __name__ == "__main__":
    main()
