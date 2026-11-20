import sqlite3
import pytest
from app.config import ROOT, Settings
from app.database.connection import SCHEMA, Store
from scripts.restore import restore


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


def test_restore_rejects_backup_newer_than_application_schema(tmp_path):
    source = tmp_path / 'future.sqlite3'
    store = Store(source)
    with store.connect() as db:
        db.execute('PRAGMA user_version=999')
    target = tmp_path / 'restore' / 'library.sqlite3'
    with pytest.raises(ValueError, match='newer'):
        restore(source, target)
    assert not target.parent.exists()


def test_restore_rejects_backup_with_orphaned_history(tmp_path):
    source = Store(tmp_path / 'library.sqlite3').path
    with sqlite3.connect(source) as db:
        db.execute('PRAGMA foreign_keys=OFF')
        db.execute("INSERT INTO conversations(user_id,title) VALUES (99,'Saved conversation')")
        assert db.execute('PRAGMA quick_check').fetchone() == ('ok',)
    target = tmp_path / 'restore' / 'library.sqlite3'
    with pytest.raises(ValueError, match='foreign key'):
        restore(source, target)
    assert not target.exists()


def test_v1_message_migration_preserves_existing_history(tmp_path):
    path=tmp_path/'library.sqlite3'
    with sqlite3.connect(path) as db:
        db.executescript(SCHEMA.replace('PRIMARY KEY AUTOINCREMENT','PRIMARY KEY',2))
        db.execute("INSERT INTO users(email,name,password_hash) VALUES ('fixture@example.test','Reader','synthetic-hash')")
        db.execute("INSERT INTO conversations(user_id,title) VALUES (1,'Existing conversation')")
        db.execute("INSERT INTO messages(conversation_id,role,content) VALUES (1,'user','Existing message')")
        db.execute("INSERT INTO messages(conversation_id,role,content) VALUES (1,'assistant','Existing answer')")
        db.execute("INSERT INTO feedback VALUES (1,2,1,'Useful')")
        db.execute('ALTER TABLE messages DROP COLUMN books')
        db.execute('ALTER TABLE messages DROP COLUMN context_query')
        db.execute('ALTER TABLE messages DROP COLUMN list_book_ids')
        db.execute('PRAGMA user_version=1')
    migrated=Store(path)
    with migrated.connect() as db:
        row=db.execute('SELECT * FROM messages').fetchone()
        assert row['content']=='Existing message' and row['books']=='[]' and row['context_query']==''
        assert row['list_book_ids']=='[]'
        assert db.execute('PRAGMA user_version').fetchone()[0]==3
        assert tuple(db.execute('SELECT * FROM feedback').fetchone()) == (1,2,1,'Useful')
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
        for table, index in [('messages','ix_messages_conversation'), ('conversations','ix_conversations_user')]:
            assert index in {row['name'] for row in db.execute(f'PRAGMA index_list({table})')}
        db.execute('DELETE FROM conversations')
        assert not db.execute('SELECT 1 FROM feedback').fetchone()
        cid = db.execute("INSERT INTO conversations(user_id,title) VALUES (1,'New chat')").lastrowid
        mid = db.execute("INSERT INTO messages(conversation_id,role,content) VALUES (?,'user','Hello')",(cid,)).lastrowid
        assert cid > 1 and mid > 2
