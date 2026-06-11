# -*- coding: utf-8 -*-
"""
统一参考文献存储 — ReferenceStore (v12.2)

用 SQLite 替代 14 个碎片化 JSON 文件，提供：
1. 唯一真相源：所有论文元数据、搜索缓存、claims、citations 在一个 refs.db
2. 线程安全：WAL 模式 + threading.Lock 写锁，支持并发读
3. 子 Agent 边界：tasks 表 + claim_tasks/complete_task 控制检索边界
4. 防重复：DOI/title_norm 去重，search_log 防重复 API 调用

替代的文件：
- reference_pool.json          → papers 表
- citation_bank.json           → claims 表
- citation_entries.json        → citations 表
- citation_map.json            → citations.bib_key 列
- reference_verification*.json → citations.verified 列
- search_cache/*.json          → search_log 表
- ref_md/*.md 元数据           → papers.fulltext_* 列
"""

import os
import re
import json
import sqlite3
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Schema DDL
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_SCHEMA_SQL = """
-- ━━ 核心论文表（唯一真相源）━━━
CREATE TABLE IF NOT EXISTS papers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    doi             TEXT UNIQUE,
    title           TEXT NOT NULL,
    title_norm      TEXT NOT NULL,       -- lowercase + 去标点，去重用
    authors         TEXT,                -- JSON: ["name1", "name2"]
    year            INTEGER,
    venue           TEXT,
    abstract        TEXT,
    citation_count  INTEGER DEFAULT 0,

    -- 来源追踪
    source          TEXT DEFAULT 'unknown',  -- pack/web_search/openalex/paper_fetch/user
    search_query    TEXT,                    -- 哪个 query 搜到的
    group_name      TEXT,                    -- core_topic/methods/datasets/baselines
    relevance_score REAL DEFAULT 0,

    -- 全文状态
    fulltext_status TEXT DEFAULT 'none',     -- none/fetching/fetched/failed
    fulltext_path   TEXT,                    -- ref_md/xxx.md
    token_estimate  INTEGER DEFAULT 0,
    fetched_at      TEXT,

    -- 处理状态（防止重复处理）
    claims_extracted INTEGER DEFAULT 0,
    verified         INTEGER DEFAULT 0,
    used_in_paper    INTEGER DEFAULT 0,

    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_papers_doi ON papers(doi);
CREATE INDEX IF NOT EXISTS idx_papers_title_norm ON papers(title_norm);
CREATE INDEX IF NOT EXISTS idx_papers_fulltext_status ON papers(fulltext_status);
CREATE INDEX IF NOT EXISTS idx_papers_source ON papers(source);
CREATE INDEX IF NOT EXISTS idx_papers_fetch_candidate ON papers(fulltext_status, citation_count);

-- ━━ 搜索缓存（防重复 API 调用）━━━
CREATE TABLE IF NOT EXISTS search_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    query           TEXT NOT NULL,
    query_norm      TEXT NOT NULL,       -- 标准化 query（去停用词+lowercase）
    source          TEXT NOT NULL,       -- offline/web_search/openalex/mcp
    results_json    TEXT,                -- 原始返回（审计用）
    result_count    INTEGER DEFAULT 0,
    hit_doi_list    TEXT,                -- JSON: ["doi1","doi2"] 已去重 DOI
    searched_at     TEXT DEFAULT (datetime('now')),
    expires_at      TEXT,                -- 缓存过期（默认7天）
    UNIQUE(query_norm, source)
);

CREATE INDEX IF NOT EXISTS idx_search_log_query ON search_log(query_norm, source);
CREATE INDEX IF NOT EXISTS idx_search_log_expires ON search_log(expires_at);

-- ━━ Claim 提取结果 ━━
CREATE TABLE IF NOT EXISTS claims (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id        INTEGER NOT NULL REFERENCES papers(id),
    claim_text      TEXT NOT NULL,
    technique       TEXT,                -- 方法/技术关键词
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_claims_paper ON claims(paper_id);

-- ━━ 引用解析（章节 → 论文映射）━━━
CREATE TABLE IF NOT EXISTS citations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_num     INTEGER NOT NULL,
    citation_tag    TEXT,                -- 原始 <citation ...> 标记
    paper_id        INTEGER REFERENCES papers(id),
    cite_num        INTEGER,             -- 最终编号 [N]
    bib_key         TEXT,                -- 最终 \\cite{key}
    verified        INTEGER DEFAULT 0,
    verified_reason TEXT,
    UNIQUE(chapter_num, citation_tag)
);

CREATE INDEX IF NOT EXISTS idx_citations_paper ON citations(paper_id);
CREATE INDEX IF NOT EXISTS idx_citations_cite_num ON citations(cite_num);

-- ━━ 任务队列（sub-agent 边界控制）━━━
CREATE TABLE IF NOT EXISTS tasks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type       TEXT NOT NULL,       -- search/fetch/extract_claims/verify
    status          TEXT DEFAULT 'pending',  -- pending/running/done/failed
    paper_id        INTEGER REFERENCES papers(id),
    params          TEXT,                -- JSON: {"query": "...", "source": "..."}
    agent           TEXT,                -- 哪个 sub-agent 领了这任务
    result_summary  TEXT,
    error           TEXT,
    started_at      TEXT,
    completed_at    TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_tasks_type_status ON tasks(task_type, status);
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 工具函数
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _normalize_title(title: str) -> str:
    """标题标准化：lowercase + 去标点 + 单空格，用于去重"""
    t = title.lower().strip()
    t = re.sub(r'[^a-z0-9\s]', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def _normalize_query(query: str) -> str:
    """Query 标准化：lowercase + 去停用词，用于搜索缓存命中"""
    q = query.lower().strip()
    q = re.sub(r'[^a-z0-9\s]', ' ', q)
    stopwords = {'the', 'a', 'an', 'of', 'for', 'and', 'in', 'on', 'to',
                 'from', 'with', 'by', 'at', 'is', 'are', 'using', 'based'}
    words = [w for w in q.split() if w not in stopwords and len(w) > 1]
    return ' '.join(sorted(words))


def _authors_to_json(authors) -> str:
    """统一 authors 为 JSON 字符串 ["name1", "name2"]"""
    if not authors:
        return "[]"
    if isinstance(authors, str):
        return json.dumps([authors])
    result = []
    for a in authors:
        if isinstance(a, dict):
            result.append(a.get("name", ""))
        elif isinstance(a, str):
            result.append(a)
        else:
            result.append(str(a))
    return json.dumps([n for n in result if n])


def _json_to_authors(authors_json: str) -> List[Dict]:
    """反序列化为 [{name: "..."}] 格式（兼容旧代码）"""
    try:
        names = json.loads(authors_json) if authors_json else []
    except (json.JSONDecodeError, TypeError):
        return []
    return [{"name": n} for n in names if n]


def _row_to_dict(row) -> Optional[Dict]:
    """sqlite3.Row → dict"""
    if row is None:
        return None
    return dict(row)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ReferenceStore 主类
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ReferenceStore:
    """
    统一参考文献存储 — refs.db 的唯一访问入口。

    线程安全设计：
    - SQLite WAL 模式：允许多线程并发读
    - self._write_lock：串行化所有写操作
    - 每个线程用独立的 cursor（check_same_thread=False）

    使用方式：
        store = ReferenceStore("/path/to/output/refs.db")
        paper_id = store.upsert_paper({...})
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._write_lock = threading.RLock()  # RLock: 允许读方法内调读方法，线程安全

        # 确保目录存在
        os.makedirs(os.path.dirname(db_path) or '.', exist_ok=True)

        # 连接 + WAL 模式
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA foreign_keys=ON")

        # 建表
        self._conn.executescript(_SCHEMA_SQL)
        self._conn.commit()

        logger.info(f"[ReferenceStore] 初始化: {db_path}")

    def close(self):
        """关闭数据库连接"""
        try:
            self._conn.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    # ══════════════════════════════════════
    # papers 表 — CRUD
    # ══════════════════════════════════════

    def upsert_paper(self, paper: Dict) -> int:
        """
        插入或更新论文。用 DOI / title_norm 去重。
        返回 paper id。
        """
        with self._write_lock:
            pid = self._upsert_paper_inner(paper)
            self._conn.commit()
            return pid

    def _upsert_paper_inner(self, paper: Dict) -> int:
        """
        upsert 核心逻辑（无 commit），供 upsert_paper 和 upsert_papers_batch 复用。
        调用者必须持有 self._write_lock。
        """
        doi = paper.get("doi", "") or ""
        title = paper.get("title", "") or ""
        title_norm = _normalize_title(title)
        authors_json = _authors_to_json(paper.get("authors", []))
        year = paper.get("year")
        if isinstance(year, str):
            try:
                year = int(year)
            except (ValueError, TypeError):
                year = None
        venue = paper.get("venue", "") or ""
        if isinstance(venue, dict):
            venue = venue.get("raw", "")
        abstract = paper.get("abstract", "") or ""
        if len(abstract) > 2000:
            abstract = abstract[:2000]
        citation_count = paper.get("citationCount",
                                    paper.get("citation_count", 0)) or 0
        source = paper.get("_source", paper.get("source", "unknown"))
        search_query = paper.get("search_query", "")
        group_name = paper.get("group", paper.get("group_name", ""))
        relevance_score = paper.get("_relevance_score",
                                     paper.get("relevance_score", 0)) or 0

        # 查找已有记录
        existing = None
        if doi:
            row = self._conn.execute(
                "SELECT id FROM papers WHERE doi = ?", (doi,)
            ).fetchone()
            if row:
                existing = row["id"]
        if existing is None and title_norm:
            row = self._conn.execute(
                "SELECT id FROM papers WHERE title_norm = ?", (title_norm,)
            ).fetchone()
            if row:
                existing = row["id"]

        if existing is not None:
            self._conn.execute("""
                UPDATE papers SET
                    title = CASE WHEN LENGTH(title) < LENGTH(?) THEN ? ELSE title END,
                    authors = CASE WHEN authors = '[]' THEN ? ELSE authors END,
                    year = COALESCE(year, ?),
                    venue = CASE WHEN venue = '' THEN ? ELSE venue END,
                    abstract = CASE WHEN LENGTH(abstract) < LENGTH(?) THEN ? ELSE abstract END,
                    citation_count = MAX(citation_count, ?),
                    relevance_score = MAX(relevance_score, ?),
                    source = CASE WHEN source = 'unknown' THEN ? ELSE source END,
                    group_name = COALESCE(NULLIF(group_name, ''), ?, group_name),
                    search_query = COALESCE(NULLIF(search_query, ''), ?, search_query)
                WHERE id = ?
            """, (title, title, authors_json, year, venue,
                  abstract, abstract, citation_count, relevance_score,
                  source, group_name, search_query, existing))
            return existing
        else:
            cur = self._conn.execute("""
                INSERT INTO papers (doi, title, title_norm, authors, year, venue,
                    abstract, citation_count, source, search_query, group_name,
                    relevance_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (doi, title, title_norm, authors_json, year, venue,
                  abstract, citation_count, source, search_query, group_name,
                  relevance_score))
            return cur.lastrowid

    def upsert_papers_batch(self, papers: List[Dict]) -> int:
        """批量插入，每篇独立 SAVEPOINT，失败只跳过当前篇"""
        count = 0
        with self._write_lock:
            for i, p in enumerate(papers):
                sp_name = f"batch_{i}"
                self._conn.execute(f"SAVEPOINT {sp_name}")
                try:
                    self._upsert_paper_inner(p)
                    count += 1
                    self._conn.execute(f"RELEASE {sp_name}")
                except Exception as e:
                    logger.debug(f"[ReferenceStore] upsert_papers_batch 跳过: {e}")
                    self._conn.execute(f"ROLLBACK TO {sp_name}")
                    self._conn.execute(f"RELEASE {sp_name}")
            self._conn.commit()
        return count

    def get_paper(self, paper_id: int) -> Optional[Dict]:
        """按 ID 获取论文"""
        with self._write_lock:
            row = self._conn.execute(
                "SELECT * FROM papers WHERE id = ?", (paper_id,)
            ).fetchone()
        return self._paper_row_to_dict(row)

    def find_paper_by_doi(self, doi: str) -> Optional[Dict]:
        """按 DOI 查找"""
        with self._write_lock:
            row = self._conn.execute(
                "SELECT * FROM papers WHERE doi = ?", (doi,)
            ).fetchone()
        return self._paper_row_to_dict(row)

    def find_paper_by_title(self, title: str) -> Optional[Dict]:
        """按标题模糊查找"""
        title_norm = _normalize_title(title)
        with self._write_lock:
            row = self._conn.execute(
                "SELECT * FROM papers WHERE title_norm = ?", (title_norm,)
            ).fetchone()
        return self._paper_row_to_dict(row)

    def get_all_papers(self, limit: int = 200,
                       min_relevance: float = 0) -> List[Dict]:
        """获取所有论文，按 relevance_score 排序"""
        with self._write_lock:
            rows = self._conn.execute("""
                SELECT * FROM papers
                WHERE relevance_score >= ?
                ORDER BY relevance_score DESC, citation_count DESC
                LIMIT ?
            """, (min_relevance, limit)).fetchall()
        return [self._paper_row_to_dict(r) for r in rows]

    def get_paper_count(self) -> int:
        with self._write_lock:
            return self._conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]

    def get_papers_for_fetch(self, limit: int = 20) -> List[Dict]:
        """获取待获取全文的论文（按引用数排序）"""
        with self._write_lock:
            rows = self._conn.execute("""
                SELECT * FROM papers
                WHERE fulltext_status = 'none' AND (doi != '' OR title != '')
                ORDER BY citation_count DESC
                LIMIT ?
            """, (limit,)).fetchall()
        return [self._paper_row_to_dict(r) for r in rows]

    def get_papers_for_analysis(self, limit: int = 50) -> List[Dict]:
        """获取待提取 claims 的论文"""
        with self._write_lock:
            rows = self._conn.execute("""
                SELECT * FROM papers
                WHERE claims_extracted = 0 AND abstract != ''
                ORDER BY relevance_score DESC
                LIMIT ?
            """, (limit,)).fetchall()
        return [self._paper_row_to_dict(r) for r in rows]

    def update_fulltext_status(self, paper_id: int, status: str,
                                fulltext_path: str = "",
                                token_estimate: int = 0):
        """更新全文获取状态"""
        with self._write_lock:
            fetched_at = datetime.now().isoformat() if status == "fetched" else None
            self._conn.execute("""
                UPDATE papers SET
                    fulltext_status = ?,
                    fulltext_path = COALESCE(NULLIF(?, ''), fulltext_path),
                    token_estimate = ?,
                    fetched_at = COALESCE(?, fetched_at)
                WHERE id = ?
            """, (status, fulltext_path, token_estimate, fetched_at, paper_id))
            self._conn.commit()

    def mark_claims_extracted(self, paper_id: int):
        with self._write_lock:
            self._conn.execute(
                "UPDATE papers SET claims_extracted = 1 WHERE id = ?",
                (paper_id,)
            )
            self._conn.commit()

    def mark_verified(self, paper_id: int, verified: bool = True):
        with self._write_lock:
            self._conn.execute(
                "UPDATE papers SET verified = ? WHERE id = ?",
                (1 if verified else 0, paper_id)
            )
            self._conn.commit()

    # ══════════════════════════════════════
    # search_log — 搜索缓存
    # ══════════════════════════════════════

    def search_cache_hit(self, query: str, source: str) -> Optional[List[Dict]]:
        """
        查搜索缓存。命中返回论文列表，未命中返回 None。
        过期的缓存自动失效。
        """
        query_norm = _normalize_query(query)
        with self._write_lock:
            row = self._conn.execute("""
                SELECT results_json, expires_at FROM search_log
                WHERE query_norm = ? AND source = ?
            """, (query_norm, source)).fetchone()

        if not row:
            return None

        # 检查过期
        if row["expires_at"]:
            try:
                expires = datetime.fromisoformat(row["expires_at"])
                if datetime.now() > expires:
                    return None  # 过期
            except (ValueError, TypeError):
                pass

        try:
            return json.loads(row["results_json"])
        except (json.JSONDecodeError, TypeError):
            return None

    def log_search(self, query: str, source: str, results: List[Dict],
                   ttl_days: int = 7):
        """记录搜索结果到缓存"""
        query_norm = _normalize_query(query)
        expires = (datetime.now() + timedelta(days=ttl_days)).isoformat()
        results_json = json.dumps(results, ensure_ascii=False)
        doi_list = json.dumps([
            p.get("doi", "") for p in results if p.get("doi")
        ])

        with self._write_lock:
            self._conn.execute("""
                INSERT OR REPLACE INTO search_log
                    (query, query_norm, source, results_json, result_count,
                     hit_doi_list, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (query, query_norm, source, results_json,
                  len(results), doi_list, expires))
            self._conn.commit()

    def cleanup_expired_cache(self):
        """清理过期搜索缓存"""
        with self._write_lock:
            self._conn.execute(
                "DELETE FROM search_log WHERE expires_at < ?",
                (datetime.now().isoformat(),)
            )
            self._conn.commit()

    # ══════════════════════════════════════
    # claims — Claim 提取结果
    # ══════════════════════════════════════

    def add_claims(self, paper_id: int, claims: List[Dict]):
        """为一篇论文添加 claims"""
        with self._write_lock:
            for c in claims:
                self._conn.execute("""
                    INSERT INTO claims (paper_id, claim_text, technique)
                    VALUES (?, ?, ?)
                """, (paper_id,
                      c.get("claim", c.get("claim_text", "")),
                      c.get("technique", "")))
            self._conn.execute(
                "UPDATE papers SET claims_extracted = 1 WHERE id = ?",
                (paper_id,)
            )
            self._conn.commit()

    def get_all_claims(self) -> List[Dict]:
        """获取所有 claims"""
        with self._write_lock:
            rows = self._conn.execute("""
                SELECT c.id, c.claim_text, c.technique,
                       p.title, p.year, p.doi AS paper_id_str, p.id AS paper_db_id
                FROM claims c JOIN papers p ON c.paper_id = p.id
                ORDER BY p.relevance_score DESC
            """).fetchall()
        return [dict(r) for r in rows]

    def get_claims_for_paper(self, paper_id: int) -> List[Dict]:
        with self._write_lock:
            rows = self._conn.execute(
                "SELECT * FROM claims WHERE paper_id = ?", (paper_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    # ══════════════════════════════════════
    # citations — 引用解析
    # ══════════════════════════════════════

    def upsert_citation(self, chapter_num: int, citation_tag: str,
                        paper_id: int = None, cite_num: int = None,
                        bib_key: str = None, verified: bool = False,
                        reason: str = "") -> int:
        """插入或更新引用条目"""
        with self._write_lock:
            existing = self._conn.execute("""
                SELECT id FROM citations
                WHERE chapter_num = ? AND citation_tag = ?
            """, (chapter_num, citation_tag)).fetchone()

            if existing:
                self._conn.execute("""
                    UPDATE citations SET
                        paper_id = COALESCE(?, paper_id),
                        cite_num = COALESCE(?, cite_num),
                        bib_key = COALESCE(?, bib_key),
                        verified = ?,
                        verified_reason = COALESCE(?, verified_reason)
                    WHERE id = ?
                """, (paper_id, cite_num, bib_key,
                      1 if verified else 0, reason, existing["id"]))
                self._conn.commit()
                return existing["id"]
            else:
                cur = self._conn.execute("""
                    INSERT INTO citations
                        (chapter_num, citation_tag, paper_id, cite_num,
                         bib_key, verified, verified_reason)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (chapter_num, citation_tag, paper_id, cite_num,
                      bib_key, 1 if verified else 0, reason))
                self._conn.commit()
                return cur.lastrowid

    def get_citation_map(self) -> Dict[int, str]:
        """获取 {cite_num: bib_key} 映射"""
        with self._write_lock:
            rows = self._conn.execute("""
                SELECT cite_num, bib_key FROM citations
                WHERE cite_num IS NOT NULL AND bib_key IS NOT NULL
                ORDER BY cite_num
            """).fetchall()
        return {r["cite_num"]: r["bib_key"] for r in rows}

    def get_citation_entries(self) -> List[Dict]:
        """获取编号后的引用条目（用于导出 references.md）"""
        with self._write_lock:
            rows = self._conn.execute("""
                SELECT c.*, p.title, p.year, p.authors, p.venue, p.doi
                FROM citations c
                LEFT JOIN papers p ON c.paper_id = p.id
                WHERE c.cite_num IS NOT NULL
                ORDER BY c.cite_num
            """).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                d["authors"] = _json_to_authors(d.get("authors", "[]"))
                results.append(d)
        return results

    def get_next_cite_num(self) -> int:
        """获取下一个可用引用编号"""
        with self._write_lock:
            row = self._conn.execute(
                "SELECT MAX(cite_num) as max_num FROM citations"
            ).fetchone()
        return (row["max_num"] or 0) + 1

    def get_unresolved_citations(self) -> List[Dict]:
        """获取未匹配论文的引用"""
        with self._write_lock:
            rows = self._conn.execute("""
                SELECT * FROM citations
                WHERE paper_id IS NULL OR verified = 0
            """).fetchall()
        return [dict(r) for r in rows]

    # ══════════════════════════════════════
    # tasks — 子 Agent 任务队列
    # ══════════════════════════════════════

    def claim_tasks(self, task_type: str, agent: str,
                    limit: int = 10) -> List[Dict]:
        """
        原子性地领取任务。用写锁保证同一个任务不会被两个 agent 领取。
        """
        with self._write_lock:
            rows = self._conn.execute("""
                SELECT * FROM tasks
                WHERE task_type = ? AND status = 'pending'
                ORDER BY id
                LIMIT ?
            """, (task_type, limit)).fetchall()

            task_ids = [r["id"] for r in rows]
            if task_ids:
                placeholders = ','.join('?' * len(task_ids))
                self._conn.execute(f"""
                    UPDATE tasks SET status = 'running', agent = ?,
                                     started_at = datetime('now')
                    WHERE id IN ({placeholders})
                """, [agent] + task_ids)
                self._conn.commit()

            return [dict(r) for r in rows]

    def complete_task(self, task_id: int, summary: str = "", error: str = ""):
        """完成任务"""
        with self._write_lock:
            status = "done" if not error else "failed"
            self._conn.execute("""
                UPDATE tasks SET status = ?, result_summary = ?,
                                 error = ?, completed_at = datetime('now')
                WHERE id = ?
            """, (status, summary, error, task_id))
            self._conn.commit()

    def create_tasks(self, task_type: str, params_list: List[Dict]) -> int:
        """批量创建任务，返回创建数量"""
        with self._write_lock:
            for params in params_list:
                self._conn.execute("""
                    INSERT INTO tasks (task_type, params)
                    VALUES (?, ?)
                """, (task_type, json.dumps(params, ensure_ascii=False)))
            self._conn.commit()
        return len(params_list)

    def create_paper_tasks(self, task_type: str, paper_ids: List[int],
                           extra_params: Dict = None):
        """为一组论文创建任务"""
        with self._write_lock:
            for pid in paper_ids:
                params = {"paper_id": pid}
                if extra_params:
                    params.update(extra_params)
                self._conn.execute("""
                    INSERT INTO tasks (task_type, paper_id, params)
                    VALUES (?, ?, ?)
                """, (task_type, pid, json.dumps(params, ensure_ascii=False)))
            self._conn.commit()

    def get_task_stats(self) -> Dict:
        """获取任务统计"""
        with self._write_lock:
            rows = self._conn.execute("""
                SELECT task_type, status, COUNT(*) as cnt
                FROM tasks GROUP BY task_type, status
            """).fetchall()
            stats = {}
            for r in rows:
                key = f"{r['task_type']}:{r['status']}"
                stats[key] = r["cnt"]
        return stats

    # ══════════════════════════════════════
    # 导出接口（生成最终产物）
    # ══════════════════════════════════════

    def export_reference_pool(self) -> Dict:
        """导出为旧格式 reference_pool.json（兼容过渡）"""
        papers = self.get_all_papers(limit=200)
        return {"total": len(papers), "papers": papers}

    def export_citation_bank(self) -> Dict:
        """导出为旧格式 citation_bank.json（兼容过渡）"""
        claims = self.get_all_claims()
        pool_size = self.get_paper_count()
        formatted = []
        for c in claims:
            formatted.append({
                "claim": c["claim_text"],
                "paper_id": c.get("doi", "") or str(c.get("paper_db_id", "")),
                "title": c.get("title", ""),
                "year": c.get("year"),
            })
        return {"claims": formatted, "pool_size": pool_size}

    def export_references_md(self) -> str:
        """生成 references.md 格式化文本"""
        entries = self.get_citation_entries()
        if not entries:
            return "# References\n\n*No references verified.*\n"
        lines = ["# References\n"]
        for e in entries:
            authors = e.get("authors", [])
            author_names = [a.get("name", "") for a in authors if a.get("name")]
            author_str = ", ".join(author_names[:3])
            if len(author_names) > 3:
                author_str += " et al."
            title = e.get("title", "")
            venue = e.get("venue", "")
            year = e.get("year", "")
            entry = f"[{e['cite_num']}] {author_str}, \"{title},\" "
            if venue:
                entry += f"{venue}, "
            if year:
                entry += f"{year}."
            lines.append(entry)
            lines.append("")
        return "\n".join(lines)

    def export_bibtex(self) -> Tuple[str, Dict[int, str]]:
        """
        从 citations 表生成 BibTeX 内容 + citation_map。
        返回 (bib_content, {cite_num: bib_key})
        """
        entries = self.get_citation_entries()
        bib_entries = []
        citation_map = {}

        for e in entries:
            cite_num = e["cite_num"]
            title = e.get("title", "")
            if not title:
                continue

            # 生成 bib_key
            authors = e.get("authors", [])
            year = e.get("year", "")
            bib_key = self._generate_bib_key(authors, year, title, cite_num)

            # 确定 entry type
            venue = e.get("venue", "")
            entry_type = "inproceedings" if any(
                kw in str(venue).lower()
                for kw in ["cvpr", "iccv", "eccv", "neurips", "icml",
                           "aaai", "iclr", "siggraph"]
            ) else "article"

            author_names = [a.get("name", "") for a in authors]
            author_str = " and ".join(a for a in author_names if a)

            lines = [f"@{entry_type}{{{bib_key},"]
            lines.append(f"  title={{{title}}},")
            if author_str:
                lines.append(f"  author={{{author_str}}},")
            if year:
                lines.append(f"  year={{{year}}},")
            if venue:
                key = "booktitle" if entry_type == "inproceedings" else "journal"
                lines.append(f"  {key}={{{venue}}},")
            doi = e.get("doi", "")
            if doi:
                lines.append(f"  doi={{{doi}}},")
            lines.append("}")

            bib_entries.append("\n".join(lines))
            citation_map[cite_num] = bib_key

        bib_content = "\n\n".join(bib_entries)
        return bib_content, citation_map

    # ══════════════════════════════════════
    # 数据迁移：从旧 JSON 导入
    # ══════════════════════════════════════

    def import_reference_pool_json(self, json_path: str) -> int:
        """从旧 reference_pool.json 导入"""
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"[ReferenceStore] 导入失败: {json_path}: {e}")
            return 0

        papers = data if isinstance(data, list) else data.get("papers", [])
        return self.upsert_papers_batch(papers)

    def import_citation_bank_json(self, json_path: str) -> int:
        """从旧 citation_bank.json 导入 claims"""
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return 0

        claims = data.get("claims", [])
        count = 0
        for c in claims:
            paper_title = c.get("title", "")
            paper = self.find_paper_by_title(paper_title) if paper_title else None
            if paper:
                self.add_claims(paper["id"], [c])
                count += 1
        return count

    def import_offline_pack(self, pack_path: str) -> int:
        """从离线数据包 JSON 导入"""
        try:
            with open(pack_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return 0

        papers = data.get("papers", [])
        formatted = []
        for p in papers:
            formatted.append({
                "title": p.get("title", ""),
                "authors": p.get("authors", []),
                "year": p.get("year"),
                "venue": p.get("venue_abbr", p.get("venue", "")),
                "doi": p.get("doi", ""),
                "citation_count": p.get("citation_count", 0),
                "tags": p.get("tags", []),
                "_source": "pack",
            })
        return self.upsert_papers_batch(formatted)

    def import_ref_md_metadata(self, ref_md_dir: str) -> int:
        """扫描 ref_md/ 目录，导入 Markdown 文件的元数据"""
        if not os.path.isdir(ref_md_dir):
            return 0
        count = 0
        for fname in os.listdir(ref_md_dir):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(ref_md_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read(2000)  # 只读前 2KB 获取 frontmatter
                # 解析 YAML frontmatter
                meta = self._parse_md_frontmatter(content)
                if meta.get("title"):
                    paper = self.find_paper_by_title(meta["title"])
                    if paper:
                        self.update_fulltext_status(
                            paper["id"], "fetched", fpath,
                            meta.get("token_estimate", 0))
                        count += 1
                    else:
                        # 全新论文，插入
                        pid = self.upsert_paper({
                            "title": meta["title"],
                            "authors": meta.get("authors", ""),
                            "year": str(meta.get("published", ""))[:4] if meta.get("published") else None,
                            "venue": meta.get("journal", ""),
                            "doi": meta.get("doi", ""),
                            "_source": "paper_fetch",
                        })
                        self.update_fulltext_status(
                            pid, "fetched", fpath,
                            meta.get("token_estimate", 0))
                        count += 1
            except Exception as e:
                logger.debug(f"[ReferenceStore] 跳过 {fname}: {e}")
        return count

    # ══════════════════════════════════════
    # 统计与诊断
    # ══════════════════════════════════════

    def get_stats(self) -> Dict:
        """获取整体统计"""
        paper_count = self.get_paper_count()
        with self._write_lock:
            claims_count = self._conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
            citations_count = self._conn.execute("SELECT COUNT(*) FROM citations").fetchone()[0]
            verified_count = self._conn.execute(
                "SELECT COUNT(*) FROM papers WHERE verified = 1"
            ).fetchone()[0]
            fetched_count = self._conn.execute(
                "SELECT COUNT(*) FROM papers WHERE fulltext_status = 'fetched'"
            ).fetchone()[0]
            claims_done = self._conn.execute(
                "SELECT COUNT(*) FROM papers WHERE claims_extracted = 1"
            ).fetchone()[0]
            cache_count = self._conn.execute("SELECT COUNT(*) FROM search_log").fetchone()[0]

        return {
            "papers": paper_count,
            "claims": claims_count,
            "citations": citations_count,
            "verified": verified_count,
            "fulltext_fetched": fetched_count,
            "claims_extracted": claims_done,
            "search_cache": cache_count,
        }

    # ══════════════════════════════════════
    # 内部方法
    # ══════════════════════════════════════

    def _paper_row_to_dict(self, row) -> Optional[Dict]:
        """将数据库行转换为兼容旧格式的 dict"""
        if row is None:
            return None
        d = dict(row)
        # 将 authors JSON 转为 [{name: "..."}] 格式（旧代码兼容）
        d["authors"] = _json_to_authors(d.get("authors", "[]"))
        # 添加旧字段别名
        d["paperId"] = d.get("doi", "") or str(d["id"])
        d["citationCount"] = d.get("citation_count", 0)
        d["externalIds"] = {"DOI": d.get("doi", "")} if d.get("doi") else {}
        d["markdown_path"] = d.get("fulltext_path", "")
        d["content_kind"] = "fulltext" if d.get("fulltext_status") == "fetched" else ""
        d["_relevance_score"] = d.get("relevance_score", 0)
        d["_source"] = d.get("source", "unknown")
        d["group"] = d.get("group_name", "")
        return d

    @staticmethod
    def _generate_bib_key(authors, year, title, num):
        """生成 cite key: 委托给公共 text_utils.generate_bib_key"""
        from tools.text_utils import generate_bib_key as _gen_key
        return _gen_key(authors, year, title, num)

    @staticmethod
    def _parse_md_frontmatter(content: str) -> Dict:
        """解析 Markdown YAML frontmatter"""
        meta = {}
        if not content.startswith("---"):
            return meta
        end = content.find("---", 3)
        if end < 0:
            return meta
        yaml_str = content[3:end].strip()
        for line in yaml_str.split("\n"):
            if ":" in line:
                key, _, val = line.partition(":")
                meta[key.strip()] = val.strip().strip('"').strip("'")
        return meta


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 全局单例
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_store_instance: Optional[ReferenceStore] = None
_store_lock = threading.Lock()


def get_reference_store(db_path: str = None) -> ReferenceStore:
    """
    获取全局 ReferenceStore 单例。

    首次调用需提供 db_path，后续调用自动复用。
    """
    global _store_instance
    if _store_instance is not None:
        return _store_instance

    with _store_lock:
        if _store_instance is not None:
            return _store_instance

        if db_path is None:
            try:
                from config.project_config import OUTPUT_DIR
                db_path = os.path.join(OUTPUT_DIR, "refs.db")
            except ImportError:
                db_path = os.path.join("output", "refs.db")

        _store_instance = ReferenceStore(db_path)
        return _store_instance


def reset_reference_store():
    """重置全局单例（测试用）"""
    global _store_instance
    with _store_lock:
        if _store_instance is not None:
            _store_instance.close()
            _store_instance = None


def init_reference_store_from_output(output_dir: str) -> ReferenceStore:
    """
    从 output/ 目录初始化，自动导入所有旧 JSON 数据。

    返回已就绪的 ReferenceStore。
    """
    db_path = os.path.join(output_dir, "refs.db")
    store = get_reference_store(db_path)

    stats = store.get_stats()
    if stats["papers"] > 0:
        logger.info(f"[ReferenceStore] 已有 {stats['papers']} 篇论文，跳过导入")
        return store

    logger.info("[ReferenceStore] 首次初始化，导入旧数据...")

    # 1. 离线数据包
    pack_dir = os.path.join(os.path.dirname(output_dir), "data", "reference_packs")
    if os.path.isdir(pack_dir):
        for fname in os.listdir(pack_dir):
            if fname.endswith(".json"):
                n = store.import_offline_pack(os.path.join(pack_dir, fname))
                logger.info(f"  离线数据包 {fname}: +{n} 篇")

    # 2. reference_pool.json
    pool_path = os.path.join(output_dir, "reference_pool.json")
    if os.path.exists(pool_path):
        n = store.import_reference_pool_json(pool_path)
        logger.info(f"  reference_pool.json: +{n} 篇")

    # 3. citation_bank.json
    bank_path = os.path.join(output_dir, "citation_bank.json")
    if os.path.exists(bank_path):
        n = store.import_citation_bank_json(bank_path)
        logger.info(f"  citation_bank.json: +{n} claims")

    # 4. ref_md/ 元数据
    ref_md_dir = os.path.join(os.path.dirname(output_dir), "ref_md")
    n = store.import_ref_md_metadata(ref_md_dir)
    logger.info(f"  ref_md/: +{n} 篇全文元数据")

    final_stats = store.get_stats()
    logger.info(f"[ReferenceStore] 导入完成: {final_stats}")

    return store
