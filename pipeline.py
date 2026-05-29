#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=================================================================
 论文范文写作助手 v9.0 - LaTeX 直出 + 溢出自愈里程碑
=================================================================

核心升级（v9.0 相比 v8.0）：
1. LaTeX 直出生成 — 分章节直接输出 LaTeX（不走 Markdown 中间格式）
2. 5层溢出自愈闭环 — 编译→检测 Overfull→自动修复→重编译→验证
3. 完整论文输出 — 摘要+关键词+5章正文+BibTeX，0溢出0编译错误
4. 有序门控流水线 — P0格式→P1一致性→P2写作质量
5. 章节级状态机 — outline→draft→review→revision→final
6. ToolTrace 反捏造 — 追踪工具调用，验证引用真实性

使用方法：
  1. 编辑 config/project_config.py 配置输入参数
  2. 运行: python pipeline.py
  3. 查看输出: output/ 目录
  4. 运行中干预: 编辑 output/HUMAN_DIRECTIVE.md

架构：
  pipeline.py                  - 主入口
  agent/loop.py                - 自主循环引擎（核心）
  agent/skill_orchestrators/   - 多步编排器（替代旧 skills/*.py）
  agent/api_client.py          - 统一API客户端
  agent/skill_registry.py      - Skill注册与发现
  agent/skill_executor.py      - Skill执行引擎
  agent/quality_gate.py        - 质量门控
  config/venue_profiles/       - 11个期刊/会议场景配置
  skills/                      - 声明式 SKILL.yaml + prompt.md
=================================================================
"""

import sys
import argparse


def main():
    """主入口"""
    parser = argparse.ArgumentParser(description="论文范文写作助手 v9.0")
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
