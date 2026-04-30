import hashlib
import sqlite3
import threading
import time
from datetime import datetime, timedelta
import numpy as np
import config

class RecallDB:
    def __init__(self, embed_fn):
        self._get_embedding = embed_fn
        self._conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._db_lock = threading.Lock()
        self._l1_cache = {}
        self._l1_lock = threading.Lock()
        self._l1_max_entries = 1024
        self._conn.enable_load_extension(True)
        self._vec_ready = False
        try:
            if config.VEC_DLL_PATH.exists():
                self._conn.load_extension(str(config.VEC_DLL_PATH))
                self._vec_ready = True
        except Exception: pass
        self._init_db()

    def _init_db(self):
        dim = getattr(config, "EMBED_DIM", 768)
        scripts = [
            "CREATE TABLE IF NOT EXISTS data (id INTEGER PRIMARY KEY, ts TEXT, type TEXT, app TEXT, title TEXT, content TEXT, img TEXT, url TEXT)",
            "CREATE INDEX IF NOT EXISTS idx_ts ON data(ts DESC)",
            "CREATE TABLE IF NOT EXISTS app_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS vec_map (vec_rowid INTEGER PRIMARY KEY, data_id INTEGER NOT NULL)",
            "CREATE TABLE IF NOT EXISTS embedding_cache (content_hash TEXT PRIMARY KEY, embedding_blob BLOB, hit_count INTEGER DEFAULT 1, last_used REAL)",
            "CREATE INDEX IF NOT EXISTS idx_cache_last_used ON embedding_cache(last_used)",
        ]
        for s in scripts: self._conn.execute(s)
        self._set_meta("schema_version", "1")
        self._set_meta("embedding_dim", str(dim))
        if self._vec_ready:
            try: 
                self._conn.execute(f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_idx USING vec0(embedding float[{dim}])")
            except Exception as e: 
                self._vec_ready = False
        self._conn.commit()

    def _get_meta(self, key):
        row = self._conn.execute("SELECT value FROM app_meta WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def _set_meta(self, key, value):
        self._conn.execute("INSERT INTO app_meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))

    def rename_record(self, record_id, new_title):
        with self._db_lock:
            self._conn.execute("UPDATE data SET title = ? WHERE id = ?", (new_title, record_id))
            self._conn.commit()

    def save(self, dtype, app, title, content, img="", url=""):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._db_lock:
            cur = self._conn.cursor()
            cur.execute("INSERT INTO data (ts, type, app, title, content, img, url) VALUES (?,?,?,?,?,?,?)", (ts, dtype, app, title, content, img, url))
            rowid = cur.lastrowid
            self._conn.commit()
            
        if self._vec_ready and self._get_embedding and (title or content):
            text_to_embed = f"{title}\n{content}"
            threading.Thread(target=self._save_embedding_bg, args=(rowid, text_to_embed), daemon=True).start()
            
        return rowid

    def _save_embedding_bg(self, rowid, text):
        emb = self._get_embedding(text)
        if emb:
            emb_bytes = np.array(emb, dtype=np.float32).tobytes()
            with self._db_lock:
                try:
                    existing = self._conn.execute("SELECT rowid FROM vec_idx WHERE rowid = ?", (rowid,)).fetchone()
                    if not existing:
                        self._conn.execute("INSERT INTO vec_idx(rowid, embedding) VALUES (?, ?)", (rowid, emb_bytes))
                        self._conn.commit()
                except Exception as e:
                    config.logger.error(f"寫入向量索引失敗 (ID:{rowid}): {e}", exc_info=True)

    def query_records(self, limit=100, filters=None, sort="newest"):
        where, params = self._build_filter_clause(filters)
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        order = {"oldest": "ts ASC", "app": "app, ts DESC", "newest": "ts DESC"}.get(sort, "ts DESC")
        sql = f"SELECT id, type, ts, app, title, content, img, url, NULL FROM data {where_sql} ORDER BY {order} LIMIT ?"
        rows = self._conn.execute(sql, (*params, limit)).fetchall()
        return [dict(r) for r in rows]

    def _build_filter_clause(self, filters):
        filters = filters or {}
        where, params = [], []
        if filters.get("app") and filters["app"] != "全部":
            where.append("app = ?"); params.append(filters["app"])
        if filters.get("type") and filters["type"] != "全部":
            where.append("type = ?"); params.append(filters["type"])
        if filters.get("since"):
            where.append("ts >= ?"); params.append(filters["since"])
        return where, params

    def get_sessions(self, limit: int = 100, filters: dict = None, gap_minutes: int = 5) -> list[dict]:
        where_sql, params = self._build_filter_clause(filters)
        where_clause = f"WHERE {' AND '.join(where_sql)}" if where_sql else ""
        gap_seconds = gap_minutes * 60

        sql = f"""
        WITH TimeDiffs AS (
            SELECT id, ts, app, title, content, img, url,
                   (julianday(ts) - julianday(lag(ts, 1, ts) OVER (ORDER BY ts ASC))) * 86400.0 AS gap_sec,
                   lag(app, 1, app) OVER (ORDER BY ts ASC) as prev_app
            FROM data {where_clause}
        ),
        SessionMarkers AS (
            SELECT *, CASE WHEN gap_sec > {gap_seconds} OR app != prev_app THEN 1 ELSE 0 END as is_new
            FROM TimeDiffs
        ),
        SessionGroups AS (
            SELECT *, SUM(is_new) OVER (ORDER BY ts ASC) as session_id
            FROM SessionMarkers
        ),
        Aggregated AS (
            SELECT session_id, MIN(ts) as start_time, MAX(ts) as end_time, app, 
                   COUNT(*) as count, GROUP_CONCAT(id) as ids
            FROM SessionGroups
            GROUP BY session_id
        )
        SELECT a.start_time as start, a.end_time as end, a.app, a.count, a.ids,
               g.title, g.content, g.img, g.url
        FROM Aggregated a
        JOIN SessionGroups g ON a.session_id = g.session_id AND a.start_time = g.ts
        ORDER BY a.start_time DESC
        LIMIT ?
        """
        with self._db_lock:
            rows = self._conn.execute(sql, (*params, limit)).fetchall()
            
        sessions = []
        for r in rows:
            session_dict = dict(r)
            session_dict["ids"] = [int(i) for i in str(session_dict["ids"]).split(",")]
            sessions.append(session_dict)
        return sessions

    def get_filter_options(self):
        with self._db_lock:
            apps = [r[0] for r in self._conn.execute("SELECT DISTINCT app FROM data WHERE app != '' ORDER BY app").fetchall()]
            types = [r[0] for r in self._conn.execute("SELECT DISTINCT type FROM data WHERE type != '' ORDER BY type").fetchall()]
        return apps, types

    def delete_records(self, ids, delete_screenshots=True):
        if not ids: return 0
        ids = [int(i) for i in ids]
        placeholders = ",".join("?" for _ in ids)
        with self._db_lock:
            img_rows = self._conn.execute(f"SELECT img FROM data WHERE id IN ({placeholders}) AND img != ''", ids).fetchall()
            self._conn.execute(f"DELETE FROM data WHERE id IN ({placeholders})", ids)
            if delete_screenshots:
                for (img_name,) in img_rows:
                    if img_name:
                        img_path = config.SCREENSHOT_DIR / img_name
                        try:
                            if img_path.exists():
                                img_path.unlink()
                        except Exception as e:
                            config.logger.warning(f"刪除截圖實體檔案失敗 ({img_name}): {e}")
            self._conn.commit()
        return len(ids)

    def purge_records_older_than(self, days, delete_screenshots=True):
        cutoff = (datetime.now() - timedelta(days=int(days))).strftime("%Y-%m-%d %H:%M:%S")
        with self._db_lock:
            rows = self._conn.execute("SELECT id FROM data WHERE ts < ?", (cutoff,)).fetchall()
        return self.delete_records([r[0] for r in rows], delete_screenshots=delete_screenshots)

    def purge_old_cache(self, max_entries=50000):
        with self._db_lock:
            try:
                count_row = self._conn.execute("SELECT COUNT(*) FROM embedding_cache").fetchone()
                current_count = count_row[0] if count_row else 0
                if current_count > max_entries:
                    delete_count = current_count - max_entries
                    sql = """
                        DELETE FROM embedding_cache 
                        WHERE content_hash IN (
                            SELECT content_hash 
                            FROM embedding_cache 
                            ORDER BY last_used ASC 
                            LIMIT ?
                        )
                    """
                    self._conn.execute(sql, (delete_count,))
                    self._conn.commit()
            except Exception as e:
                config.logger.warning(f"清理 Embedding 快取失敗: {e}", exc_info=True)

    def vector_search(self, query, limit=10, filters=None):
        if not self._vec_ready or not self._get_embedding:
            return self.query_records(limit, filters)
        emb = self._get_embedding(query)
        if not emb: 
            return []
        emb_bytes = np.array(emb, dtype=np.float32).tobytes()
        where_sql, params = self._build_filter_clause(filters)
        filter_str = f"AND {' AND '.join(where_sql)}" if where_sql else ""
        sql = f"""
            SELECT d.id, d.type, d.ts, d.app, d.title, d.content, d.img, d.url, v.distance
            FROM vec_idx v
            JOIN data d ON v.rowid = d.id
            WHERE v.embedding MATCH ? AND k = ? {filter_str}
            ORDER BY v.distance ASC
        """
        with self._db_lock:
            try:
                rows = self._conn.execute(sql, (emb_bytes, limit, *params)).fetchall()
                return [dict(r) for r in rows]
            except Exception as e:
                config.logger.error(f"向量搜尋失敗: {e}", exc_info=True)
                return []
