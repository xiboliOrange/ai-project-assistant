import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class FileRepository:
    def __init__(self, database_path: Path):
        self.database_path = database_path

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self):
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY,
                    original_filename TEXT NOT NULL,
                    stored_filename TEXT NOT NULL UNIQUE,
                    file_path TEXT NOT NULL UNIQUE,
                    file_type TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    uploaded_at TEXT NOT NULL,
                    summary TEXT,
                    keywords TEXT,
                    summary_source TEXT,
                    keywords_source TEXT
                )
            """)

    @staticmethod
    def _metadata(row):
        if row is None:
            return None
        item = dict(row)
        item["keywords"] = json.loads(item["keywords"]) if item["keywords"] else []
        return item

    def add(self, original_filename, stored_filename, file_path, file_type, file_size, uploaded_at):
        with self._connect() as connection:
            cursor = connection.execute("""
                INSERT INTO files (original_filename, stored_filename, file_path,
                                   file_type, file_size, uploaded_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (original_filename, stored_filename, file_path,
                  file_type, file_size, uploaded_at))
            return cursor.lastrowid

    def list(self):
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM files ORDER BY uploaded_at DESC, id DESC"
            ).fetchall()
        return [self._metadata(row) for row in rows]

    def get(self, file_id):
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
        return self._metadata(row)

    def update_user(self, file_id, changes):
        assignments = []
        values = []
        if "summary" in changes:
            assignments.extend(["summary = ?", "summary_source = 'user'"])
            values.append(changes["summary"])
        if "keywords" in changes:
            assignments.extend(["keywords = ?", "keywords_source = 'user'"])
            values.append(json.dumps(changes["keywords"], ensure_ascii=False))
        if assignments:
            with self._connect() as connection:
                connection.execute(
                    f"UPDATE files SET {', '.join(assignments)} WHERE id = ?",
                    (*values, file_id),
                )
        return self.get(file_id)

    def update_llm(self, file_id, summary, keywords):
        with self._connect() as connection:
            connection.execute("""
                UPDATE files SET
                    summary = CASE WHEN summary_source = 'user' THEN summary ELSE ? END,
                    summary_source = CASE WHEN summary_source = 'user' THEN summary_source ELSE 'llm' END,
                    keywords = CASE WHEN keywords_source = 'user' THEN keywords ELSE ? END,
                    keywords_source = CASE WHEN keywords_source = 'user' THEN keywords_source ELSE 'llm' END
                WHERE id = ?
            """, (summary, json.dumps(keywords, ensure_ascii=False), file_id))
        return self.get(file_id)
