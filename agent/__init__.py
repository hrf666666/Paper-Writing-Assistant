# -*- coding: utf-8 -*-
"""
Agent模块 - 自主循环架构核心组件
实现 THINK → EXECUTE → REFLECT 闭环
"""

from agent.api_client import UnifiedAPIClient
from agent.memory import MemoryManager
from agent.checkpoint import CheckpointManager
from agent.quality_gate import QualityGate
from agent.human_directive import HumanDirective
from agent.dispatcher import AgentDispatcher
from agent.loop import ResearchLoop
