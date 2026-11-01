import pytest

from app.database.connection import Store
from scripts.prepare_candidate import prepare_snapshot


def test_candidate_copies_only_public_content_and_does_not_seed_duplicates(tmp_path):
    source=Store(tmp_path/'main'/'library.sqlite3')
    with source.connect() as db:
        db.execute("INSERT INTO users(email,name,password_hash) VALUES ('private@example.test','private user','private hash')")
        cid=db.execute("INSERT INTO conversations(user_id,title) VALUES (1,'private history')").lastrowid
        db.execute("INSERT INTO messages(conversation_id,role,content) VALUES (?,'user','private message')",(cid,))
        for published in (0,1):
            db.execute('INSERT INTO books(title,source_url,checked_at,published) VALUES (?,?,?,?)',
                ('Public' if published else 'Draft',f'https://lic.ut.edu.vn/snapshot-{published}','2026-10-31',published))
    target=tmp_path/'candidate'
    report=prepare_snapshot(source.path,target)
    assert report['counts']['books']==1 and report['private_tables_copied'] is False
    candidate=Store(target/'library.sqlite3')
    with candidate.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM users').fetchone()[0]==0
        assert db.execute('SELECT COUNT(*) FROM messages').fetchone()[0]==0
        assert db.execute('SELECT title FROM books').fetchone()[0]=='Public'
        assert dict(db.execute('SELECT key,value FROM meta'))=={'seeded':'1','books_seeded':'1'}
    with source.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM users').fetchone()[0]==1
        assert db.execute('SELECT COUNT(*) FROM books').fetchone()[0]==2


def test_snapshot_refuses_missing_source_or_existing_target(tmp_path):
    with pytest.raises(ValueError):
        prepare_snapshot(tmp_path/'missing.sqlite3',tmp_path/'new')
    assert not (tmp_path/'new').exists()
    source=Store(tmp_path/'library.sqlite3')
    target=tmp_path/'existing'; target.mkdir()
    marker=target/'marker'; marker.write_text('preserve')
    with pytest.raises(ValueError):
        prepare_snapshot(source.path,target)
    assert marker.read_text()=='preserve'
