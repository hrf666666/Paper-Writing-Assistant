# -*- coding: utf-8 -*-
"""
Skill注册与加载引擎

设计参考 auto-deep-researcher-24x7 的 Skill 系统：
- 每个 Skill 是一个独立目录，包含 SKILL.yaml 配置
- 配置驱动的注册、发现、调度
- Skill 分为三类：generator（内容生成）、analyzer（内容分析）、tool（工具类）

与硬编码的区别：
- 旧方式：每个Skill是一个Python文件，prompt硬编码在代码中
- 新方式：Skill配置在YAML中，prompt模板在外部文件，Python代码只负责逻辑编排
"""

import os
import yaml
import logging
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Skill基目录
SKILLS_DIR = Path(__file__).parent.parent / "skills"


@dataclass
class SkillConfig:
    """Skill配置数据类"""
    name: str
    description: str
    type: str  # generator | analyzer | tool | strategy
    version: str = "1.0"
    
    # 触发条件
    triggers: List[str] = field(default_factory=list)
    
    # 依赖的其他Skill
    dependencies: List[str] = field(default_factory=list)
    
    # 输入输出定义
    inputs: List[Dict] = field(default_factory=list)
    outputs: List[Dict] = field(default_factory=list)
    
    # 执行参数
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    # Prompt模板路径（相对于Skill目录）
    prompt_template: str = ""
    
    # 模型要求
    model_type: str = "generation"  # generation | reasoning | light
    
    # 质量门控
    quality_check: bool = True
    quality_threshold: float = 60.0
    max_retries: int = 2
    
    # Skill目录路径
    skill_dir: str = ""
    
    # 原始YAML配置
    raw_config: Dict = field(default_factory=dict)


class SkillRegistry:
    """
    Skill注册与发现引擎
    
    负责：
    1. 从 skills/ 目录自动发现和注册所有Skill
    2. 解析 SKILL.yaml 配置
    3. 提供Skill查询和获取接口
    4. 验证Skill依赖关系
    """
    
    def __init__(self, skills_dir: str = None):
        self.skills_dir = Path(skills_dir) if skills_dir else SKILLS_DIR
        self._skills: Dict[str, SkillConfig] = {}
        self._load_all_skills()
    
    def _load_all_skills(self):
        """自动发现并加载所有Skill"""
        if not self.skills_dir.exists():
            logger.warning(f"Skill目录不存在: {self.skills_dir}")
            return
        
        for item in self.skills_dir.iterdir():
            if item.is_dir():
                skill_file = item / "SKILL.yaml"
                if skill_file.exists():
                    try:
                        config = self._load_skill_yaml(skill_file)
                        self._skills[config.name] = config
                        logger.debug(f"注册Skill: {config.name} ({config.type})")
                    except Exception as e:
                        logger.error(f"加载Skill失败 {item.name}: {e}")
        
        # 验证依赖关系
        self._validate_dependencies()
        
        logger.info(f"Skill注册完成: 共 {len(self._skills)} 个Skill")
    
    def _load_skill_yaml(self, yaml_path: Path) -> SkillConfig:
        """加载并解析SKILL.yaml"""
        with open(yaml_path, 'r', encoding='utf-8') as f:
            raw = yaml.safe_load(f) or {}
        
        return SkillConfig(
            name=raw.get("name", yaml_path.parent.name),
            description=raw.get("description", ""),
            type=raw.get("type", "generator"),
            version=raw.get("version", "1.0"),
            triggers=raw.get("triggers", []),
            dependencies=raw.get("dependencies", []),
            inputs=raw.get("inputs", []),
            outputs=raw.get("outputs", []),
            parameters=raw.get("parameters", {}),
            prompt_template=raw.get("prompt_template", "prompt.md"),
            model_type=raw.get("model_type", "generation"),
            quality_check=raw.get("quality_check", True),
            quality_threshold=raw.get("quality_threshold", 60.0),
            max_retries=raw.get("max_retries", 2),
            skill_dir=str(yaml_path.parent),
            raw_config=raw,
        )
    
    def _validate_dependencies(self):
        """验证所有Skill的依赖关系是否满足"""
        for name, config in self._skills.items():
            for dep in config.dependencies:
                if dep not in self._skills:
                    logger.warning(f"Skill '{name}' 依赖 '{dep}' 未注册")
    
    def get_skill(self, name: str) -> Optional[SkillConfig]:
        """获取指定Skill的配置"""
        return self._skills.get(name)
    
    def get_skills_by_type(self, skill_type: str) -> List[SkillConfig]:
        """获取指定类型的所有Skill"""
        return [s for s in self._skills.values() if s.type == skill_type]
    
    def get_all_skills(self) -> Dict[str, SkillConfig]:
        """获取所有注册的Skill"""
        return self._skills.copy()
    
    def get_skill_prompt(self, name: str) -> str:
        """获取Skill的prompt模板内容"""
        config = self.get_skill(name)
        if not config:
            raise ValueError(f"Skill '{name}' 未注册")
        
        # strategy/analyzer类Skill可能没有prompt模板
        if not config.prompt_template:
            return ""
        
        prompt_path = Path(config.skill_dir) / config.prompt_template
        
        # 检查是否为有效文件路径（排除目录、空路径等）
        if not prompt_path.is_file():
            # 尝试 .md 扩展名
            prompt_path_md = Path(config.skill_dir) / (config.prompt_template + ".md")
            if prompt_path_md.is_file():
                prompt_path = prompt_path_md
            else:
                logger.debug(f"Skill '{name}' 无prompt模板文件")
                return ""
        
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def get_generation_skills(self) -> List[SkillConfig]:
        """获取所有内容生成类Skill"""
        return self.get_skills_by_type("generator")
    
    def get_analyzer_skills(self) -> List[SkillConfig]:
        """获取所有分析类Skill"""
        return self.get_skills_by_type("analyzer")
    
    def get_strategy_skills(self) -> List[SkillConfig]:
        """获取所有策略类Skill"""
        return self.get_skills_by_type("strategy")


# 全局单例
_default_registry: Optional[SkillRegistry] = None
_registry_lock = threading.Lock()


def get_skill_registry() -> SkillRegistry:
    """获取全局Skill注册表单例（线程安全）"""
    global _default_registry
    if _default_registry is None:
        with _registry_lock:
            if _default_registry is None:
                _default_registry = SkillRegistry()
    return _default_registry
