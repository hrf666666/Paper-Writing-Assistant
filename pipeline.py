#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=================================================================
 论文范文写作助手 v6.0 - 全自主循环架构
=================================================================

核心升级（相比v5.0）：
1. 配置驱动 API：统一 OpenAI 兼容接口，多模型自动降级
2. 参考文献池：写作前批量检索真实论文，LLM 从池中引用
3. 全局大纲规划：Content Checklist + 篇幅预算 + 子节推导
4. 引用管理器：统一 <citation> 收集→验证→去重→编号→替换
5. 跨章节一致性检查：术语/数值/格式/引用编号连续性
6. MCP 增强检索：智谱 MCP + Semantic Scholar 双通道验证

使用方法：
  1. 编辑 config/project_config.py 配置输入参数
  2. 运行: python pipeline.py
  3. 查看输出: output/ 目录
  4. 运行中干预: 编辑 output/HUMAN_DIRECTIVE.md

架构：
  agent/loop.py      - 自主循环引擎（核心）
  agent/api_client.py - 统一API客户端
  agent/memory.py    - 双层记忆系统
  agent/checkpoint.py - 检查点管理
  agent/quality_gate.py - 质量门控
  agent/human_directive.py - 人工干预
  agent/dispatcher.py - 任务调度
=================================================================
"""

import sys
import argparse


def main():
    """主入口"""
    parser = argparse.ArgumentParser(description="论文范文写作助手 v6.0")
    parser.add_argument("--no-resume", action="store_true",
                       help="不从检查点恢复，从头开始")
    parser.add_argument("--debug", action="store_true",
                       help="启用调试日志")
    parser.add_argument("--title", type=str, default=None,
                       help="覆盖论文标题（默认使用 project_config.PAPER_TITLE）")
    parser.add_argument("--output", type=str, default=None,
                       help="覆盖输出目录（默认使用 project_config.OUTPUT_DIR）")
    parser.add_argument("--code-path", type=str, default=None,
                       help="覆盖项目代码路径（默认使用 project_config.PROJECT_CODE_PATH）")
    args = parser.parse_args()

    # 命令行参数覆盖配置
    if args.title or args.output or args.code_path:
        import config.project_config as pc
        if args.title:
            pc.PAPER_TITLE = args.title
        if args.output:
            pc.OUTPUT_DIR = args.output
        if args.code_path:
            pc.PROJECT_CODE_PATH = args.code_path

    # 配置日志
    import logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    from agent.loop import ResearchLoop
    loop = ResearchLoop()
    loop.run(resume=not args.no_resume)


if __name__ == "__main__":
    main()
