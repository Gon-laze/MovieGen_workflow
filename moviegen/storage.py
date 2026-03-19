from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            project_file TEXT NOT NULL,
            requested_stage TEXT NOT NULL,
            dry_run INTEGER NOT NULL,
            status TEXT NOT NULL,
            notes TEXT,
            started_at TEXT NOT NULL,
            finished_at TEXT
        );

        CREATE TABLE IF NOT EXISTS stage_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            stage_name TEXT NOT NULL,
            status TEXT NOT NULL,
            attempt INTEGER NOT NULL DEFAULT 1,
            notes TEXT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            UNIQUE(run_id, stage_name, attempt)
        );

        CREATE TABLE IF NOT EXISTS generation_jobs (
            job_id TEXT PRIMARY KEY,
            shot_id TEXT,
            provider TEXT,
            provider_model TEXT,
            status TEXT NOT NULL,
            external_job_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS candidate_clips (
            candidate_clip_id TEXT PRIMARY KEY,
            job_id TEXT,
            shot_id TEXT,
            provider TEXT,
            artifact_path TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS judge_scores (
            judge_score_id TEXT PRIMARY KEY,
            candidate_clip_id TEXT,
            weighted_total_score REAL,
            decision TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS budget_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            provider TEXT,
            job_id TEXT,
            event_type TEXT NOT NULL,
            budget_class TEXT,
            estimated_cost_usd REAL,
            actual_cost_usd REAL,
            currency TEXT NOT NULL DEFAULT 'USD',
            notes TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS human_gates (
            gate_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            gate_name TEXT NOT NULL,
            status TEXT NOT NULL,
            reviewer TEXT,
            decision_summary TEXT,
            decision_payload TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS artifacts (
            artifact_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            artifact_type TEXT NOT NULL,
            artifact_path TEXT NOT NULL,
            source_stage TEXT NOT NULL,
            source_id TEXT,
            content_hash TEXT,
            file_size_bytes INTEGER,
            retention_policy TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )
    _ensure_column(conn, "generation_jobs", "packet_id", "TEXT")
    _ensure_column(conn, "generation_jobs", "provider_rank", "INTEGER")
    _ensure_column(conn, "generation_jobs", "selected_reason", "TEXT")
    _ensure_column(conn, "generation_jobs", "archetype", "TEXT")
    _ensure_column(conn, "generation_jobs", "grade", "TEXT")
    _ensure_column(conn, "generation_jobs", "budget_class", "TEXT")
    _ensure_column(conn, "generation_jobs", "estimated_cost_usd", "REAL")
    _ensure_column(conn, "generation_jobs", "queue_policy", "TEXT")
    _ensure_column(conn, "generation_jobs", "fallback_chain", "TEXT")
    conn.commit()


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def insert_run(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    project_id: str,
    project_file: str,
    requested_stage: str,
    dry_run: bool,
    status: str,
    notes: str,
    started_at: str,
) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO runs
        (run_id, project_id, project_file, requested_stage, dry_run, status, notes, started_at, finished_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT finished_at FROM runs WHERE run_id = ?), NULL))
        """,
        (run_id, project_id, project_file, requested_stage, int(dry_run), status, notes, started_at, run_id),
    )
    conn.commit()


def complete_run(conn: sqlite3.Connection, run_id: str, status: str, notes: str, finished_at: str) -> None:
    conn.execute(
        "UPDATE runs SET status = ?, notes = ?, finished_at = ? WHERE run_id = ?",
        (status, notes, finished_at, run_id),
    )
    conn.commit()


def insert_stage_run(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    stage_name: str,
    status: str,
    notes: str,
    started_at: str,
    finished_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO stage_runs (run_id, stage_name, status, notes, started_at, finished_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (run_id, stage_name, status, notes, started_at, finished_at),
    )
    conn.commit()


def insert_artifact(
    conn: sqlite3.Connection,
    *,
    artifact_id: str,
    run_id: str,
    artifact_type: str,
    artifact_path: str,
    source_stage: str,
    source_id: str | None,
    content_hash: str | None,
    file_size_bytes: int,
    retention_policy: str,
    created_at: str,
) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO artifacts
        (artifact_id, run_id, artifact_type, artifact_path, source_stage, source_id, content_hash, file_size_bytes, retention_policy, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            artifact_id,
            run_id,
            artifact_type,
            artifact_path,
            source_stage,
            source_id,
            content_hash,
            file_size_bytes,
            retention_policy,
            created_at,
        ),
    )
    conn.commit()


def fetch_run(conn: sqlite3.Connection, run_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()


def fetch_stage_runs(conn: sqlite3.Connection, run_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM stage_runs WHERE run_id = ? ORDER BY id",
        (run_id,),
    ).fetchall()


def list_runs(conn: sqlite3.Connection, limit: int = 20) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?",
        (limit,),
    ).fetchall()


def upsert_human_gate(
    conn: sqlite3.Connection,
    *,
    gate_id: str,
    run_id: str,
    gate_name: str,
    status: str,
    reviewer: str | None,
    decision_summary: str | None,
    decision_payload: str | None,
    created_at: str,
    updated_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO human_gates
        (gate_id, run_id, gate_name, status, reviewer, decision_summary, decision_payload, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(gate_id) DO UPDATE SET
            status = excluded.status,
            reviewer = excluded.reviewer,
            decision_summary = excluded.decision_summary,
            decision_payload = excluded.decision_payload,
            updated_at = excluded.updated_at
        """,
        (
            gate_id,
            run_id,
            gate_name,
            status,
            reviewer,
            decision_summary,
            decision_payload,
            created_at,
            updated_at,
        ),
    )
    conn.commit()


def fetch_human_gates(conn: sqlite3.Connection, run_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM human_gates WHERE run_id = ? ORDER BY created_at, gate_name",
        (run_id,),
    ).fetchall()


def fetch_artifacts(conn: sqlite3.Connection, run_id: str | None = None) -> list[sqlite3.Row]:
    if run_id is None:
        return conn.execute("SELECT * FROM artifacts ORDER BY created_at").fetchall()
    return conn.execute(
        "SELECT * FROM artifacts WHERE run_id = ? ORDER BY created_at",
        (run_id,),
    ).fetchall()


def delete_artifact_rows(conn: sqlite3.Connection, artifact_ids: list[str]) -> None:
    if not artifact_ids:
        return
    conn.executemany("DELETE FROM artifacts WHERE artifact_id = ?", [(artifact_id,) for artifact_id in artifact_ids])
    conn.commit()


def upsert_generation_job(
    conn: sqlite3.Connection,
    *,
    job_id: str,
    shot_id: str,
    packet_id: str | None,
    provider: str,
    provider_model: str,
    provider_rank: int | None,
    selected_reason: str | None,
    archetype: str | None,
    grade: str | None,
    budget_class: str | None,
    estimated_cost_usd: float | None,
    queue_policy: str | None,
    fallback_chain: str | None,
    status: str,
    external_job_id: str | None,
    created_at: str,
    updated_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO generation_jobs
        (job_id, shot_id, packet_id, provider, provider_model, provider_rank, selected_reason, archetype, grade, budget_class, estimated_cost_usd, queue_policy, fallback_chain, status, external_job_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(job_id) DO UPDATE SET
            packet_id = excluded.packet_id,
            status = excluded.status,
            external_job_id = excluded.external_job_id,
            provider_rank = excluded.provider_rank,
            selected_reason = excluded.selected_reason,
            archetype = excluded.archetype,
            grade = excluded.grade,
            budget_class = excluded.budget_class,
            estimated_cost_usd = excluded.estimated_cost_usd,
            queue_policy = excluded.queue_policy,
            fallback_chain = excluded.fallback_chain,
            updated_at = excluded.updated_at
        """,
        (
            job_id,
            shot_id,
            packet_id,
            provider,
            provider_model,
            provider_rank,
            selected_reason,
            archetype,
            grade,
            budget_class,
            estimated_cost_usd,
            queue_policy,
            fallback_chain,
            status,
            external_job_id,
            created_at,
            updated_at,
        ),
    )
    conn.commit()


def row_to_dict(row: sqlite3.Row) -> dict[str, object]:
    return {key: row[key] for key in row.keys()}


def payload_to_json(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)
