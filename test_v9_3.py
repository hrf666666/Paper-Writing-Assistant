# -*- coding: utf-8 -*-
"""
v9.3 journal-adapt 集成测试

测试内容：
1. IEEE Trans 风格配置文件加载
2. AcademicStyleChecker P5 规则检测
3. Chapter orchestrators 风格注入
4. 完整风格检查流程
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, '/home/bigboss/code/paper-writing-assistant')

def test_ieee_trans_style_profile():
    """测试 1: IEEE Trans 风格配置文件加载"""
    print("\n=== 测试 1: IEEE Trans 风格配置文件加载 ===")
    
    try:
        from config.ieee_trans_style_profile import (
            get_ieee_trans_style_profile,
            get_section_requirements,
            get_red_flags,
            get_language_style,
        )
        
        profile = get_ieee_trans_style_profile()
        assert 'journal_meta' in profile
        assert 'editorial_identity' in profile
        assert 'introduction_conventions' in profile
        assert 'section_requirements' in profile
        
        # 测试章节要求
        intro_req = get_section_requirements("Introduction")
        assert 'structure' in intro_req
        assert 'contributions' in intro_req
        
        method_req = get_section_requirements("Method")
        assert 'entry' in method_req
        assert 'required' in method_req
        
        exp_req = get_section_requirements("Experiments")
        assert 'structure' in exp_req
        assert 'setup_must_include' in exp_req
        
        # 测试 Red Flags
        red_flags = get_red_flags()
        assert len(red_flags) > 0
        assert any("revolutionized" in flag.lower() for flag in red_flags)
        
        # 测试语言风格
        lang = get_language_style()
        assert 'voice' in lang
        assert 'sentence_length' in lang
        
        print("✅ 测试 1 通过: IEEE Trans 风格配置文件加载成功")
        print(f"   - 期刊: {profile['journal_meta']['name']}")
        print(f"   - Red Flags: {len(red_flags)} 个")
        print(f"   - 章节要求: {list(profile['section_requirements'].keys())}")
        return True
        
    except Exception as e:
        print(f"❌ 测试 1 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_p5_cleanup_rules():
    """测试 2: AcademicStyleChecker P5 清理规则检测"""
    print("\n=== 测试 2: P5 清理规则检测 ===")
    
    try:
        from agent.academic_style_checker import AcademicStyleChecker
        
        checker = AcademicStyleChecker()
        
        # 测试包含 P5 禁止句式的文本
        test_content = """
This paper explores the depth estimation problem. 
It is worth noting that our method achieves better results.
Furthermore, we demonstrate the effectiveness.
Our results highlight the importance of careful design.
To the best of our knowledge, this is the first study to address this.
We propose a novel architecture that significantly improves performance.
"""
        
        result = checker.check_style_compliance(test_content, "Introduction")
        
        # 应该检测到多个 P5 违规
        p5_issues = [i for i in result['issues'] if i['type'] == 'p5_always_remove']
        assert len(p5_issues) >= 5, f"应检测到至少 5 个 P5 违规，实际: {len(p5_issues)}"
        
        # 评分应该较低
        assert result['score'] < 80, f"P5 违规较多时评分应较低，实际: {result['score']}"
        
        print("✅ 测试 2 通过: P5 清理规则检测正常")
        print(f"   - 检测到 P5 违规: {len(p5_issues)} 个")
        print(f"   - 风格评分: {result['score']:.1f}/100")
        print(f"   - 问题列表: {len(result['issues'])} 个")
        return True
        
    except Exception as e:
        print(f"❌ 测试 2 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_chapter_orchestrator_injection():
    """测试 3: Chapter orchestrators 风格注入"""
    print("\n=== 测试 3: Chapter orchestrators 风格注入 ===")
    
    try:
        # 测试 ch1_introduction
        from agent.skill_orchestrators.ch1_introduction import _build_style_instruction as ch1_build
        ch1_instruction = ch1_build({}, {})
        assert "IEEE Transactions 期刊特定规则" in ch1_instruction
        assert "Introduction 结构要求" in ch1_instruction
        assert "Red Flags" in ch1_instruction
        print("✅ ch1_introduction 风格注入成功")
        
        # 测试 ch2_related_work
        from agent.skill_orchestrators.ch2_related_work import _build_style_instruction as ch2_build
        ch2_instruction = ch2_build({}, {}, is_related_work=True)
        assert "IEEE Transactions 期刊特定规则" in ch2_instruction
        assert "Related Work 结构要求" in ch2_instruction
        print("✅ ch2_related_work 风格注入成功")
        
        # 测试 ch3_methodology
        from agent.skill_orchestrators.ch3_methodology import _build_style_instruction as ch3_build
        ch3_instruction = ch3_build({}, {})
        assert "IEEE Transactions 期刊特定规则" in ch3_instruction
        assert "Method 结构要求" in ch3_instruction
        print("✅ ch3_methodology 风格注入成功")
        
        # 测试 ch4_experiments
        from agent.skill_orchestrators.ch4_experiments import _build_style_instruction as ch4_build
        ch4_instruction = ch4_build({}, {})
        assert "IEEE Transactions 期刊特定规则" in ch4_instruction
        assert "Experiments 结构要求" in ch4_instruction
        print("✅ ch4_experiments 风格注入成功")
        
        # 测试 ch5_conclusion (通过读取文件检查)
        ch5_path = '/home/bigboss/code/paper-writing-assistant/agent/skill_orchestrators/ch5_conclusion.py'
        with open(ch5_path, 'r', encoding='utf-8') as f:
            ch5_content = f.read()
        assert "ieee_trans_style_profile" in ch5_content
        assert "IEEE Transactions 期刊特定规则" in ch5_content
        print("✅ ch5_conclusion 风格注入成功")
        
        print("\n✅ 测试 3 通过: 所有 chapter orchestrators 风格注入成功")
        return True
        
    except Exception as e:
        print(f"❌ 测试 3 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_style_guide_updated():
    """测试 4: style_guide.md 包含 ml_cv_nlp 规则"""
    print("\n=== 测试 4: style_guide.md 更新验证 ===")
    
    try:
        style_guide_path = '/home/bigboss/code/paper-writing-assistant/skills/academic_writing_style/style_guide.md'
        with open(style_guide_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查 P5 清理规则
        assert "P5 清理规则" in content or "Always Remove Patterns" in content
        assert "This paper explores..." in content
        assert "We propose a novel..." in content
        assert "State-of-the-art performance" in content
        
        # 检查 ML/CV/NLP 专用规范
        assert "ML/CV/NLP 专用规范" in content
        assert "Abstract 规范" in content
        assert "Experiments 规范" in content
        
        print("✅ 测试 4 通过: style_guide.md 已更新")
        print(f"   - 包含 P5 清理规则")
        print(f"   - 包含 ML/CV/NLP 专用规范")
        return True
        
    except Exception as e:
        print(f"❌ 测试 4 失败: {e}")
        return False


def test_full_style_check_pipeline():
    """测试 5: 完整风格检查流程"""
    print("\n=== 测试 5: 完整风格检查流程 ===")
    
    try:
        from agent.academic_style_checker import AcademicStyleChecker
        
        checker = AcademicStyleChecker()
        
        # 测试高质量学术文本
        good_content = """
