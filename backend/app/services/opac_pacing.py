"""One durable request clock shared by OPAC workers on the same data volume."""
import sqlite3
import time
from contextlib import closing

from ..config import Settings


def wait_for_turn(*,minimum_gap=10,max_wait=20):
    path=Settings.load().data_dir/'opac-pacing.sqlite3'
    path.parent.mkdir(parents=True,exist_ok=True)
    deadline=time.time()+max_wait if max_wait is not None else None
    while True:
        with closing(sqlite3.connect(path,timeout=2)) as db,db:
            db.execute('CREATE TABLE IF NOT EXISTS request_clock (id INTEGER PRIMARY KEY CHECK(id=1), next_at REAL NOT NULL, minimum_gap REAL NOT NULL, reader_until REAL NOT NULL DEFAULT 0)')
            db.execute('BEGIN IMMEDIATE')
            if 'reader_until' not in {row[1] for row in db.execute('PRAGMA table_info(request_clock)')}:
                db.execute('ALTER TABLE request_clock ADD COLUMN reader_until REAL NOT NULL DEFAULT 0')
            row=db.execute('SELECT next_at,minimum_gap,reader_until FROM request_clock WHERE id=1').fetchone()
            now=time.time()
            delay=max(0,row[0]-now) if row else 0
            priority=row[2] if row else 0
            if deadline is not None and delay:
                priority=max(priority,deadline)
                db.execute('UPDATE request_clock SET reader_until=? WHERE id=1',(priority,))
            elif deadline is None:
                delay=max(delay,priority-now)
            if not delay:
                gap=max(10,minimum_gap,row[1] if row else 10)
                db.execute('INSERT OR REPLACE INTO request_clock VALUES (1,?,?,?)',(now+gap,gap,priority))
                return
        if deadline is not None and now+delay>deadline:
            raise TimeoutError('OPAC request queue is busy')
        time.sleep(min(delay,1))
