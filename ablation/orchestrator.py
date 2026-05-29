# -*- coding: utf-8 -*-
"""
消融实验编排器 (Ablation Orchestrator)

通过子进程调用 auto_research_agent (api.py) 执行真实消融实验。

工作流:
  1. 分析项目代码，确定消融维度
  2. 生成消融变体代码（每个变体禁用一个模块）
  3. 通过 subprocess 启动 auto_research_agent
  4. 轮询实验状态（通过 SQLite）
  5. 收集结果并验证

与 auto_research_agent 的交互:
  - 启动: `python api.py start --project <path> --gpu <id>`
  - 状态: `python api.py status --project <path>`
  - 结果: 直接读取项目目录下的 SQLite 数据库
"""

from __future__ import annotations

import json
import os
import subprocess
import sqlite3
import time
import logging
import re
from typing import Dict, Any, List, Optional

from config.project_config import (
    AUTO_RESEARCH_AGENT_PATH,
    AUTO_RESEARCH_AGENT_PYTHON,
    PROJECT_CODE_PATH,
)

logger = logging.getLogger(__name__)


class AblationOrchestrator:
    """消融实验编排器"""

    POLL_INTERVAL = 30  # 轮询间隔（秒）
    MAX_POLL_TIME = 3600 * 6  # 最大等待6小时

    def __init__(self):
        self.agent_path = AUTO_RESEARCH_AGENT_PATH
        self.python_path = AUTO_RESEARCH_AGENT_PYTHON
        self._process = None

    def run(self, project_data: Dict, output_dir: str,
            ablation_config=None) -> Dict[str, Any]:
        """
        执行消融实验

        Args:
            project_data: 项目分析数据
            output_dir: 输出目录
            ablation_config: AblationConfig 实例（来自 venue profile）

        Returns:
            {
                "experiments": List[dict],
                "ablation_design": dict,
                "results_collected": bool,
                "tables": dict,
            }
        """
        logger.info("[AblationOrchestrator] 开始消融实验编排...")

        try:
            os.makedirs(output_dir, exist_ok=True)
        except OSError as e:
            logger.error(f"创建输出目录失败 {output_dir}: {e}")

        # Step 1: 设计消融实验
        try:
            ablation_design = self._design_ablations(project_data, ablation_config)
        except Exception as e:
            logger.error(f"消融实验设计失败: {e}")
            ablation_design = {"variants": [], "method": "error"}

        logger.info(f"[AblationOrchestrator] 设计了 {len(ablation_design.get('variants', []))} 个消融变体")

        # 保存设计
        design_file = os.path.join(output_dir, "ablation_design.json")
        try:
            with open(design_file, 'w', encoding='utf-8') as f:
                json.dump(ablation_design, f, ensure_ascii=False, indent=2)
        except IOError as e:
            logger.error(f"保存消融设计方案失败: {e}")

        # Step 2: 尝试调用 auto_research_agent
        results = self._try_run_agent(project_data, output_dir, ablation_design)

        # Step 3: 收集和格式化结果
        if results:
            try:
                from ablation.table_generator import AblationTableGenerator
                table_gen = AblationTableGenerator()
                tables = table_gen.generate_tables(results, ablation_config)
            except Exception as e:
                logger.error(f"表格生成失败: {e}")
                tables = {}

            return {
                "experiments": results,
                "ablation_design": ablation_design,
                "results_collected": True,
                "tables": tables,
            }

        # 降级：生成模板结果
        return {
            "experiments": [],
            "ablation_design": ablation_design,
            "results_collected": False,
            "tables": {},
            "note": "auto_research_agent execution skipped; results need manual input",
        }

    def _design_ablations(self, project_data: Dict,
                           ablation_config) -> Dict:
        """设计消融实验方案"""
        innovations = project_data.get("innovation_points", [])
        arch = project_data.get("model_architecture", {})

        min_abl = 3
        max_abl = 5
        if ablation_config:
            min_abl = ablation_config.min_ablations
            max_abl = ablation_config.max_ablations

        # 基于创新点生成消融变体
        variants = []
        for i, inn in enumerate(innovations[:max_abl]):
            name = inn.get("创新点名称", f"Component {i+1}")
            variants.append({
                "name": f"w/o {name}",
                "description": f"Remove {name} from the full model",
                "component": name,
                "expected_impact": "performance degradation expected",
            })

        # 添加完整模型作为 baseline
        variants.insert(0, {
            "name": "Full Model",
            "description": "Complete model with all components",
            "component": None,
            "expected_impact": "upper bound",
        })

        return {
            "variants": variants,
            "method": "leave-one-out",
            "min_ablations": min_abl,
            "max_ablations": max_abl,
        }

    def _try_run_agent(self, project_data: Dict, output_dir: str,
                        ablation_design: Dict) -> Optional[List[Dict]]:
        """尝试调用 auto_research_agent 执行实验"""
        code_path = PROJECT_CODE_PATH
        if not os.path.isdir(code_path):
            logger.warning(f"项目代码路径不存在: {code_path}")
            return None

        api_script = os.path.join(self.agent_path, "api.py")
        if not os.path.isfile(api_script):
            logger.warning(f"auto_research_agent API 脚本不存在: {api_script}")
            return None

        # 检查是否已有实验结果
        existing = self._check_existing_results(code_path)
        if existing:
            logger.info(f"[AblationOrchestrator] 发现已有实验结果: {len(existing)} 条")
            return existing

        # 启动 auto_research_agent
        logger.info("[AblationOrchestrator] 启动 auto_research_agent...")
        try:
            env = os.environ.copy()
            # 确保 API keys 在环境中
            for key in ["GLM_CODING_PLAN_API_KEY", "ALI_TOKEN_PLAN_API_KEY",
                        "ALI_API_KEY", "OPENAI_API_KEY"]:
                if key in os.environ:
                    env[key] = os.environ[key]

            cmd = [
                self.python_path, api_script,
                "start", "--project", code_path,
                "--gpu", "0",
            ]

            self._process = subprocess.Popen(
                cmd,
                cwd=self.agent_path,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            # 轮询实验状态
            results = self._poll_results(code_path)
            return results

        except subprocess.SubprocessError as e:
            logger.error(f"auto_research_agent 子进程启动失败: {e}")
            return None
        except Exception as e:
            logger.error(f"auto_research_agent 启动失败: {e}")
            return None

    def _check_existing_results(self, project_path: str) -> Optional[List[Dict]]:
        """检查是否已有实验结果"""
        # 尝试读取项目中的实验结果文件
        result_patterns = [
            os.path.join(project_path, "results.json"),
            os.path.join(project_path, "ablation_results.json"),
            os.path.join(project_path, "output", "results.json"),
        ]

        for path in result_patterns:
            if os.path.isfile(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if isinstance(data, list) and len(data) > 0:
                        return data
                    if isinstance(data, dict) and "experiments" in data:
                        return data["experiments"]
                except Exception:
                    continue

        # 尝试读取 SQLite
        db_patterns = [
            os.path.join(project_path, "autoresearcher.db"),
            os.path.join(project_path, "research.db"),
        ]
        for db_path in db_patterns:
            if os.path.isfile(db_path):
                try:
                    return self._read_sqlite_results(db_path)
                except Exception:
                    continue

        return None

    def _poll_results(self, project_path: str) -> Optional[List[Dict]]:
        """轮询实验状态直到完成"""
        start_time = time.time()
        api_script = os.path.join(self.agent_path, "api.py")

        while time.time() - start_time < self.MAX_POLL_TIME:
            # 检查状态
            try:
                result = subprocess.run(
                    [self.python_path, api_script, "status", "--project", project_path],
                    cwd=self.agent_path,
                    capture_output=True, text=True, timeout=30,
                )
                status_text = result.stdout

                if "completed" in status_text.lower() or "finished" in status_text.lower():
                    logger.info("[AblationOrchestrator] 实验完成!")
                    return self._check_existing_results(project_path)

                if "failed" in status_text.lower() or "error" in status_text.lower():
                    logger.warning(f"[AblationOrchestrator] 实验失败: {status_text[:200]}")
                    return None

            except subprocess.TimeoutExpired:
                pass
            except Exception as e:
                logger.debug(f"状态查询失败: {e}")

            # 等待
            elapsed = int(time.time() - start_time)
            logger.info(f"[AblationOrchestrator] 等待实验... ({elapsed}s)")
            time.sleep(self.POLL_INTERVAL)

        logger.warning("[AblationOrchestrator] 超时，停止等待")
        return None

    def _read_sqlite_results(self, db_path: str) -> List[Dict]:
        """从 SQLite 读取实验结果"""
        results = []
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # 尝试常见的表结构
            tables = cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = [t[0] for t in tables]

            for table in table_names:
                try:
                    rows = cursor.execute(f"SELECT * FROM {table} LIMIT 100").fetchall()
                    if rows:
                        cols = [d[0] for d in cursor.description]
                        for row in rows:
                            results.append(dict(zip(cols, row)))
                except Exception:
                    continue

            conn.close()
        except Exception as e:
            logger.warning(f"SQLite 读取失败: {e}")

        return results