We propose a depth estimation method that leverages multi-scale feature fusion. 
The architecture consists of three modules: feature extraction, depth prediction, and refinement.
Experiments on NYU Depth v2 and KITTI datasets demonstrate the effectiveness of our approach.
Our method achieves 15% improvement in RMSE compared to baseline methods.
The ablation study confirms that each component contributes to the final performance.
"""
        
        good_result = checker.check_style_compliance(good_content, "Methodology")
        print(f"高质量文本评分: {good_result['score']:.1f}/100")
        assert good_result['score'] >= 85, f"高质量文本评分应 >= 85，实际: {good_result['score']}"
        
        # 测试低质量文本（包含多个违规）
        bad_content = """
Deep learning has revolutionized the field. This paper explores a novel approach.
It is worth noting that our method is groundbreaking and remarkably effective.
Furthermore, we demonstrate unprecedented results. To the best of our knowledge, 
this is the first study to address this crucial problem. Our results highlight 
the importance of this game-changing technology.
"""
        
        bad_result = checker.check_style_compliance(bad_content, "Introduction")
        print(f"低质量文本评分: {bad_result['score']:.1f}/100")
        assert bad_result['score'] < 70, f"低质量文本评分应 < 70，实际: {bad_result['score']}"
        
        # 检查详细统计
        assert 'p5_patterns' in bad_result['details']
        assert 'ai_words' in bad_result['details']
        
        print("✅ 测试 5 通过: 完整风格检查流程正常")
        print(f"   - 高质量文本: {good_result['score']:.1f}/100 (通过: {good_result['passed']})")
        print(f"   - 低质量文本: {bad_result['score']:.1f}/100 (通过: {bad_result['passed']})")
        print(f"   - AI 词汇: {bad_result['details']['ai_words']} 个")
        print(f"   - P5 违规: {bad_result['details']['p5_patterns']} 个")
        return True
        
    except Exception as e:
        print(f"❌ 测试 5 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("v9.3 journal-adapt 集成测试")
    print("=" * 60)
    
    tests = [
        test_ieee_trans_style_profile,
        test_p5_cleanup_rules,
        test_chapter_orchestrator_injection,
        test_style_guide_updated,
        test_full_style_check_pipeline,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        if test():
            passed += 1
        else:
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"测试结果: {passed}/{len(tests)} 通过")
    print("=" * 60)
    
    if failed == 0:
        print("\n✅ 所有测试通过！journal-adapt 集成成功！")
    else:
        print(f"\n❌ {failed} 个测试失败，请检查错误信息")
        sys.exit(1)
