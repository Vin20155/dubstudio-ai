"""
SQLite Storage Layer for Multi-Provider Translation Engine.
Stores project settings, user AI settings, translation memory, glossaries, jobs, and audit logs.
"""

import json
import logging
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import DATA_DIR

logger = logging.getLogger("translation_db")
DB_PATH = DATA_DIR / "translation.db"


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=30000;")
    except Exception:
        pass
    return conn


def init_db():
    """Initializes the database schema with proper indexes."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 1. User AI settings table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_ai_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT UNIQUE NOT NULL,
                translation_provider TEXT DEFAULT 'gemini',
                translation_model TEXT DEFAULT 'gemini-3.5-flash',
                fallback_provider TEXT DEFAULT 'openai',
                fallback_enabled INTEGER DEFAULT 1,
                translation_options TEXT,
                credentials TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        # 2. Project settings table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS project_translation_settings (
                project_id TEXT PRIMARY KEY,
                translation_provider TEXT,
                translation_model TEXT,
                source_language TEXT DEFAULT 'en',
                target_language TEXT DEFAULT 'km',
                style TEXT DEFAULT 'natural',
                translation_options TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        # 3. Translation Memory table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS translation_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT DEFAULT 'default_user',
                project_id TEXT,
                source_language TEXT NOT NULL,
                target_language TEXT NOT NULL,
                source_text TEXT NOT NULL,
                translated_text TEXT NOT NULL,
                provider TEXT,
                use_count INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(source_language, target_language, source_text)
            );
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_tm_lookup 
            ON translation_memory(source_language, target_language, source_text);
            """
        )

        # 4. Project Glossary table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS project_glossaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT DEFAULT 'global',
                source_term TEXT NOT NULL,
                target_term TEXT NOT NULL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(project_id, source_term)
            );
            """
        )

        # 5. Translation Jobs table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS translation_jobs (
                id TEXT PRIMARY KEY,
                project_id TEXT,
                user_id TEXT DEFAULT 'default_user',
                provider TEXT,
                model TEXT,
                status TEXT DEFAULT 'queued',
                total_segments INTEGER DEFAULT 0,
                completed_segments INTEGER DEFAULT 0,
                failed_segments INTEGER DEFAULT 0,
                progress INTEGER DEFAULT 0,
                error_message TEXT,
                status_message TEXT,
                current_segment_idx INTEGER DEFAULT 0,
                current_segment_text TEXT,
                segments_data TEXT,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        # Safe migrations for existing DBs that don't have the newer columns
        for col, col_def in [
            ("status_message", "TEXT"),
            ("current_segment_idx", "INTEGER DEFAULT 0"),
            ("current_segment_text", "TEXT"),
        ]:
            try:
                conn.execute(f"ALTER TABLE translation_jobs ADD COLUMN {col} {col_def};")
                conn.commit()
            except Exception:
                pass  # Column already exists — that's fine

        # 6. Translation Logs (audit & stats)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS translation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT DEFAULT 'default_user',
                project_id TEXT,
                provider TEXT NOT NULL,
                model TEXT,
                source_language TEXT,
                target_language TEXT,
                segments_count INTEGER DEFAULT 0,
                tokens_used INTEGER DEFAULT 0,
                duration_ms INTEGER DEFAULT 0,
                status TEXT NOT NULL,
                error_code TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        # Insert default user settings if none exist
        cursor.execute("SELECT id FROM user_ai_settings WHERE user_id = 'default_user';")
        if not cursor.fetchone():
            cursor.execute(
                """
                INSERT INTO user_ai_settings (
                    user_id, translation_provider, translation_model, fallback_provider, fallback_enabled, translation_options
                ) VALUES (
                    'default_user', 'gemini', 'gemini-3.5-flash', 'openai', 1, ?
                );
                """,
                (json.dumps({
                    "style": "natural",
                    "use_context": True,
                    "preserve_speaker_personality": True,
                    "optimize_for_dubbing": True,
                    "use_translation_memory": True,
                    "use_glossary": True,
                    "enable_fallback": True
                }),)
            )

        # Insert helpful default glossary terms if empty
        cursor.execute("SELECT COUNT(*) as cnt FROM project_glossaries WHERE project_id = 'global';")
        row = cursor.fetchone()
        if row and row["cnt"] == 0:
            defaults = [
                ("AI", "បញ្ញាសិប្បនិម្មិត", "Artificial Intelligence standard Khmer term"),
                ("Server", "ម៉ាស៊ីនមេ", "Server computer"),
                ("Database", "មូលដ្ឋានទិន្នន័យ", "Database system"),
                ("Login", "ចូលប្រព័ន្ធ", "User sign-in"),
                ("Dashboard", "ផ្ទាំងគ្រប់គ្រង", "Admin dashboard panel"),
            ]
            cursor.executemany(
                "INSERT INTO project_glossaries (project_id, source_term, target_term, notes) VALUES ('global', ?, ?, ?);",
                defaults
            )

        # Auto-sync saved Gemini key to .env if available in database
        try:
            cursor.execute("SELECT credentials FROM user_ai_settings WHERE user_id = 'default_user';")
            row = cursor.fetchone()
            if row and row["credentials"]:
                creds = json.loads(row["credentials"])
                saved_key = creds.get("gemini_api_key") or creds.get("api_key")
                if saved_key:
                    from ..config import persist_env_key
                    persist_env_key("GEMINI_API_KEY", saved_key)
        except Exception:
            pass

        conn.commit()
    logger.info("Translation database initialized successfully at %s", DB_PATH)


# Initialize DB immediately on module import
init_db()


# --- User AI Settings Helpers ---

def get_user_ai_settings(user_id: str = "default_user") -> Dict[str, Any]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_ai_settings WHERE user_id = ?;", (user_id,))
        row = cursor.fetchone()
        if row:
            options = json.loads(row["translation_options"]) if row["translation_options"] else {}
            creds = json.loads(row["credentials"]) if row["credentials"] else {}
            env_gemini = os.environ.get("GEMINI_API_KEY")
            if not creds.get("gemini_api_key") and env_gemini:
                creds["gemini_api_key"] = env_gemini
                creds["api_key"] = env_gemini
            elif creds.get("gemini_api_key") and not os.environ.get("GEMINI_API_KEY"):
                os.environ["GEMINI_API_KEY"] = creds["gemini_api_key"]

            p = row["translation_provider"] or "gemini"
            m = row["translation_model"] or "gemini-3.5-flash"
            return {
                "user_id": row["user_id"],
                "provider": p,
                "model": m,
                "translation_provider": p,
                "translation_model": m,
                "fallback_provider": row["fallback_provider"] or "openai",
                "fallback_enabled": bool(row["fallback_enabled"]),
                "options": options,
                "credentials": creds,
            }
        env_gemini = os.environ.get("GEMINI_API_KEY", "")
        default_creds = {"gemini_api_key": env_gemini, "api_key": env_gemini} if env_gemini else {}
        return {
            "user_id": user_id,
            "provider": "gemini",
            "model": "gemini-3.5-flash",
            "translation_provider": "gemini",
            "translation_model": "gemini-3.5-flash",
            "fallback_provider": "openai",
            "fallback_enabled": True,
            "options": {},
            "credentials": default_creds,
        }


def save_user_ai_settings(
    user_id: str = "default_user",
    provider: Optional[str] = None,
    model: Optional[str] = None,
    fallback_provider: Optional[str] = None,
    fallback_enabled: Optional[bool] = None,
    options: Optional[Dict[str, Any]] = None,
    credentials: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    current = get_user_ai_settings(user_id)
    new_provider = provider if provider is not None else current["translation_provider"]
    new_model = model if model is not None else current["translation_model"]
    new_fallback_provider = fallback_provider if fallback_provider is not None else current["fallback_provider"]
    new_fallback_enabled = fallback_enabled if fallback_enabled is not None else current["fallback_enabled"]
    new_options = {**current["options"], **(options or {})}
    new_creds = {**current["credentials"]}
    if credentials is not None:
        for k, v in credentials.items():
            if v:
                new_creds[k] = v
            elif k in new_creds and (v is None or v == "__DELETE__"):
                del new_creds[k]

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO user_ai_settings (
                user_id, translation_provider, translation_model, fallback_provider, fallback_enabled, translation_options, credentials, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                translation_provider = excluded.translation_provider,
                translation_model = excluded.translation_model,
                fallback_provider = excluded.fallback_provider,
                fallback_enabled = excluded.fallback_enabled,
                translation_options = excluded.translation_options,
                credentials = excluded.credentials,
                updated_at = CURRENT_TIMESTAMP;
            """,
            (
                user_id,
                new_provider,
                new_model,
                new_fallback_provider,
                1 if new_fallback_enabled else 0,
                json.dumps(new_options),
                json.dumps(new_creds),
            ),
        )
        conn.commit()

    return get_user_ai_settings(user_id)


