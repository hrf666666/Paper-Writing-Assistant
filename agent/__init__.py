# -*- coding: utf-8 -*-
"""
Agent 模块 - 自主循环架构核心组件
实现 THINK → EXECUTE → REFLECT 闭环

子模块：
  api_client.py           - 统一 LLM API 客户端（OpenAI 系 + Anthropic 系）
  loop.py                 - 自主循环引擎（核心调度）
  dispatcher.py           - 任务调度器
  memory.py               - 双层记忆系统
  checkpoint.py           - 检查点管理
  quality_gate.py         - 质量门控
  human_directive.py      - 人工干预接口
  auditor.py              - 反幻觉审计
  skill_registry.py       - Skill 注册与发现引擎
  skill_executor.py       - Skill 执行引擎
  venue_adapter.py        - Venue 配置适配器
  motivation_engine.py    - v7.0 动机驱动写作
  exemplar_learner.py     - v7.0 深度范例学习
  rationale_matrix.py     - v7.0 写作理由矩阵
  closed_book_rewriter.py - v7.0 闭卷重写
  seven_anchor_test.py    - v7.0 七锚测试
  multi_reviewer.py       - v7.0 多代理审阅
  skill_orchestrators/    - 多步编排器（替代旧 skills/*.py）
"""

from agent.api_client import UnifiedAPIClient
from agent.memory import MemoryManager
from agent.checkpoint import CheckpointManager
from agent.quality_gate import QualityGate
from agent.human_directive import HumanDirective
from agent.dispatcher import AgentDispatcher
from agent.loop import ResearchLoop
