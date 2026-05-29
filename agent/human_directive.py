# -*- coding: utf-8 -*-
"""
人工干预机制 - 运行中通过文件干预Agent方向

设计参考 auto-deep-researcher 的 HUMAN_DIRECTIVE.md：
- 用户可在运行中创建指令文件干预Agent行为
- Agent在每次循环开始时检查是否有新指令
- 支持暂停、修改方向、跳过阶段等操作
"""

import os
import json
import time
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict, field

from config.project_config import OUTPUT_DIR

logger = logging.getLogger(__name__)


DIRECTIVE_FILE = "HUMAN_DIRECTIVE.md"
ACK_FILE = "HUMAN_DIRECTIVE_ACK.md"


@dataclass
class HumanDirective:
    """
    人工指令

    用户通过在 output/ 目录下创建 HUMAN_DIRECTIVE.md 文件来干预Agent行为。
    支持的指令格式：
    ```
    # 指令类型
    ## PAUSE
    暂停原因

    ## SKIP: phase_name
    跳过原因

    ## REDO: phase_name
    重做原因

    ## ADJUST: strategy_description
    调整方向描述

    ## STOP
    停止原因
    ```
    """
    directive_type: str   # "PAUSE" | "SKIP" | "REDO" | "ADJUST" | "STOP" | "RESUME"
    target: str = ""      # 目标阶段名
    reason: str = ""      # 原因
    content: str = ""     # 附加内容
    timestamp: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


class DirectiveManager:
    """
    人工指令管理器

    工作方式：
    1. 用户在 output/ 目录下创建 HUMAN_DIRECTIVE.md
    2. Agent 在每次循环开始时调用 check() 检查
    3. Agent 执行指令后写入 HUMAN_DIRECTIVE_ACK.md 确认
    4. 执行完毕后删除或清空 HUMAN_DIRECTIVE.md
    """

    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or OUTPUT_DIR
        self._last_check_time = 0.0
        self._pending: List[HumanDirective] = []
        self._processed: List[HumanDirective] = []

    def check(self) -> List[HumanDirective]:
        """
        检查是否有新的人工指令

        Returns:
            List[HumanDirective]: 待处理的指令列表
        """
        directive_path = os.path.join(self.output_dir, DIRECTIVE_FILE)

        if not os.path.exists(directive_path):
            return []

        # 检查文件修改时间
        mtime = os.path.getmtime(directive_path)
        if mtime <= self._last_check_time:
            return []

        self._last_check_time = mtime

        try:
            with open(directive_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()

            if not content:
                return []

            directives = self._parse_directives(content)
            self._pending.extend(directives)

            logger.info(f"检测到 {len(directives)} 条人工指令")
            return directives

        except Exception as e:
            logger.error(f"读取人工指令失败: {e}")
            return []

    def _parse_directives(self, content: str) -> List[HumanDirective]:
        """解析指令文件内容（含输入长度限制）"""
        # 输入长度限制，防止恶意构造的超长指令
        MAX_DIRECTIVE_SIZE = 100_000  # 100KB
        if len(content) > MAX_DIRECTIVE_SIZE:
            logger.warning(f"指令文件过大 ({len(content)} bytes)，截断到 {MAX_DIRECTIVE_SIZE} bytes")
            content = content[:MAX_DIRECTIVE_SIZE]

        directives = []
        lines = content.split("\n")
        current_type = None
        current_content_lines = []

        for line in lines:
            line = line.strip()

            # 解析指令头
            if line.startswith("## "):
                # 保存前一个指令
                if current_type:
                    directives.append(HumanDirective(
                        directive_type=current_type,
                        content="\n".join(current_content_lines).strip(),
                        timestamp=time.time()
                    ))

                header = line[3:].strip()

                # 解析带目标的指令 (如 "SKIP: phase_name")
                if ":" in header:
                    parts = header.split(":", 1)
                    current_type = parts[0].strip().upper()
                    # target 暂存到 content，后面提取
                    current_content_lines = [f"TARGET: {parts[1].strip()}"]
                else:
                    current_type = header.upper()
                    current_content_lines = []

            elif line.startswith("# ") and not current_type:
                # 文件标题行，忽略
                continue
            elif line and current_type:
                current_content_lines.append(line)

        # 保存最后一个指令
        if current_type:
            directives.append(HumanDirective(
                directive_type=current_type,
                content="\n".join(current_content_lines).strip(),
                timestamp=time.time()
            ))

        # 后处理：从content中提取target
        for d in directives:
            if d.content.startswith("TARGET: "):
                lines = d.content.split("\n")
                d.target = lines[0][8:].strip()
                d.reason = "\n".join(lines[1:]).strip()
            else:
                d.reason = d.content

        return directives

    def acknowledge(self, directive: HumanDirective):
        """
        确认已处理指令
        """
        self._processed.append(directive)
        if directive in self._pending:
            self._pending.remove(directive)

        # 写入确认文件
        ack_path = os.path.join(self.output_dir, ACK_FILE)
        ack_entry = f"[{time.strftime('%H:%M:%S')}] 已处理: {directive.directive_type}"
        if directive.target:
            ack_entry += f" -> {directive.target}"
        ack_entry += f"\n  原因: {directive.reason[:100]}\n\n"

        with open(ack_path, 'a', encoding='utf-8') as f:
            f.write(ack_entry)

        logger.info(f"已确认指令: {directive.directive_type}")

    def clear_directive_file(self):
        """清空指令文件"""
        directive_path = os.path.join(self.output_dir, DIRECTIVE_FILE)
        if os.path.exists(directive_path):
            try:
                os.remove(directive_path)
                logger.info("已清空指令文件")
            except Exception as e:
                logger.warning(f"清空指令文件失败: {e}")

    def has_pending(self) -> bool:
        """是否有待处理的指令"""
        return len(self._pending) > 0

    def get_pending(self) -> List[HumanDirective]:
        """获取待处理的指令"""
        return self._pending.copy()

    def should_pause(self) -> bool:
        """是否应该暂停"""
        return any(d.directive_type == "PAUSE" for d in self._pending)

    def should_stop(self) -> bool:
        """是否应该停止"""
        return any(d.directive_type == "STOP" for d in self._pending)

    def get_skip_phases(self) -> List[str]:
        """获取应该跳过的阶段"""
        return [d.target for d in self._pending if d.directive_type == "SKIP" and d.target]

    def get_redo_phases(self) -> List[str]:
        """获取应该重做的阶段"""
        return [d.target for d in self._pending if d.directive_type == "REDO" and d.target]

    def get_adjustments(self) -> List[str]:
        """获取方向调整"""
        return [d.reason for d in self._pending if d.directive_type == "ADJUST"]

    def create_template(self):
        """创建指令文件模板"""
        template_path = os.path.join(self.output_dir, DIRECTIVE_FILE)
        if os.path.exists(template_path):
            return

        template = """# 人工干预指令
# 在Agent运行期间修改此文件来干预Agent行为
# Agent会在每次循环开始时检查此文件
#
# 支持的指令（取消注释对应行即可生效）：
# ## PAUSE              — 暂停Agent执行（等待恢复）
# ## RESUME             — 恢复暂停的Agent
# ## SKIP: chapter1     — 跳过指定阶段
# ## REDO: chapter3     — 重新执行指定阶段
# ## ADJUST: 说明       — 调整Agent方向
# ## STOP               — 完全停止Agent执行
"""

        os.makedirs(self.output_dir, exist_ok=True)
        with open(template_path, 'w', encoding='utf-8') as f:
            f.write(template)
        logger.info(f"已创建指令模板: {template_path}")
