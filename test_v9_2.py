#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 v9.2 柔性引导 + 硬约束系统

验证项：
1. 学术风格指南是否成功加载到章节生成 prompt
2. 学术风格检查器是否正确检测 AI 风格词汇
3. QualityGate 是否融合风格评分
4. latex_converter.py 是否已移除硬编码修复
"""

import os
import sys
import re

# 设置路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agent.academic_style_checker import AcademicStyleChecker
from config.project_config import OUTPUT_DIR

def test_style_guide_loaded():
    """测试 1: 风格指南是否加载到章节生成 prompt"""
    print("\n=== 测试 1: 风格指南加载 ===")
    
    # 检查风格指南文件是否存在
    style_guide_path = os.path.join(
        os.path.dirname(__file__),
        "skills", "academic_writing_style", "style_guide.md"
    )
    
    if not os.path.exists(style_guide_path):
        print(f"❌ 风格指南文件不存在: {style_guide_path}")
        return False
    
    with open(style_guide_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查关键内容
    checks = [
        ("AI 风格词汇列表", "revolutionize" in content.lower()),
        ("括号使用规范", "20" in content and "词" in content),
        ("句子长度控制", "20-30" in content or "20 ~ 30" in content),
        ("时态规范", "时态" in content),
    ]
    
    all_passed = True
    for name, result in checks:
        status = "✅" if result else "❌"
        print(f"  {status} {name}")
        if not result:
            all_passed = False
    
    if all_passed:
        print("✅ 风格指南加载测试通过")
    else:
        print("❌ 风格指南加载测试失败")
    
    return all_passed


def test_academic_style_checker():
    """测试 2: 学术风格检查器功能"""
    print("\n=== 测试 2: 学术风格检查器 ===")
    
    checker = AcademicStyleChecker()
    
    # 测试用例：包含 AI 风格词汇的文本
    test_content = """
This paper proposes a revolutionary approach that fundamentally transforms the landscape 
of depth estimation. Our groundbreaking method achieves unprecedented performance on 
benchmark datasets. The results are remarkably superior to existing methods, demonstrating 
tremendous improvements in accuracy.
    
We delve into the tapestry of existing methods and navigate the realm of deep learning 
to foster a novel architecture. This testament to our efforts paves the way for future 
research in this big and important field.
    """
    
    result = checker.check_style_compliance(test_content, "Introduction")
    
    print(f"  合规评分: {result['score']:.1f}/100")
    print(f"  是否通过: {'✅' if result['passed'] else '❌'}")
    print(f"  发现问题: {len(result['issues'])} 个")
    
    # 检查是否检测到 AI 词汇
    ai_word_count = result['details'].get('ai_words', 0)
    print(f"  AI 风格词汇: {ai_word_count} 个")
    
    # 显示检测到的词汇
    ai_issues = [i for i in result['issues'] if i['type'] == 'ai_flavored_word']
    if ai_issues:
        print(f"  检测到的词汇:")
        for issue in ai_issues[:5]:
            print(f"    - {issue['word']} → {issue['suggestion']}")
    
    # 预期应该检测到至少 10 个 AI 词汇
    if ai_word_count >= 10:
        print("✅ 学术风格检查器测试通过")
        return True
    else:
        print(f"❌ 学术风格检查器测试失败（预期 >=10，实际 {ai_word_count}）")
        return False


def test_quality_gate_integration():
    """测试 3: QualityGate 是否集成风格检查"""
    print("\n=== 测试 3: QualityGate 集成 ===")
    
    # 读取 quality_gate.py
    qg_path = os.path.join(
        os.path.dirname(__file__),
        "agent", "quality_gate.py"
    )
    
    with open(qg_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = [
        ("导入 AcademicStyleChecker", "from agent.academic_style_checker import AcademicStyleChecker" in content),
        ("调用风格检查", "style_checker.check_style_compliance" in content),
        ("融合评分", "style_score * 0.3" in content or "style_score * 0.3" in content),
    ]
    
    all_passed = True
    for name, result in checks:
        status = "✅" if result else "❌"
        print(f"  {status} {name}")
        if not result:
            all_passed = False
    
    if all_passed:
        print("✅ QualityGate 集成测试通过")
    else:
        print("❌ QualityGate 集成测试失败")
    
    return all_passed


def test_hardcoding_removed():
    """测试 4: latex_converter.py 是否已移除硬编码修复"""
    print("\n=== 测试 4: 硬编码修复移除 ===")
    
    lc_path = os.path.join(
        os.path.dirname(__file__),
        "tools", "latex_converter.py"
    )
    
    with open(lc_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查是否还存在 AI 词汇替换
    has_ai_replacement = bool(re.search(r'ai_word_replacements\s*=\s*\{', content))
    has_long_paren_fix = bool(re.search(r'长括号改为方括号', content))
    
    checks = [
        ("AI 词汇替换已移除", not has_ai_replacement),
        ("长括号转换已移除", not has_long_paren_fix),
        ("有 v9.2 注释说明", "v9.2" in content and "硬编码" in content),
    ]
    
    all_passed = True
    for name, result in checks:
        status = "✅" if result else "❌"
        print(f"  {status} {name}")
        if not result:
            all_passed = False
    
    if all_passed:
        print("✅ 硬编码修复移除测试通过")
    else:
        print("❌ 硬编码修复移除测试失败")
    
    return all_passed


def test_chapter_style_injection():
    """测试 5: 章节生成是否注入风格指南"""
    print("\n=== 测试 5: 章节风格指南注入 ===")
    
    chapters_to_check = [
        ("ch1_introduction.py", "agent/skill_orchestrators"),
        ("ch3_methodology.py", "agent/skill_orchestrators"),
    ]
    
    all_passed = True
    for filename, subdir in chapters_to_check:
        filepath = os.path.join(
            os.path.dirname(__file__),
            subdir,
            filename
        )
        
        if not os.path.exists(filepath):
            print(f"  ⚠️  文件不存在: {filename}")
            continue
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        has_style_guide_load = "academic_writing_style" in content and "style_guide.md" in content
        has_ai_word_warning = "AI 风格词汇" in content or "revolutionize" in content
        
        status = "✅" if has_style_guide_load else "❌"
        print(f"  {status} {filename}: 风格指南加载={'✅' if has_style_guide_load else '❌'}")
        
        if not has_style_guide_load:
            all_passed = False
    
    if all_passed:
        print("✅ 章节风格指南注入测试通过")
    else:
        print("❌ 章节风格指南注入测试失败")
    
    return all_passed


def main():
    print("=" * 60)
    print("  v9.2 柔性引导 + 硬约束系统测试")
    print("=" * 60)
    
    results = []
    
    results.append(("风格指南加载", test_style_guide_loaded()))
    results.append(("学术风格检查器", test_academic_style_checker()))
    results.append(("QualityGate 集成", test_quality_gate_integration()))
    results.append(("硬编码修复移除", test_hardcoding_removed()))
    results.append(("章节风格指南注入", test_chapter_style_injection()))
    
    print("\n" + "=" * 60)
    print("  测试结果汇总")
    print("=" * 60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {status}: {name}")
    
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！柔性引导 + 硬约束系统已就绪")
        return 0
    else:
        print(f"\n⚠️  有 {total - passed} 个测试失败，请检查")
        return 1


if __name__ == "__main__":
    sys.exit(main())
