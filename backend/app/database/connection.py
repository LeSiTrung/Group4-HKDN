"""Short-lived transactional connections; always rollback and close on failure."""
import sqlite3
from contextlib import contextmanager

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
 password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'reader', active INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')));
CREATE TABLE IF NOT EXISTS sessions (
 token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, expires_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS conversations (
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, title TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
 updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')));
CREATE TABLE IF NOT EXISTS messages (
 id INTEGER PRIMARY KEY, conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
 role TEXT NOT NULL, content TEXT NOT NULL, sources TEXT NOT NULL DEFAULT '[]', status TEXT NOT NULL DEFAULT '', mode TEXT NOT NULL DEFAULT '',
 books TEXT NOT NULL DEFAULT '[]', context_query TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')));
CREATE TABLE IF NOT EXISTS feedback (
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
 rating INTEGER NOT NULL CHECK(rating IN (-1,1)), comment TEXT NOT NULL DEFAULT '', PRIMARY KEY(user_id,message_id));
CREATE TABLE IF NOT EXISTS knowledge (
 id INTEGER PRIMARY KEY, title TEXT NOT NULL, question TEXT NOT NULL, aliases TEXT NOT NULL DEFAULT '[]', keywords TEXT NOT NULL DEFAULT '[]',
 answer TEXT NOT NULL, category TEXT NOT NULL, source_url TEXT NOT NULL, source_title TEXT NOT NULL,
 checked_at TEXT NOT NULL, status TEXT NOT NULL, published INTEGER NOT NULL DEFAULT 0, valid_from TEXT, valid_until TEXT, verified_by TEXT,
 updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')));
CREATE TABLE IF NOT EXISTS schedules (
 id INTEGER PRIMARY KEY, branch TEXT NOT NULL, weekday INTEGER NOT NULL, opens TEXT NOT NULL, closes TEXT NOT NULL,
 valid_from TEXT NOT NULL, valid_until TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', verified_by TEXT NOT NULL,
 source_url TEXT NOT NULL, source_title TEXT NOT NULL, checked_at TEXT NOT NULL, closed INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS jobs (
 id INTEGER PRIMARY KEY, url TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'queued', imported INTEGER NOT NULL DEFAULT 0, error TEXT,
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')));
CREATE TABLE IF NOT EXISTS audit (
 id INTEGER PRIMARY KEY, actor_id INTEGER REFERENCES users(id) ON DELETE SET NULL, action TEXT NOT NULL, target TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')));
CREATE TABLE IF NOT EXISTS renewals (
 idempotency_key TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, loan_id TEXT NOT NULL, state TEXT NOT NULL, result TEXT);
CREATE TABLE IF NOT EXISTS books (
 id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, author TEXT NOT NULL DEFAULT '', year TEXT NOT NULL DEFAULT '',
 kind TEXT NOT NULL DEFAULT 'books', subjects TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '',
 source_url TEXT NOT NULL UNIQUE, checked_at TEXT NOT NULL, published INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS ix_messages_conversation ON messages(conversation_id,id);
CREATE INDEX IF NOT EXISTS ix_conversations_user ON conversations(user_id,updated_at);
"""


class Store:
    def __init__(self, path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            if db.execute('PRAGMA user_version').fetchone()[0]>2:
                raise RuntimeError('Database was created by a newer application; refusing to downgrade it.')
            db.executescript(SCHEMA)
            columns={x[1] for x in db.execute('PRAGMA table_info(messages)')}
            if 'books' not in columns:
                db.execute("ALTER TABLE messages ADD COLUMN books TEXT NOT NULL DEFAULT '[]'")
            if 'context_query' not in columns:
                db.execute("ALTER TABLE messages ADD COLUMN context_query TEXT NOT NULL DEFAULT ''")
            db.execute('PRAGMA user_version=2')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(str(self.path), timeout=15)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA busy_timeout=15000')
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


def get_database_status():
    return 'sqlite'
