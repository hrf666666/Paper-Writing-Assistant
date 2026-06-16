# -*- coding: utf-8 -*-
"""
Skill执行引擎

负责：
1. 根据SkillConfig执行Skill
2. 模板渲染（将变量注入prompt模板）
3. 调用API生成内容
4. 质量门控
5. 结果后处理
"""

import os
import re
import json
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

from agent.skill_registry import SkillConfig, get_skill_registry
from agent.api_client import get_api_client, UnifiedAPIClient
from agent.quality_gate import QualityGate

logger = logging.getLogger(__name__)


class SkillExecutor:
    """
    Skill执行引擎
    
    执行流程：
    1. 加载prompt模板
    2. 渲染模板（注入变量）
    3. 调用API生成内容
    4. 质量门控评估
    5. 自动重试（如未达标）
    6. 返回结果
    """
    
    def __init__(self, api_client: UnifiedAPIClient = None, quality_gate: QualityGate = None):
        self.api_client = api_client or get_api_client()
        self.quality_gate = quality_gate or QualityGate(self.api_client)
        self.registry = get_skill_registry()
        self._execution_log: List[Dict] = []
    
    def execute(self, skill_name: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行指定Skill
        
        Args:
            skill_name: Skill名称
            context: 执行上下文变量
            
        Returns:
            Dict: 执行结果
        """
        config = self.registry.get_skill(skill_name)
        if not config:
            raise ValueError(f"Skill '{skill_name}' 未注册")
        
        logger.info(f"执行Skill: {skill_name} (type={config.type})")
        
        # 自动注入论文等级约束（如果context中未提供）
        if "tier_constraint" not in context:
            from config.project_config import get_tier_prompt_block
            context["tier_constraint"] = get_tier_prompt_block()
        
        # 自动注入ref_pdf行文风格（如果context中有style_guide但未注入风格指令）
        if "style_guide" in context and isinstance(context["style_guide"], dict) and "ref_style_instruction" not in context:
            style_guide = context["style_guide"]
            style_parts = []
            vocab = style_guide.get("用词特征", [])
            if vocab:
                style_parts.append(f"参考论文学术用词: {vocab[:20]}")
            citation = style_guide.get("引用风格", {})
            if citation:
                style_parts.append(f"参考论文引用风格: {json.dumps(citation, ensure_ascii=False)[:300]}")
            patterns = style_guide.get("句式特征", {})
            if patterns:
                style_parts.append(f"参考论文句式特征: {json.dumps(patterns, ensure_ascii=False)[:500]}")
            if style_parts:
                context["ref_style_instruction"] = "\n".join(style_parts)
        
        # 1. 加载prompt模板
        prompt_template = self.registry.get_skill_prompt(skill_name)
        
        # 2. 渲染模板
        rendered_prompt = self._render_template(prompt_template, context)
        
        # 3. 调用API
        result = self._call_api(rendered_prompt, config)
        
        # 4. 后处理
        processed_result = self._post_process(result, config, context)
        
        # 5. 记录执行日志
        log_entry = {
            "skill": skill_name,
            "type": config.type,
            "input_chars": len(rendered_prompt),
            "output_chars": len(processed_result) if isinstance(processed_result, str) else 0,
        }
        self._execution_log.append(log_entry)
        
        return {
            "content": processed_result,
            "skill": skill_name,
            "config": config,
            "log": log_entry,
        }
    
    def execute_with_quality(self, skill_name: str, context: Dict[str, Any],
                             style_guide: Dict = None, chapter_org: Dict = None,
                             previous_content: str = "") -> Dict[str, Any]:
        """
        执行Skill并带质量门控
        
        如果质量不达标，自动重试
        """
        config = self.registry.get_skill(skill_name)
        if not config:
            raise ValueError(f"Skill '{skill_name}' 未注册")
        
        max_retries = config.max_retries
        
        for attempt in range(max_retries + 1):
            # 执行Skill
            exec_result = self.execute(skill_name, context)
            content = exec_result["content"]
            
            if not config.quality_check or attempt == max_retries:
                # 无需质量检查或最后一次尝试
                return exec_result
            
            # 质量门控
            try:
                revised_content, report = self.quality_gate.evaluate_and_revise(
                    chapter_name=config.name,
                    chapter_content=content,
                    style_guide=style_guide or {},
                    chapter_org=chapter_org or {},
                    previous_content=previous_content,
                )
                
                if report.overall_score >= config.quality_threshold:
                    logger.info(f"Skill '{skill_name}' 质量达标: {report.overall_score:.1f}")
                    exec_result["content"] = revised_content
                    exec_result["quality_score"] = report.overall_score
                    return exec_result
                else:
                    logger.warning(
                        f"Skill '{skill_name}' 质量未达标 "
                        f"({report.overall_score:.1f} < {config.quality_threshold}), "
                        f"重试 {attempt + 1}/{max_retries}"
                    )
                    # 将质量报告注入上下文以改进下一轮
                    context["quality_feedback"] = report.to_dict()
                    
            except Exception as e:
                logger.error(f"质量门控异常: {e}")
                return exec_result
        
        return exec_result
    
    def _render_template(self, template: str, context: Dict[str, Any]) -> str:
        """
        渲染prompt模板
        
        支持 {{variable}} 语法
        支持 {% if condition %}...{% endif %} 条件语法
        支持 {% for item in list %}...{% endfor %} 循环语法
        """
        if not template:
            return ""
        
        result = template
        
        # 简单变量替换 {{var}}
        for key, value in context.items():
            placeholder = "{{" + key + "}}"
            if placeholder in result:
                if isinstance(value, (dict, list)):
                    str_value = json.dumps(value, ensure_ascii=False, indent=2)
                else:
                    str_value = str(value)
                # 防注入：清理替换值中可能干扰模板的标记
                str_value = str_value.replace("{{", "").replace("}}", "")
                result = result.replace(placeholder, str_value)
        
        # 条件语法 {% if condition %}...{% endif %}
        def replace_conditional(match):
            condition_var = match.group(1).strip()
            content = match.group(2)
            if condition_var in context and context[condition_var]:
                return content
            return ""
        
        result = re.sub(
            r'\{%\s*if\s+(\w+)\s*%\}(.*?)\{%\s*endif\s*%\}',
            replace_conditional,
            result,
            flags=re.DOTALL
        )
        
        return result
    
    def _call_api(self, prompt: str, config: SkillConfig) -> str:
        """根据Skill配置调用API"""
        if config.model_type == "generation":
            return self.api_client.call_generation(prompt)
        elif config.model_type == "reasoning":
            return self.api_client.call_reasoning(prompt)
        elif config.model_type == "light":
            return self.api_client.call_light(prompt)
        else:
            return self.api_client.call_generation(prompt)
    
    def _post_process(self, content: str, config: SkillConfig, 
                      context: Dict[str, Any]) -> str:
        """
        后处理生成内容
        
        - 清理多余空白
        - 处理特殊标记
        - 应用Skill特定的后处理逻辑
        """
        if not isinstance(content, str):
            return content
        
        # 清理多余空白
        content = re.sub(r'\n{4,}', '\n\n\n', content)
        
        # 应用Skill参数中的后处理规则
        params = config.parameters
        if params.get("strip_prefix"):
            prefix = params["strip_prefix"]
            if content.startswith(prefix):
                content = content[len(prefix):].lstrip()
        
        if params.get("ensure_heading"):
            heading = params["ensure_heading"]
            # 检查内容是否已包含该标题（避免重复添加）
            heading_stripped = heading.lstrip('#').strip()
            if not re.search(r'^#+\s+' + re.escape(heading_stripped), content, re.MULTILINE):
                content = heading + "\n\n" + content
        
        return content.strip()
    
    def get_execution_log(self) -> List[Dict]:
        """获取执行日志"""
        return self._execution_log.copy()
