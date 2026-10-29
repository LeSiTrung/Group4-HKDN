import sqlite3
import pytest
from app.config import ROOT, Settings
from app.database.connection import Store


def test_relative_runtime_is_independent_of_launch_directory(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('DATA_DIR','runtime')
    assert Settings.load().data_dir == ROOT/'runtime'


def test_unknown_newer_schema_is_not_downgraded(tmp_path):
    path=tmp_path/'future.sqlite3'
    with sqlite3.connect(path) as db:
        db.execute('PRAGMA user_version=999')
        db.execute('CREATE TABLE future_data(value TEXT)')
        db.execute("INSERT INTO future_data VALUES ('preserve me')")
    with pytest.raises(RuntimeError,match='newer'):
        Store(path)
    with sqlite3.connect(path) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0]==999
        assert db.execute('SELECT value FROM future_data').fetchone()[0]=='preserve me'


def test_v1_message_migration_preserves_existing_history(tmp_path):
    path=tmp_path/'library.sqlite3'
    store=Store(path)
    with store.connect() as db:
        db.execute("INSERT INTO users(email,name,password_hash) VALUES ('fixture@example.test','Reader','synthetic-hash')")
        db.execute("INSERT INTO conversations(user_id,title) VALUES (1,'Existing conversation')")
        db.execute("INSERT INTO messages(conversation_id,role,content) VALUES (1,'user','Existing message')")
        db.execute('ALTER TABLE messages DROP COLUMN books')
        db.execute('ALTER TABLE messages DROP COLUMN context_query')
        db.execute('PRAGMA user_version=1')
    migrated=Store(path)
    with migrated.connect() as db:
        row=db.execute('SELECT * FROM messages').fetchone()
        assert row['content']=='Existing message' and row['books']=='[]' and row['context_query']==''
        assert db.execute('PRAGMA user_version').fetchone()[0]==2
