# -*- coding: utf-8 -*-
"""
学术风格检查器 - 硬约束二次评价机制

功能：
1. AI 风格词汇检测（检测顶刊禁用词汇）
2. 括号长度检查（单括号内超过 20 词视为不规范）
3. 破折号滥用检测
4. 句子长度分布检查（理想 20-30 词）
5. 段落 TEEL 结构验证
6. 时态一致性检查（按章节）
7. 引用格式规范性检查

使用方式：
- 在 QualityGate.evaluate() 中调用
- 作为 VERIFY 阶段的补充检查
- 生成风格合规评分和修改建议
"""

import re
import logging
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)


class AcademicStyleChecker:
    """
    学术风格合规性检查器
    
    执行二次评价，确保 AI 生成的内容符合顶刊写作风格
    支持 P1-P5 优先级规则系统
    """
    
    # === 禁用 AI 风格词汇 ===
    AI_FLAVORED_WORDS = {
        # 过度夸张词汇
        "revolutionize": "transform / advance",
        "groundbreaking": "novel / innovative",
        "unprecedented": "significant / notable",
        "remarkable": "notable / considerable",
        "remarkably": "significantly / substantially",
        "tremendous": "substantial / significant",
        "crucial": "important / essential",
        "vital": "important / necessary",
        "pivotal": "important / key",
        "fundamentally": "significantly / substantially",
        "drastically": "significantly / considerably",
        # 口语化词汇
        "a lot of": "numerous / many / substantial",
        "lots of": "numerous / many",
        "big": "significant / substantial / large",
        "huge": "substantial / significant / large",
        "really": "significantly / notably",
        "very": "highly / significantly / notably",
        # AI 套路词汇
        "delve": "examine / investigate",
        "dive into": "examine / analyze",
        "tapestry": "complex / diverse",
        "testament": "evidence / indication",
        "landscape": "field / domain",
        "realm": "field / domain",
        "foster": "promote / encourage",
        "harness": "utilize / leverage",
        "navigate": "address / handle",
        "embark": "begin / start",
    }
    
    # === P5 清理规则（始终删除的句式）===
    ALWAYS_REMOVE_PATTERNS = [
        # 空洞意图声明
        (r'\bthis paper explores\b', '直接陈述发现，而非意图'),
        (r'\bin this study,? we aim to\b', '陈述为事实："We propose X that achieves Y"'),
        (r'\bwe aim to\b', '陈述为具体贡献，而非意图'),
        
        # 填充词
        (r'\bit is worth noting that\b', '直接陈述事实'),
        (r'\bit should be noted that\b', '直接陈述事实'),
        (r'\bit is important to note that\b', '直接陈述事实'),
        
        # 空洞连接词（作为段落开头且无实质内容）
        (r'^Furthermore,?\s+', '使用结构性过渡或省略'),
        (r'^Moreover,?\s+', '使用结构性过渡或省略'),
        (r'^Additionally,?\s+', '使用结构性过渡或省略'),
        
        # 空洞贡献声明
        (r'\bcontributes to the growing literature on\b', '具体说明贡献内容'),
        (r'\bour results highlight the importance of\b', '陈述具体结果'),
        (r'\btaken together,? these findings suggest\b', '直接陈述含义'),
        (r'\bfuture research should explore\b', '提出具体研究方向'),
        
        # 无法验证的声明
        (r'\bto the best of our knowledge\b', '省略或直接陈述'),
        (r'\bthis is the first study to\b', '"Unlike prior work, we..."'),
        
        # ML/CV/NLP 专用禁止句式
        (r'\bwe propose a novel\b', '省略 "novel"，直接描述方法'),
        (r'\bstate-of-the-art performance\b', '让数据说话，而非自述'),
        (r'\bour method is simple yet effective\b', '描述具体设计选择'),
        (r'\bextensive experiments demonstrate\b', '"Experiments on X datasets show..."'),
        (r'\bwe leave .+ for future work\b', '提出具体未来方向'),
    ]
    
    # 学术推荐词汇（正面引导）
    ACADEMIC_PREFERRED = {
        # 动词
        "propose", "present", "demonstrate", "achieve", "obtain",
        "investigate", "analyze", "evaluate", "verify", "validate",
        "implement", "construct", "design", "develop", "optimize",
        "introduce", "formulate", "derive", "establish", "confirm",
        # 形容词
        "significant", "substantial", "notable", "considerable",
        "effective", "efficient", "robust", "superior", "competitive",
        "comprehensive", "systematic", "rigorous", "accurate", "precise",
        # 连接词
        "furthermore", "moreover", "consequently", "therefore",
        "however", "nevertheless", "additionally", "specifically",
        "particularly", "notably", "respectively", "correspondingly",
    }
    
    # 章节时态规范
    CHAPTER_TENSE_RULES = {
        "Introduction": {
            "present": ["propose", "present", "address", "solve"],  # 本文工作用现在时
            "past": ["proposed", "developed", "introduced"],  # 他人工作用过去时
            "present_perfect": ["have proposed", "have been developed"],  # 领域现状
        },
        "Related Work": {
            "past": ["proposed", "developed", "introduced", "presented"],  # 主要用过去时
            "present_perfect": ["have been proposed", "have attracted"],  # 研究现状
        },
        "Methodology": {
            "present": ["define", "compute", "calculate", "optimize"],  # 方法描述用现在时
        },
        "Experiments": {
            "past": ["achieved", "obtained", "demonstrated", "showed"],  # 实验结果用过去时
            "present": ["shows", "indicates", "demonstrates"],  # 图表说明用现在时
        },
        "Conclusion": {
            "present": ["propose", "present", "achieve"],  # 总结用现在时
            "future": ["will explore", "will investigate"],  # 未来工作
        },
    }
    
    def __init__(self):
        self._compile_patterns()
    
    def _compile_patterns(self):
        """预编译正则表达式"""
        # AI 词汇匹配（不区分大小写）
        self.ai_word_pattern = re.compile(
            r'\b(' + '|'.join(re.escape(w) for w in self.AI_FLAVORED_WORDS.keys()) + r')\b',
            re.IGNORECASE
        )
        
        # 括号内容匹配
        self.parenthesis_pattern = re.compile(r'\(([^)]+)\)')
        
        # 破折号匹配
        self.dash_pattern = re.compile(r'--|—|–')
        
        # 句子分割（简单按句号/问号/感叹号）
        self.sentence_split_pattern = re.compile(r'[.!?]+\s+')
        
        # 段落分割
        self.paragraph_split_pattern = re.compile(r'\n\s*\n')
    
    def check_style_compliance(self, content: str, chapter_name: str = "") -> Dict:
        """
        检查学术风格合规性
        
        Args:
            content: 章节内容
            chapter_name: 章节名称（用于时态检查）
        
        Returns:
            Dict: {
                "passed": bool,
                "score": float,  # 0-100
                "issues": List[Dict],
                "suggestions": List[str],
                "details": Dict  # 各项检查详情
            }
        """
        issues = []
        suggestions = []
        
        # 1. AI 风格词汇检测
        ai_word_issues = self._check_ai_words(content)
        issues.extend(ai_word_issues["issues"])
        if ai_word_issues["count"] > 0:
            suggestions.append(f"替换 {ai_word_issues['count']} 个 AI 风格词汇为学术用语")
        
        # 1.5 P5 清理规则检测（新增）
        p5_issues = self._check_always_remove_patterns(content)
        issues.extend(p5_issues["issues"])
        if p5_issues["count"] > 0:
            suggestions.append(f"重写 {p5_issues['count']} 个 P5 禁止句式")
        
        # 2. 括号长度检查
        paren_issues = self._check_parenthesis_length(content)
        issues.extend(paren_issues["issues"])
        if paren_issues["count"] > 0:
            suggestions.append(f"拆分 {paren_issues['count']} 个过长括号内容（应 <20 词）")
        
        # 3. 破折号滥用检查
        dash_issues = self._check_dash_usage(content)
        issues.extend(dash_issues["issues"])
        if dash_issues["count"] > 3:
            suggestions.append("减少破折号使用（建议全文 <3 个），改用逗号或括号")
        
        # 4. 句子长度检查
        sentence_issues = self._check_sentence_length(content)
        issues.extend(sentence_issues["issues"])
        if sentence_issues["avg_length"] > 35:
            suggestions.append(f"平均句长 {sentence_issues['avg_length']:.0f} 词过长，建议 20-30 词")
        
        # 5. 段落结构检查
        paragraph_issues = self._check_paragraph_structure(content)
        issues.extend(paragraph_issues["issues"])
        
        # 6. 时态一致性检查
        if chapter_name:
            tense_issues = self._check_tense_consistency(content, chapter_name)
            issues.extend(tense_issues["issues"])
        
        # 7. 计算综合评分
        score = self._calculate_score(issues, len(content.split()))
        passed = score >= 75.0 and len([i for i in issues if i["severity"] == "critical"]) == 0
        
        return {
            "passed": passed,
            "score": score,
            "issues": issues,
            "suggestions": suggestions,
            "details": {
                "ai_words": ai_word_issues["count"],
                "p5_patterns": p5_issues["count"],
                "long_parentheses": paren_issues["count"],
                "dashes": dash_issues["count"],
                "avg_sentence_length": sentence_issues["avg_length"],
                "paragraph_count": paragraph_issues["count"],
            }
        }
    
    def _check_ai_words(self, content: str) -> Dict:
        """检测 AI 风格词汇"""
        matches = list(self.ai_word_pattern.finditer(content))
        issues = []
        
        for match in matches:
            word = match.group(0)
            replacement = self.AI_FLAVORED_WORDS.get(word.lower(), "academic alternative")
            issues.append({
                "type": "ai_flavored_word",
                "severity": "warning",
                "word": word,
                "location": match.start(),
                "context": content[max(0, match.start()-30):match.end()+30],
                "suggestion": f'将 "{word}" 替换为 "{replacement}"',
            })
        
        return {
            "count": len(issues),
            "issues": issues,
        }
    
    def _check_always_remove_patterns(self, content: str) -> Dict:
        """
        检测 P5 清理规则（始终删除的句式）
        
        来自 journal-adapt P5 规则和 IEEE Trans 规范
        """
        issues = []
        
        for pattern, suggestion in self.ALWAYS_REMOVE_PATTERNS:
            for match in re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE):
                issues.append({
                    "type": "p5_always_remove",
                    "severity": "warning",
                    "pattern": match.group(0),
                    "location": match.start(),
                    "context": content[max(0, match.start()-40):match.end()+40],
                    "suggestion": suggestion,
                })
        
        return {
            "count": len(issues),
            "issues": issues,
        }
    
    def _check_parenthesis_length(self, content: str) -> Dict:
        """检查括号内容长度"""
        issues = []
        
        for match in self.parenthesis_pattern.finditer(content):
            paren_content = match.group(1)
            word_count = len(paren_content.split())
            
            if word_count > 20:
                issues.append({
                    "type": "long_parenthesis",
                    "severity": "warning",
                    "word_count": word_count,
                    "location": match.start(),
                    "context": match.group(0)[:100],
                    "suggestion": f"括号内 {word_count} 词过长，建议拆分为独立句子或使用逗号/分号",
                })
        
        return {
            "count": len(issues),
            "issues": issues,
        }
    
    def _check_dash_usage(self, content: str) -> Dict:
        """检查破折号使用"""
        issues = []
        
        for match in self.dash_pattern.finditer(content):
            issues.append({
                "type": "dash_usage",
                "severity": "info",
                "location": match.start(),
                "context": content[max(0, match.start()-20):match.end()+20],
                "suggestion": "考虑使用逗号或括号替代破折号",
            })
        
        return {
            "count": len(issues),
            "issues": issues,
        }
    
    def _check_sentence_length(self, content: str) -> Dict:
        """检查句子长度分布"""
        sentences = self.sentence_split_pattern.split(content)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
        
        if not sentences:
            return {"count": 0, "issues": [], "avg_length": 0}
        
        lengths = [len(s.split()) for s in sentences]
        avg_length = sum(lengths) / len(lengths)
        
        issues = []
        long_sentences = [l for l in lengths if l > 40]
        very_long = [l for l in lengths if l > 50]
        
        if len(very_long) > len(sentences) * 0.2:
            issues.append({
                "type": "too_many_long_sentences",
                "severity": "warning",
                "count": len(very_long),
                "total": len(sentences),
                "suggestion": f"{len(very_long)}/{len(sentences)} 句子超过 50 词，建议拆分",
            })
        
        return {
            "count": len(long_sentences),
            "issues": issues,
            "avg_length": avg_length,
            "distribution": {
                "short": len([l for l in lengths if l < 15]),
                "medium": len([l for l in lengths if 15 <= l <= 30]),
                "long": len([l for l in lengths if 30 < l <= 40]),
                "very_long": len(very_long),
            }
        }
    
    def _check_paragraph_structure(self, content: str) -> Dict:
        """检查段落结构（TEEL：Topic-Explanation-Evidence-Link）"""
        paragraphs = self.paragraph_split_pattern.split(content)
        paragraphs = [p.strip() for p in paragraphs if len(p.strip()) > 50]
        
        issues = []
        
        for i, para in enumerate(paragraphs):
            sentences = self.sentence_split_pattern.split(para)
            sentences = [s.strip() for s in sentences if s.strip()]
            
            # 检查段落长度
            if len(sentences) < 3:
                issues.append({
                    "type": "short_paragraph",
                    "severity": "info",
                    "paragraph_index": i,
                    "sentence_count": len(sentences),
                    "suggestion": "段落过短（<3 句），建议扩展或合并",
                })
            elif len(sentences) > 8:
                issues.append({
                    "type": "long_paragraph",
                    "severity": "info",
                    "paragraph_index": i,
                    "sentence_count": len(sentences),
                    "suggestion": "段落过长（>8 句），建议拆分以提高可读性",
                })
        
        return {
            "count": len(paragraphs),
            "issues": issues,
        }
    
    def _check_tense_consistency(self, content: str, chapter_name: str) -> Dict:
        """检查时态一致性"""
        issues = []
        
        if chapter_name not in self.CHAPTER_TENSE_RULES:
            return {"issues": issues}
        
        rules = self.CHAPTER_TENSE_RULES[chapter_name]
        
        # 简单启发式检查
        # Related Work 应该主要用过去时
        if chapter_name == "Related Work":
            past_verbs = rules.get("past", [])
            present_verbs = rules.get("present", [])
            
            past_count = sum(1 for v in past_verbs if v.lower() in content.lower())
            present_count = sum(1 for v in present_verbs if v.lower() in content.lower())
            
            if present_count > past_count * 2:
                issues.append({
                    "type": "tense_inconsistency",
                    "severity": "warning",
                    "chapter": chapter_name,
                    "suggestion": "Related Work 章节应主要使用过去时描述他人工作",
                })
        
        # Methodology 应该主要用现在时
        elif chapter_name == "Methodology":
            present_verbs = rules.get("present", [])
            present_count = sum(1 for v in present_verbs if v.lower() in content.lower())
            
            if present_count == 0:
                issues.append({
                    "type": "tense_inconsistency",
                    "severity": "warning",
                    "chapter": chapter_name,
                    "suggestion": "Methodology 章节应使用现在时描述方法",
                })
        
        return {"issues": issues}
    
    def _calculate_score(self, issues: List[Dict], word_count: int) -> float:
        """
        计算风格合规评分
        
        评分规则：
        - 基础分 100
        - AI 词汇：每个 -3 分
        - P5 禁止句式：每个 -4 分（更严重）
        - 长括号：每个 -2 分
        - 破折号过多（>3）：每个 -1 分
        - 句子过长：-5 分
        - 时态不一致：-10 分
        """
        score = 100.0
        
        for issue in issues:
            if issue["type"] == "ai_flavored_word":
                score -= 3
            elif issue["type"] == "p5_always_remove":
                score -= 4  # P5 规则更严重
            elif issue["type"] == "long_parenthesis":
                score -= 2
            elif issue["type"] == "dash_usage":
                if score > 90:  # 只在分数较高时扣分
                    score -= 1
            elif issue["type"] == "too_many_long_sentences":
                score -= 5
            elif issue["type"] == "tense_inconsistency":
                score -= 10
            elif issue["type"] in ["short_paragraph", "long_paragraph"]:
                score -= 1  # info 级别只扣 1 分
        
        return max(0.0, min(100.0, score))
    
    def generate_style_report(self, content: str, chapter_name: str = "") -> str:
        """
        生成风格检查报告（用于日志）
        
        Args:
            content: 章节内容
            chapter_name: 章节名称
        
        Returns:
            str: 格式化的报告文本
        """
        result = self.check_style_compliance(content, chapter_name)
        
        report_lines = [
            f"=== 学术风格检查报告: {chapter_name or 'Unknown'} ===",
            f"合规评分: {result['score']:.1f}/100 ({'通过' if result['passed'] else '不通过'})",
            f"发现问题: {len(result['issues'])} 个",
        ]
        
        if result["details"]:
            report_lines.append(f"\n详细统计:")
            report_lines.append(f"  AI 风格词汇: {result['details'].get('ai_words', 0)} 个")
            report_lines.append(f"  P5 禁止句式: {result['details'].get('p5_patterns', 0)} 个")
            report_lines.append(f"  过长括号: {result['details'].get('long_parentheses', 0)} 个")
            report_lines.append(f"  破折号: {result['details'].get('dashes', 0)} 个")
            report_lines.append(f"  平均句长: {result['details'].get('avg_sentence_length', 0):.1f} 词")
            report_lines.append(f"  段落数: {result['details'].get('paragraph_count', 0)} 个")
        
        if result["suggestions"]:
            report_lines.append(f"\n修改建议:")
            for i, suggestion in enumerate(result["suggestions"], 1):
                report_lines.append(f"  {i}. {suggestion}")
        
        if result["issues"]:
            report_lines.append(f"\n问题详情:")
            for issue in result["issues"][:10]:  # 最多显示 10 个
                severity_mark = {"critical": "!!", "warning": "!", "info": "-"}.get(
                    issue.get("severity", "info"), "-")
                report_lines.append(
                    f"  [{severity_mark}] {issue['type']}: {issue.get('suggestion', '')}"
                )
        
        return "\n".join(report_lines)


# 便捷函数
def check_academic_style(content: str, chapter_name: str = "") -> Dict:
    """
    便捷函数：检查学术风格
    
    Args:
        content: 章节内容
        chapter_name: 章节名称
    
    Returns:
        Dict: 检查结果
    """
    checker = AcademicStyleChecker()
    return checker.check_style_compliance(content, chapter_name)
