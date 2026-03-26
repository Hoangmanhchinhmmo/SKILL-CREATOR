"""
CRUD operations for all SQLite tables.
All functions accept optional conn parameter for transaction control.
"""

import datetime
from .database import get_connection


# =============================================================================
# ARTICLES
# =============================================================================

def create_article(topic: str, format: str, content: str, conn=None) -> int:
    """Insert a new article, return its id."""
    own_conn = conn is None
    if own_conn:
        conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO articles (topic, format, content) VALUES (?, ?, ?)",
            (topic, format, content),
        )
        if own_conn:
            conn.commit()
        return cursor.lastrowid
    finally:
        if own_conn:
            conn.close()


def update_article_titles(article_id: int, titles: str):
    """Update article titles (JSON list of suggested titles)."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE articles SET titles = ?, updated_at = ? WHERE id = ?",
            (titles, datetime.datetime.now().isoformat(), article_id),
        )
        conn.commit()
    finally:
        conn.close()


def update_article_content(article_id: int, content: str):
    """Update article content and updated_at timestamp."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE articles SET content = ?, updated_at = ? WHERE id = ?",
            (content, datetime.datetime.now().isoformat(), article_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_article(article_id: int) -> dict | None:
    """Get a single article by id."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_articles(search: str = "", format_filter: str = "", status_filter: str = "",
                  sort: str = "newest", page: int = 1, per_page: int = 20) -> tuple[list[dict], int]:
    """List articles with search, filter, sort, pagination.
    Returns (articles, total_count).
    """
    conn = get_connection()
    try:
        where_clauses = []
        params = []

        if search:
            where_clauses.append("a.topic LIKE ?")
            params.append(f"%{search}%")

        if format_filter:
            where_clauses.append("a.format = ?")
            params.append(format_filter)

        if status_filter:
            where_clauses.append("pr.status = ?")
            params.append(status_filter)

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        sort_map = {
            "newest": "a.created_at DESC",
            "oldest": "a.created_at ASC",
            "duration": "pr.total_time DESC",
        }
        order_sql = sort_map.get(sort, "a.created_at DESC")

        # Count total
        count_sql = f"""
            SELECT COUNT(*) FROM articles a
            LEFT JOIN pipeline_runs pr ON pr.article_id = a.id
            {where_sql}
        """
        total = conn.execute(count_sql, params).fetchone()[0]

        # Fetch page
        offset = (page - 1) * per_page
        query_sql = f"""
            SELECT a.*, pr.status as run_status, pr.total_time
            FROM articles a
            LEFT JOIN pipeline_runs pr ON pr.article_id = a.id
            {where_sql}
            ORDER BY {order_sql}
            LIMIT ? OFFSET ?
        """
        rows = conn.execute(query_sql, params + [per_page, offset]).fetchall()
        return [dict(r) for r in rows], total
    finally:
        conn.close()


def delete_article(article_id: int):
    """Delete an article and its related pipeline runs."""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM pipeline_runs WHERE article_id = ?", (article_id,))
        conn.execute("DELETE FROM articles WHERE id = ?", (article_id,))
        conn.commit()
    finally:
        conn.close()


def get_recent_articles(limit: int = 5) -> list[dict]:
    """Get most recent articles for dashboard."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT a.*, pr.status as run_status, pr.total_time
               FROM articles a
               LEFT JOIN pipeline_runs pr ON pr.article_id = a.id
               ORDER BY a.created_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_article_count() -> int:
    conn = get_connection()
    try:
        return conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    finally:
        conn.close()


# =============================================================================
# PIPELINE RUNS
# =============================================================================

def create_pipeline_run(article_id: int = None) -> int:
    """Create a new pipeline run, return its id."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO pipeline_runs (article_id, status) VALUES (?, 'running')",
            (article_id,),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def update_pipeline_run(run_id: int, status: str = None, article_id: int = None,
                        finished_at: str = None, total_time: float = None):
    """Update pipeline run fields."""
    conn = get_connection()
    try:
        updates = []
        params = []
        if status:
            updates.append("status = ?")
            params.append(status)
        if article_id is not None:
            updates.append("article_id = ?")
            params.append(article_id)
        if finished_at:
            updates.append("finished_at = ?")
            params.append(finished_at)
        if total_time is not None:
            updates.append("total_time = ?")
            params.append(total_time)

        if updates:
            params.append(run_id)
            conn.execute(f"UPDATE pipeline_runs SET {', '.join(updates)} WHERE id = ?", params)
            conn.commit()
    finally:
        conn.close()


def get_pipeline_run(run_id: int) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM pipeline_runs WHERE id = ?", (run_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# =============================================================================
# AGENT LOGS
# =============================================================================

def create_agent_log(run_id: int, agent_name: str, status: str = "waiting") -> int:
    """Create a new agent log entry."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO agent_logs (run_id, agent_name, status) VALUES (?, ?, ?)",
            (run_id, agent_name, status),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def update_agent_log(log_id: int, status: str = None, attempt: int = None,
                     started_at: str = None, finished_at: str = None, error_msg: str = None):
    """Update agent log fields."""
    conn = get_connection()
    try:
        updates = []
        params = []
        if status:
            updates.append("status = ?")
            params.append(status)
        if attempt is not None:
            updates.append("attempt = ?")
            params.append(attempt)
        if started_at:
            updates.append("started_at = ?")
            params.append(started_at)
        if finished_at:
            updates.append("finished_at = ?")
            params.append(finished_at)
        if error_msg is not None:
            updates.append("error_msg = ?")
            params.append(error_msg)

        if updates:
            params.append(log_id)
            conn.execute(f"UPDATE agent_logs SET {', '.join(updates)} WHERE id = ?", params)
            conn.commit()
    finally:
        conn.close()


def get_agent_logs_for_run(run_id: int) -> list[dict]:
    """Get all agent logs for a pipeline run."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM agent_logs WHERE run_id = ? ORDER BY id ASC",
            (run_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_log_count() -> int:
    conn = get_connection()
    try:
        return conn.execute("SELECT COUNT(*) FROM agent_logs").fetchone()[0]
    finally:
        conn.close()


def delete_old_logs(days: int = 30):
    """Delete agent_logs and pipeline_runs older than N days."""
    conn = get_connection()
    try:
        cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).isoformat()
        conn.execute("DELETE FROM agent_logs WHERE run_id IN (SELECT id FROM pipeline_runs WHERE started_at < ?)", (cutoff,))
        conn.execute("DELETE FROM pipeline_runs WHERE started_at < ? AND article_id IS NULL", (cutoff,))
        conn.commit()
    finally:
        conn.close()


# =============================================================================
# SETTINGS
# =============================================================================

def get_setting(key: str) -> str | None:
    """Get a setting value by key (raw, may be encrypted)."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT value, encrypted FROM settings WHERE key = ?", (key,)).fetchone()
        if row:
            return row["value"]
        return None
    finally:
        conn.close()