# --- Project Settings Helpers ---

def get_project_settings(project_id: str) -> Dict[str, Any]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM project_translation_settings WHERE project_id = ?;", (project_id,))
        row = cursor.fetchone()
        if row:
            opts = json.loads(row["translation_options"]) if row["translation_options"] else {}
            p = row["translation_provider"]
            m = row["translation_model"]
            return {
                "project_id": row["project_id"],
                "provider": p,
                "model": m,
                "translation_provider": p,
                "translation_model": m,
                "source_language": row["source_language"] or "en",
                "target_language": row["target_language"] or "km",
                "style": row["style"] or "natural",
                "options": opts,
            }
        return {}


def save_project_settings(
    project_id: str,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    source_language: str = "en",
    target_language: str = "km",
    style: str = "natural",
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    current = get_project_settings(project_id)
    new_provider = provider if provider is not None else current.get("translation_provider")
    new_model = model if model is not None else current.get("translation_model")
    new_opts = {**(current.get("options") or {}), **(options or {})}

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO project_translation_settings (
                project_id, translation_provider, translation_model, source_language, target_language, style, translation_options, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(project_id) DO UPDATE SET
                translation_provider = excluded.translation_provider,
                translation_model = excluded.translation_model,
                source_language = excluded.source_language,
                target_language = excluded.target_language,
                style = excluded.style,
                translation_options = excluded.translation_options,
                updated_at = CURRENT_TIMESTAMP;
            """,
            (project_id, new_provider, new_model, source_language, target_language, style, json.dumps(new_opts)),
        )
        conn.commit()

    return get_project_settings(project_id)


def resolve_effective_settings(project_id: Optional[str] = None, user_id: str = "default_user") -> Dict[str, Any]:
    """
    Resolves settings using the required priority order:
    1. Project Setting
    2. User Setting
    3. System Default ('gemini')
    """
    user_settings = get_user_ai_settings(user_id)
    project_settings = get_project_settings(project_id) if project_id else {}

    provider = (
        project_settings.get("translation_provider")
        or user_settings.get("translation_provider")
        or "gemini"
    )
    model = (
        project_settings.get("translation_model")
        or user_settings.get("translation_model")
        or ("gemini-3.5-flash" if provider == "gemini" else "")
    )
    style = project_settings.get("style") or user_settings.get("options", {}).get("style") or "natural"
    source_lang = project_settings.get("source_language") or "en"
    target_lang = project_settings.get("target_language") or "km"

    options = {
        **user_settings.get("options", {}),
        **(project_settings.get("options") or {}),
        "style": style,
        "fallback_provider": user_settings.get("fallback_provider", "openai"),
        "enable_fallback": user_settings.get("fallback_enabled", True),
    }

    return {
        "provider": provider,
        "model": model,
        "source_language": source_lang,
        "target_language": target_lang,
        "style": style,
        "options": options,
        "credentials": user_settings.get("credentials", {}),
    }


# --- Translation Memory Helpers ---

def lookup_translation_memory(source_text: str, source_lang: str = "en", target_lang: str = "km") -> Optional[str]:
    cleaned = source_text.strip()
    if not cleaned:
        return None
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT translated_text FROM translation_memory 
            WHERE source_language = ? AND target_language = ? AND source_text = ?;
            """,
            (source_lang, target_lang, cleaned),
        )
        row = cursor.fetchone()
        if row:
            # Increment use count
            cursor.execute(
                """
                UPDATE translation_memory 
                SET use_count = use_count + 1, updated_at = CURRENT_TIMESTAMP
                WHERE source_language = ? AND target_language = ? AND source_text = ?;
                """,
                (source_lang, target_lang, cleaned),
            )
            conn.commit()
            return row["translated_text"]
    return None


def store_translation_memory(
    source_text: str,
    translated_text: str,
    source_lang: str = "en",
    target_lang: str = "km",
    provider: str = "gemini",
    project_id: Optional[str] = None,
    user_id: str = "default_user",
):
    s_clean = source_text.strip()
    t_clean = translated_text.strip()
    if not s_clean or not t_clean or s_clean == t_clean:
        return

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO translation_memory (
                user_id, project_id, source_language, target_language, source_text, translated_text, provider, use_count, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(source_language, target_language, source_text) DO UPDATE SET
                translated_text = excluded.translated_text,
                provider = excluded.provider,
                use_count = translation_memory.use_count + 1,
                updated_at = CURRENT_TIMESTAMP;
            """,
            (user_id, project_id, source_lang, target_lang, s_clean, t_clean, provider),
        )
        conn.commit()


def list_translation_memory(limit: int = 100) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, source_language, target_language, source_text, translated_text, provider, use_count, created_at, updated_at
            FROM translation_memory
            ORDER BY updated_at DESC LIMIT ?;
            """,
            (limit,),
        )
        return [dict(r) for r in cursor.fetchall()]


def delete_translation_memory(item_id: int) -> bool:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM translation_memory WHERE id = ?;", (item_id,))
        conn.commit()
        return cursor.rowcount > 0


# --- Project Glossary Helpers ---

def get_project_glossary_map(project_id: Optional[str] = None) -> Dict[str, str]:
    """Returns a dict mapping source terms to their target Khmer translations."""
    glossary = {}
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Fetch global terms first
        cursor.execute("SELECT source_term, target_term FROM project_glossaries WHERE project_id = 'global';")
        for r in cursor.fetchall():
            glossary[r["source_term"].strip()] = r["target_term"].strip()

        # Overlay project-specific terms
        if project_id and project_id != "global":
            cursor.execute("SELECT source_term, target_term FROM project_glossaries WHERE project_id = ?;", (project_id,))
            for r in cursor.fetchall():
                glossary[r["source_term"].strip()] = r["target_term"].strip()

    return glossary


def list_glossary_terms(project_id: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if project_id:
            cursor.execute(
                "SELECT id, project_id, source_term, target_term, notes, created_at FROM project_glossaries WHERE project_id IN ('global', ?) ORDER BY id DESC;",
                (project_id,)
            )
        else:
            cursor.execute(
                "SELECT id, project_id, source_term, target_term, notes, created_at FROM project_glossaries ORDER BY id DESC;"
            )
        return [dict(r) for r in cursor.fetchall()]


def add_glossary_term(project_id: str, source_term: str, target_term: str, notes: str = "") -> Dict[str, Any]:
    s = source_term.strip()
    t = target_term.strip()
    if not s or not t:
        raise ValueError("Source term and target term cannot be empty")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO project_glossaries (project_id, source_term, target_term, notes)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(project_id, source_term) DO UPDATE SET
                target_term = excluded.target_term,
                notes = excluded.notes;
            """,
            (project_id or "global", s, t, notes),
        )
        conn.commit()
        last_id = cursor.lastrowid
        if not last_id:
            cursor.execute("SELECT id FROM project_glossaries WHERE project_id = ? AND source_term = ?;", (project_id or "global", s))
            row = cursor.fetchone()
            last_id = row["id"] if row else None
        return {"id": last_id, "project_id": project_id, "source_term": s, "target_term": t, "notes": notes}


def delete_glossary_term(term_id: int) -> bool:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM project_glossaries WHERE id = ?;", (term_id,))
        conn.commit()
        return cursor.rowcount > 0


# --- Translation Job System ---

def create_translation_job(
    job_id: str,
    project_id: Optional[str],
    provider: str,
    model: str,
    total_segments: int,
    user_id: str = "default_user",
) -> Dict[str, Any]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO translation_jobs (
                id, project_id, user_id, provider, model, status, total_segments, completed_segments, failed_segments, progress, error_message, started_at, completed_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'processing', ?, 0, 0, 0, NULL, CURRENT_TIMESTAMP, NULL, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                project_id = excluded.project_id,
                user_id = excluded.user_id,
                provider = excluded.provider,
                model = excluded.model,
                status = 'processing',
                total_segments = excluded.total_segments,
                completed_segments = 0,
                failed_segments = 0,
                progress = 0,
                error_message = NULL,
                started_at = CURRENT_TIMESTAMP,
                completed_at = NULL,
                updated_at = CURRENT_TIMESTAMP;
            """,
            (job_id, project_id, user_id, provider, model, total_segments),
        )
        conn.commit()
    return get_translation_job(job_id)



def update_translation_job(
    job_id: str,
    status: Optional[str] = None,
    completed_segments: Optional[int] = None,
    failed_segments: Optional[int] = None,
    progress: Optional[int] = None,
    error_message: Optional[str] = None,
    status_message: Optional[str] = None,
    current_segment_idx: Optional[int] = None,
    current_segment_text: Optional[str] = None,
    segments_data: Optional[List[Dict[str, Any]]] = None,
):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        fields = ["updated_at = CURRENT_TIMESTAMP"]
        params = []

        if status is not None:
            fields.append("status = ?")
            params.append(status)
            if status in ["completed", "failed", "cancelled"]:
                fields.append("completed_at = CURRENT_TIMESTAMP")
        if completed_segments is not None:
            fields.append("completed_segments = ?")
            params.append(completed_segments)
        if failed_segments is not None:
            fields.append("failed_segments = ?")
            params.append(failed_segments)
        if progress is not None:
            fields.append("progress = ?")
            params.append(progress)
        if error_message is not None:
            fields.append("error_message = ?")
            params.append(error_message)
        if status_message is not None:
            fields.append("status_message = ?")
            params.append(status_message)
        if current_segment_idx is not None:
            fields.append("current_segment_idx = ?")
            params.append(current_segment_idx)
        if current_segment_text is not None:
            fields.append("current_segment_text = ?")
            params.append(current_segment_text)
        if segments_data is not None:
            fields.append("segments_data = ?")
            params.append(json.dumps(segments_data))

        params.append(job_id)
        query = f"UPDATE translation_jobs SET {', '.join(fields)} WHERE id = ?;"
        cursor.execute(query, params)
        conn.commit()


def get_translation_job(job_id: str) -> Optional[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM translation_jobs WHERE id = ?;", (job_id,))
        row = cursor.fetchone()
        if row:
            d = dict(row)
            if d.get("segments_data"):
                try:
                    d["segments"] = json.loads(d["segments_data"])
                except Exception:
                    d["segments"] = []
            else:
                d["segments"] = []
            return d
    return None


# --- Translation Logs & Admin Stats ---

def log_translation_run(
    provider: str,
    status: str,
    duration_ms: int,
    segments_count: int,
    model: str = "",
    source_language: str = "en",
    target_language: str = "km",
    error_code: Optional[str] = None,
    project_id: Optional[str] = None,
    user_id: str = "default_user",
):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO translation_logs (
                user_id, project_id, provider, model, source_language, target_language, segments_count, duration_ms, status, error_code
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                user_id,
                project_id,
                provider,
                model,
                source_language,
                target_language,
                segments_count,
                duration_ms,
                status,
                error_code,
            ),
        )
        conn.commit()


def get_admin_translation_stats() -> Dict[str, Any]:
    """Returns aggregate usage statistics for the admin dashboard."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Provider breakdown
        cursor.execute(
            """
            SELECT 
                provider,
                COUNT(*) as total_requests,
                SUM(segments_count) as total_segments,
                AVG(duration_ms) as avg_duration_ms,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as successful_requests,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_requests,
                SUM(CASE WHEN error_code = 'RATE_LIMIT' THEN 1 ELSE 0 END) as rate_limit_events
            FROM translation_logs
            GROUP BY provider;
            """
        )
        providers_stats = [dict(r) for r in cursor.fetchall()]

        # Totals
        cursor.execute(
            """
            SELECT 
                COUNT(*) as total_jobs,
                SUM(segments_count) as total_translated_segments,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as total_failures,
                AVG(duration_ms) as overall_avg_duration_ms
            FROM translation_logs;
            """
        )
        totals = dict(cursor.fetchone() or {})

        return {
            "totals": totals,
            "providers": providers_stats,
        }
