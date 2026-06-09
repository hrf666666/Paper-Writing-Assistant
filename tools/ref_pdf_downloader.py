# -*- coding: utf-8 -*-
"""
Tool: 参考论文批量下载器 (v11.0)

v11.0: 集成 paper-fetch-skill 作为主下载后端
- paper-fetch 优先：获取结构化 Markdown 全文（17 个出版社覆盖）
- scansci-pdf 降级：PDF 下载备选
- 逐层收束搜索：从项目创新点提取核心方向 → Level 1 精准 → Level 4 兜底
- 双模式输出：Markdown (ref_md/) + PDF (ref_pdf/)

核心原则：精准收束，逐层放宽
- 代码 = 裁判（逐层搜索、计数、判断是否停止）
- LLM = 运动员（从创新点提取核心方向、规划搜索词）
- MD = 规则书（ref_search_strategy_guide.md）

安装：
    pip install paper-fetch-skill   # 主后端（推荐）
    pip install scansci-pdf         # 降级后端（可选）
"""

from __future__ import annotations

import json
import os
import logging
import re
import shutil
import subprocess
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class RefPdfDownloader:
    """参考论文批量下载器（v11.0: paper-fetch + scansci-pdf 双后端）"""

    def __init__(
        self,
        output_dir: str = "./ref_pdf",
        output_md_dir: str = "",
        strategy: str = "fastest",
        max_papers: int = 20,
        prefer_markdown: bool = True,
    ):
        """
        Args:
            output_dir: PDF 下载目标目录（默认 ref_pdf/）
            output_md_dir: Markdown 保存目录（默认 {output_dir} 的同级 ref_md/）
            strategy: 下载策略 fastest|oa_first|scihub_only|legal_only
            max_papers: 最大下载论文数
            prefer_markdown: 是否优先获取 Markdown 全文（paper-fetch）
        """
        self.output_dir = os.path.abspath(output_dir)
        self.output_md_dir = os.path.abspath(output_md_dir) if output_md_dir else os.path.abspath(
            os.path.join(os.path.dirname(output_dir), "ref_md")
        )
        self.strategy = strategy
        self.max_papers = max_papers
        self.prefer_markdown = prefer_markdown
        self._backend = self._detect_backend()

    def _detect_backend(self) -> str:
        """
        检测可用后端，优先级：
        1. paper-fetch-skill（Markdown 全文，17 个出版社覆盖）
        2. scansci-pdf（PDF 下载）
        """
        # 1. paper-fetch-skill（优先）
        try:
            from paper_fetch import fetch_paper  # noqa: F401
            return "paper_fetch"
        except ImportError:
            pass

        # 2. scansci-pdf Python 包
        try:
            import scansci_pdf  # noqa: F401
            return "scansci_python"
        except ImportError:
            pass

        # 3. scansci-pdf CLI
        try:
            result = subprocess.run(
                ["scansci-pdf", "--version"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                return "scansci_cli"
        except Exception:
            pass

        logger.warning(
            "[RefPdfDownloader] paper-fetch-skill 和 scansci-pdf 均未安装。"
            "请运行: pip install paper-fetch-skill"
        )
        return "unavailable"

    def search_and_download(
        self,
        keywords: List[str],
        venue: Optional[str] = None,
        year_from: int = 2020,
        year_to: Optional[int] = None,
        extra_dois: Optional[List[str]] = None,
    ) -> Dict:
        """
        搜索并批量下载参考论文。

        Args:
            keywords: 搜索关键词列表
            venue: 目标期刊名（如 "IEEE TCSVT"，用于筛选来源）
            year_from: 起始年份
            year_to: 截止年份（默认当前年）
            extra_dois: 额外的 DOI 列表（直接下载）
        """
        if self._backend == "unavailable":
            return {
                "status": "error",
                "message": "paper-fetch-skill 和 scansci-pdf 均未安装。请运行: pip install paper-fetch-skill",
                "downloaded": 0,
            }

        os.makedirs(self.output_dir, exist_ok=True)
        if self.prefer_markdown:
            os.makedirs(self.output_md_dir, exist_ok=True)
        results = {"searched": 0, "downloaded": 0, "files": [], "md_files": [], "errors": []}

        # Step 1: 按关键词搜索论文
        all_dois = []
        for kw in keywords:
            logger.info(f"[RefPdfDownloader] 搜索: {kw}")
            search_results = self._search(kw, venue, year_from, year_to)
            for paper in search_results:
                doi = paper.get("doi", "")
                if doi and doi not in all_dois:
                    all_dois.append(doi)
            results["searched"] += len(search_results)

        # Step 2: 添加额外 DOI
        if extra_dois:
            for doi in extra_dois:
                if doi not in all_dois:
                    all_dois.append(doi)

        # 截断
        all_dois = all_dois[:self.max_papers]

        logger.info(f"[RefPdfDownloader] 找到 {len(all_dois)} 篇论文，开始下载...")

        # Step 3: 批量下载
        for i, doi in enumerate(all_dois):
            logger.info(f"[RefPdfDownloader] 下载 {i+1}/{len(all_dois)}: {doi}")
            result = self._download_one(doi)
            if result.get("success"):
                results["downloaded"] += 1
                if result.get("md_path"):
                    results["md_files"].append(result["md_path"])
                results["files"].append(result.get("path", ""))
            else:
                results["errors"].append({
                    "doi": doi,
                    "error": result.get("error", "unknown"),
                })

        logger.info(
            f"[RefPdfDownloader] 完成: {results['downloaded']}/{len(all_dois)} 下载成功 "
            f"({len(results.get('md_files', []))} Markdown)"
        )
        return results

    def download_by_doi_list(
        self,
        doi_list: List[str],
    ) -> Dict:
        """
        直接按 DOI 列表批量下载。

        Args:
            doi_list: DOI 列表

        Returns:
            下载结果统计
        """
        if self._backend == "unavailable":
            return {
                "status": "error",
                "message": "scansci-pdf 未安装",
                "downloaded": 0,
            }

        os.makedirs(self.output_dir, exist_ok=True)
        results = {"downloaded": 0, "files": [], "errors": []}

        for i, doi in enumerate(doi_list[:self.max_papers]):
            logger.info(f"[RefPdfDownloader] 下载 {i+1}/{min(len(doi_list), self.max_papers)}: {doi}")
            result = self._download_one(doi)
            if result.get("success"):
                results["downloaded"] += 1
                results["files"].append(result.get("path", ""))
            else:
                results["errors"].append({
                    "doi": doi,
                    "error": result.get("error", "unknown"),
                })

        return results

    def download_by_bib_file(
        self,
        bib_path: str,
    ) -> Dict:
        """
        从 .bib 文件导入并下载全部论文。

        Args:
            bib_path: BibTeX 文件路径
        """
        if self._backend == "unavailable":
            return {"status": "error", "message": "scansci-pdf 未安装", "downloaded": 0}

        os.makedirs(self.output_dir, exist_ok=True)

        if self._backend == "scansci_cli":
            return self._cli_import_bib(bib_path)

        # Python 后端：解析 bib 文件提取 DOI，然后批量下载
        dois = self._extract_dois_from_bib(bib_path)
        if not dois:
            logger.warning("[RefPdfDownloader] .bib 文件中未找到 DOI")
            return {"downloaded": 0, "files": [], "errors": []}

        return self.download_by_doi_list(dois)

    def download_by_venue(
        self,
        venue: str,
        topic: str,
        count: int = 15,
        year_from: int = 2021,
    ) -> Dict:
        """
        从目标期刊搜索指定主题的论文并下载。

        这是最常用的接口：给定期刊名 + 研究主题，自动搜索并下载该期刊的
        相关论文作为参考。

        Args:
            venue: 期刊名（如 "IEEE TCSVT", "IEEE TIP", "CVPR"）
            topic: 研究主题关键词（如 "depth estimation"）
            count: 下载论文数量
            year_from: 起始年份

        Returns:
            下载结果统计
        """
        # 构建搜索查询
        search_keywords = [
            f"{topic}",
            f'{topic} venue:"{venue}"',
        ]

        return self.search_and_download(
            keywords=search_keywords,
            venue=venue,
            year_from=year_from,
        )

    # ═══════════════════════════════════════════════════
    # 内部实现
    # ═══════════════════════════════════════════════════

    def _search(
        self,
        keyword: str,
        venue: Optional[str],
        year_from: int,
        year_to: Optional[int],
    ) -> List[Dict]:
        """搜索论文"""
        if self._backend == "scansci_cli":
            return self._cli_search(keyword, venue, year_from, year_to)

        # Python 后端
        try:
            from scansci_pdf import search_papers
            results = search_papers(
                query=keyword,
                limit=self.max_papers,
                year_from=year_from,
                year_to=year_to or datetime.now().year,
                venue=venue,
            )
            return results if isinstance(results, list) else []
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"[RefPdfDownloader] 搜索失败 ({keyword}): {e}")

        # 降级：使用 OpenAlex API 直接搜索
        return self._search_openalex(keyword, venue, year_from, year_to)

    def _download_one(self, doi: str) -> Dict:
        """下载单篇论文，paper-fetch 优先，scansci-pdf 降级"""
        # ── 优先使用 paper-fetch 获取 Markdown ──
        if self._backend == "paper_fetch" and self.prefer_markdown:
            try:
                from tools.paper_fetch_tool import fetch_and_save
                content, md_path = fetch_and_save(doi, self.output_md_dir)
                if md_path and content.has_fulltext:
                    logger.info(f"[RefPdfDownloader] paper-fetch 全文: {content.title[:50]}")
                    return {
                        "success": True,
                        "path": md_path,
                        "md_path": md_path,
                        "content_kind": content.content_kind,
                        "title": content.title,
                    }
                elif md_path:
                    # 即使只有 metadata，也算成功（比 PDF 解析质量更好）
                    logger.info(f"[RefPdfDownloader] paper-fetch 元数据: {content.title[:50]}")
                    return {
                        "success": True,
                        "path": md_path,
                        "md_path": md_path,
                        "content_kind": content.content_kind,
                        "title": content.title,
                    }
            except Exception as e:
                logger.warning(f"[RefPdfDownloader] paper-fetch 失败 ({doi}): {e}")

        # ── 降级到 scansci-pdf 获取 PDF ──
        if self._backend in ("scansci_python", "scansci_cli"):
            return self._download_one_scansci(doi)

        return {"success": False, "error": "no download backend available"}

    def _download_one_scansci(self, doi: str) -> Dict:
        """通过 scansci-pdf 下载 PDF（降级方案）"""
        # Python 后端
        if self._backend == "scansci_python":
            try:
                from scansci_pdf import smart_download
                result = smart_download(
                    identifier=doi,
                    output_dir=self.output_dir,
                    strategy=self.strategy,
                )
                if result and result.get("path"):
                    return {"success": True, "path": result["path"]}
            except ImportError:
                pass
            except Exception as e:
                logger.warning(f"[RefPdfDownloader] scansci-pdf 下载失败 ({doi}): {e}")

        # CLI 后端
        if self._backend in ("scansci_python", "scansci_cli"):
            return self._cli_download(doi)

        return {"success": False, "error": "scansci-pdf download failed"}

    # ── CLI 后端 ──

    def _cli_search(
        self,
        keyword: str,
        venue: Optional[str],
        year_from: int,
        year_to: Optional[int],
    ) -> List[Dict]:
        """通过 CLI 搜索"""
        try:
            cmd = [
                "scansci-pdf", "search",
                "--query", keyword,
                "--limit", str(self.max_papers),
                "--year-from", str(year_from),
                "--format", "json",
            ]
            if venue:
                cmd.extend(["--venue", venue])
            if year_to:
                cmd.extend(["--year-to", str(year_to)])

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                return json.loads(result.stdout)
        except Exception as e:
            logger.warning(f"[RefPdfDownloader] CLI 搜索失败: {e}")
        return []

    def _cli_download(self, doi: str) -> Dict:
        """通过 CLI 下载"""
        try:
            cmd = [
                "scansci-pdf", "download",
                "--identifier", doi,
                "--output-dir", self.output_dir,
                "--strategy", self.strategy,
            ]

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0:
                # 查找下载的文件
                output_text = result.stdout.strip()
                if output_text and os.path.exists(output_text):
                    return {"success": True, "path": output_text}

                # 尝试在 output_dir 中找到最新的 PDF
                pdfs = sorted(
                    [f for f in os.listdir(self.output_dir) if f.endswith(".pdf")],
                    key=lambda f: os.path.getmtime(os.path.join(self.output_dir, f)),
                    reverse=True,
                )
                if pdfs:
                    return {"success": True, "path": os.path.join(self.output_dir, pdfs[0])}

            return {"success": False, "error": result.stderr[:200] if result.stderr else "unknown"}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "download timeout (120s)"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _cli_import_bib(self, bib_path: str) -> Dict:
        """通过 CLI 导入 .bib"""
        try:
            cmd = [
                "scansci-pdf", "import-bib",
                "--path", bib_path,
                "--output-dir", self.output_dir,
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=600,
            )
            if result.returncode == 0:
                return {"downloaded": -1, "files": [], "errors": [],
                        "message": "bib import completed (check output_dir for files)"}
            return {"downloaded": 0, "files": [], "errors": [{"error": result.stderr[:200]}]}
        except Exception as e:
            return {"downloaded": 0, "files": [], "errors": [{"error": str(e)}]}

    # ── 降级：OpenAlex API 直接搜索 ──

    def _search_openalex(
        self,
        keyword: str,
        venue: Optional[str],
        year_from: int,
        year_to: Optional[int],
    ) -> List[Dict]:
        """使用 OpenAlex API 搜索论文（无需 scansci-pdf 的降级方案）"""
        import requests

        try:
            params = {
                "search": keyword,
                "filter": f"from_publication_date:{year_from}-01-01",
                "per_page": min(self.max_papers, 25),
                "sort": "relevance_score:desc",
                "select": "doi,title,publication_year,primary_location",
            }
            if year_to:
                params["filter"] += f",to_publication_date:{year_to}-12-31"

            resp = requests.get(
                "https://api.openalex.org/works",
                params=params,
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                results = []
                for work in data.get("results", []):
                    doi = work.get("doi", "")
                    if doi and doi.startswith("https://doi.org/"):
                        doi = doi.replace("https://doi.org/", "")
                    results.append({
                        "doi": doi,
                        "title": work.get("title", ""),
                        "year": work.get("publication_year", 0),
                    })
                return results
        except Exception as e:
            logger.warning(f"[RefPdfDownloader] OpenAlex 搜索失败: {e}")

        return []

    def _extract_dois_from_bib(self, bib_path: str) -> List[str]:
        """从 .bib 文件中提取 DOI"""
        import re

        try:
            with open(bib_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            logger.error(f"[RefPdfDownloader] 读取 .bib 失败: {e}")
            return []

        # 匹配 doi = {...} 或 doi = "..."
        dois = re.findall(r'doi\s*=\s*[{"](10\.\d{4,}/[^\s}"\]]+)', content, re.IGNORECASE)
        return list(set(dois))


# ═══════════════════════════════════════════════════
# 便捷函数
# ═══════════════════════════════════════════════════

def smart_download_ref_papers(
    project_data: Dict,
    innovation_points: List[Dict],
    venue: str,
    api_client=None,
    output_dir: str = "./ref_pdf",
    max_papers: int = 25,
    strategy: str = "fastest",
) -> Dict:
    """
    v10.1 智能下载入口：从项目创新点提取核心方向，逐层收束搜索。

    工作流程：
    1. RefSearchStrategist 从创新点提取核心方向 + 规划 4 层搜索策略
    2. 逐层执行搜索，每层检查累计数量
    3. 达到 stop_if_found 阈值 → 停止后续层
    4. 批量下载搜索到的论文

    Args:
        project_data: 项目数据
        innovation_points: 创新点列表
        venue: 目标期刊名
        api_client: LLM 客户端（用于策略规划）
        output_dir: 下载目录
        max_papers: 最大下载数
        strategy: 下载策略

    Returns:
        {
            "strategy": {...},      # 搜索策略
            "layer_results": [...],  # 每层搜索结果
            "downloaded": int,
            "files": [...],
            "errors": [...],
        }
    """
    downloader = RefPdfDownloader(
        output_dir=output_dir,
        strategy=strategy,
        max_papers=max_papers,
    )

    # 统计已有论文
    existing_dois = _get_existing_dois(output_dir)
    existing_count = len(existing_dois)

    # Step 1: LLM 规划搜索策略
    search_strategy = None
    if api_client:
        try:
            from agent.ref_search_strategist import RefSearchStrategist
            strategist = RefSearchStrategist(api_client)
            search_strategy = strategist.plan_search_strategy(
                project_data=project_data,
                innovation_points=innovation_points,
                venue=venue,
                existing_dois=existing_dois,
                existing_count=existing_count,
            )
            logger.info(f"[SmartDownload] 搜索策略: {len(search_strategy.get('search_layers', []))} 层")
        except Exception as e:
            logger.warning(f"[SmartDownload] 策略规划失败，使用降级策略: {e}")
            search_strategy = None

    if not search_strategy or not search_strategy.get("search_layers"):
        search_strategy = _fallback_search_strategy(innovation_points, venue)

    # Step 2: 逐层搜索 + 下载
    all_results = {
        "strategy": search_strategy,
        "layer_results": [],
        "downloaded": 0,
        "files": [],
        "survey_files": [],  # 综述论文单独追踪
        "errors": [],
    }

    cumulative_found = existing_count  # 累计找到的论文数

    for layer in search_strategy["search_layers"]:
        level = layer.get("level", 0)
        queries = layer.get("queries", [])
        stop_if = layer.get("stop_if_found", 25)
        is_survey = layer.get("is_survey", False)

        # 综述层不受研究论文累计数限制，独立计数
        if not is_survey:
            # 检查是否已达到停止条件
            if cumulative_found >= stop_if:
                logger.info(f"[SmartDownload] Level {level}: 累计 {cumulative_found} 篇 >= 阈值 {stop_if}，停止")
                continue  # 继续处理后续层（可能是 survey 层）

        logger.info(f"[SmartDownload] Level {level}: {layer.get('description', '')} {'[SURVEY]' if is_survey else ''}")

        layer_result = {
            "level": level,
            "is_survey": is_survey,
            "searched": 0,
            "new_dois": [],
            "downloaded": 0,
        }

        for query in queries:
            kw = query.get("keywords", "")
            yf = query.get("year_from", 2024)
            yt = query.get("year_to", 2026)
            v = query.get("venue", "")

            if not kw:
                continue

            # 搜索
            search_results = downloader._search(kw, v or None, yf, yt)
            layer_result["searched"] += len(search_results)

            # 去重
            new_dois = []
            for r in search_results:
                doi = r.get("doi", "")
                if doi and doi not in existing_dois and doi not in new_dois:
                    new_dois.append(doi)

            layer_result["new_dois"].extend(new_dois)

        # 下载本层找到的论文
        for doi in layer_result["new_dois"]:
            if not is_survey and all_results["downloaded"] >= max_papers:
                break
            if is_survey and len(all_results["survey_files"]) >= 3:
                break

            result = downloader._download_one(doi)
            if result.get("success"):
                all_results["downloaded"] += 1
                existing_dois.append(doi)
                layer_result["downloaded"] += 1
                if is_survey:
                    all_results["survey_files"].append({
                        "path": result.get("path", ""),
                        "doi": doi,
                        "is_survey": True,
                    })
                else:
                    all_results["files"].append(result.get("path", ""))
            else:
                all_results["errors"].append({"doi": doi, "error": result.get("error", "")})

        cumulative_found += layer_result["downloaded"]
        all_results["layer_results"].append(layer_result)

        survey_tag = " [SURVEY]" if is_survey else ""
        logger.info(
            f"[SmartDownload] Level {level}{survey_tag}: 搜索 {layer_result['searched']} 篇, "
            f"新增 DOI {len(layer_result['new_dois'])}, "
            f"下载 {layer_result['downloaded']} 篇, "
            f"累计 {cumulative_found} 篇"
        )

    # Step 3: 确保 must_include_dois 下载
    for doi in search_strategy.get("must_include_dois", []):
        if doi in existing_dois:
            continue
        if all_results["downloaded"] >= max_papers:
            break

        result = downloader._download_one(doi)
        if result.get("success"):
            all_results["downloaded"] += 1
            all_results["files"].append(result.get("path", ""))

    logger.info(f"[SmartDownload] 完成: {all_results['downloaded']} 篇下载成功")
    return all_results


def _get_existing_dois(output_dir: str) -> List[str]:
    """从已有 PDF 文件的文件名和元数据推断 DOI"""
    dois = []
    if not os.path.isdir(output_dir):
        return dois
    for fname in os.listdir(output_dir):
        if not fname.lower().endswith(".pdf"):
            continue
        # 策略1: 文件名中包含 DOI 模式 (10.xxxx/...)
        m = re.search(r'(10\.\d{4,}/[^\s"_]+)', fname)
        if m:
            dois.append(m.group(1))
            continue
        # 策略2: 从 PDF 文本元数据中提取 DOI
        fpath = os.path.join(output_dir, fname)
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(fpath)
            meta = doc.metadata or {}
            for field in ["subject", "keywords", "title"]:
                val = meta.get(field, "")
                if val:
                    m2 = re.search(r'(10\.\d{4,}/[^\s]+)', val)
                    if m2:
                        dois.append(m2.group(1))
                        break
            # 从首页文本提取
            if len(dois) == 0 or fname not in str(dois):
                first_page_text = doc[0].get_text()[:3000] if doc.page_count > 0 else ""
                m3 = re.search(r'(?:doi|DOI|Doi)[:\s]*(10\.\d{4,}/[^\s"\]]+)', first_page_text)
                if m3:
                    dois.append(m3.group(1))
            doc.close()
        except Exception:
            pass
    return dois


def _fallback_search_strategy(
    innovation_points: List[Dict],
    venue: str,
) -> Dict:
    """无 LLM 时的降级搜索策略"""
    # 从创新点 anchor 的 contribution_statement 提取英文关键词
    phrases = set()
    for ip in innovation_points[:3]:
        anchor = ip.get("anchor", {})
        contrib = anchor.get("contribution_statement", "")
        if contrib:
            words = contrib.lower().replace(",", " ").replace(".", " ").split()
            words = [w for w in words if len(w) > 3 and w not in {
                "this", "that", "from", "with", "through", "based",
                "using", "propose", "propose", "design", "method",
            }]
            phrase = " ".join(words[:4])
            phrases.add(phrase)

    queries_l1 = [{"keywords": p, "year_from": 2024, "year_to": 2026, "venue": venue} for p in list(phrases)[:3]]
    queries_l2 = [{"keywords": p, "year_from": 2022, "year_to": 2026, "venue": ""} for p in list(phrases)[:3]]

    # 提取领域词用于综述搜索
    domain_word = "depth estimation"
    if phrases:
        first_phrase = list(phrases)[0].split()
        if len(first_phrase) >= 2:
            domain_word = " ".join(first_phrase[-2:])

    return {
        "core_direction": "extracted from innovation points",
        "is_survey_paper": False,
        "search_layers": [
            {"level": 1, "description": "core keywords from innovations", "is_survey": False, "queries": queries_l1, "target_count": 10, "stop_if_found": 8},
            {"level": 2, "description": "broader search", "is_survey": False, "queries": queries_l2, "target_count": 10, "stop_if_found": 18},
            {"level": 3, "description": "domain-level", "is_survey": False, "queries": [{"keywords": domain_word, "year_from": 2020, "year_to": 2026, "venue": ""}], "target_count": 5, "stop_if_found": 25},
            {"level": 5, "description": "survey papers", "is_survey": True, "queries": [{"keywords": f"survey OR review {domain_word}", "year_from": 2020, "year_to": 2026, "venue": ""}], "target_count": 3, "stop_if_found": 3},
        ],
        "must_include_dois": [],
        "excluded_keywords": [],
    }


def download_ref_papers(
    venue: str = "IEEE TCSVT",
    topic: str = "",
    keywords: Optional[List[str]] = None,
    dois: Optional[List[str]] = None,
    bib_file: Optional[str] = None,
    output_dir: str = "./ref_pdf",
    max_papers: int = 20,
    strategy: str = "fastest",
) -> Dict:
    """
    下载参考论文的主入口（简单模式，不带 LLM 策略规划）。

    如需智能搜索（从创新点自动规划），请使用 smart_download_ref_papers()。

    使用方式（任选一种或组合）：

    1. 按期刊 + 主题搜索下载：
       download_ref_papers(venue="IEEE TCSVT", topic="depth estimation")

    2. 按关键词搜索下载：
       download_ref_papers(keywords=["light field depth estimation", "transparent surface"])

    3. 按 DOI 列表下载：
       download_ref_papers(dois=["10.1109/TCSVT.2024.xxxx", ...])

    4. 从 .bib 文件导入下载：
       download_ref_papers(bib_file="references.bib")
    """
    downloader = RefPdfDownloader(
        output_dir=output_dir,
        strategy=strategy,
        max_papers=max_papers,
    )

    all_results = {"downloaded": 0, "files": [], "errors": []}

    # 模式 1: 按期刊 + 主题
    if venue and topic:
        logger.info(f"[RefPdfDownloader] 模式 1: 期刊+主题 ({venue}: {topic})")
        result = downloader.download_by_venue(venue, topic, count=max_papers)
        all_results["downloaded"] += result.get("downloaded", 0)
        all_results["files"].extend(result.get("files", []))
        all_results["errors"].extend(result.get("errors", []))

    # 模式 2: 按关键词
    if keywords:
        logger.info(f"[RefPdfDownloader] 模式 2: 关键词 ({keywords})")
        result = downloader.search_and_download(keywords=keywords)
        all_results["downloaded"] += result.get("downloaded", 0)
        all_results["files"].extend(result.get("files", []))
        all_results["errors"].extend(result.get("errors", []))

    # 模式 3: 按 DOI
    if dois:
        logger.info(f"[RefPdfDownloader] 模式 3: DOI 列表 ({len(dois)} 篇)")
        result = downloader.download_by_doi_list(dois)
        all_results["downloaded"] += result.get("downloaded", 0)
        all_results["files"].extend(result.get("files", []))
        all_results["errors"].extend(result.get("errors", []))

    # 模式 4: 从 .bib
    if bib_file and os.path.exists(bib_file):
        logger.info(f"[RefPdfDownloader] 模式 4: .bib 文件 ({bib_file})")
        result = downloader.download_by_bib_file(bib_file)
        all_results["downloaded"] += result.get("downloaded", 0)
        all_results["files"].extend(result.get("files", []))
        all_results["errors"].extend(result.get("errors", []))

    return all_results