def is_setting_encrypted(key: str) -> bool:
    """Check if a setting is stored encrypted."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT encrypted FROM settings WHERE key = ?", (key,)).fetchone()
        return bool(row and row["encrypted"])
    finally:
        conn.close()


def set_setting(key: str, value: str, encrypted: bool = False):
    """Upsert a setting."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO settings (key, value, encrypted) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = ?, encrypted = ?",
            (key, value, int(encrypted), value, int(encrypted)),
        )
        conn.commit()
    finally:
        conn.close()


def get_all_settings() -> dict:
    """Get all settings as a dict."""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT key, value, encrypted FROM settings").fetchall()
        return {r["key"]: {"value": r["value"], "encrypted": bool(r["encrypted"])} for r in rows}
    finally:
        conn.close()


# =============================================================================
# LICENSE CACHE
# =============================================================================

def get_license_cache() -> dict | None:
    """Get cached license info."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM license_cache WHERE id = 1").fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def save_license_cache(license_key: str, machine_code: str, status: str,
                       product: str = "", plan: str = "", expires_at: str = "",
                       token_data: str = ""):
    """Save or update license cache (always id=1, single user)."""
    conn = get_connection()
    try:
        now = datetime.datetime.now().isoformat()
        conn.execute(
            """INSERT INTO license_cache (id, license_key, machine_code, status, product, plan, expires_at, verified_at, token_data)
               VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 license_key = ?, machine_code = ?, status = ?, product = ?,
                 plan = ?, expires_at = ?, verified_at = ?, token_data = ?""",
            (license_key, machine_code, status, product, plan, expires_at, now, token_data,
             license_key, machine_code, status, product, plan, expires_at, now, token_data),
        )
        conn.commit()
    finally:
        conn.close()


def update_license_verified():
    """Update verified_at to now."""
    conn = get_connection()
    try:
        now = datetime.datetime.now().isoformat()
        conn.execute("UPDATE license_cache SET verified_at = ? WHERE id = 1", (now,))
        conn.commit()
    finally:
        conn.close()


def clear_license_cache():
    """Remove all license cache data."""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM license_cache")
        conn.commit()
    finally:
        conn.close()
