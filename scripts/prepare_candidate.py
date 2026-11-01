"""Create a new content-only trial database; never copy accounts or overwrite data."""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))


def prepare_snapshot(source,target):
    from app.database.connection import Store
    from app.services.rag_service import row_fingerprint
    source,target=Path(source).resolve(),Path(target).resolve()
    if not source.is_file() or target.exists():
        raise ValueError('An existing source and a new, empty target path are required; nothing was overwritten')
    with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        if db.execute('PRAGMA user_version').fetchone()[0]!=2:
            raise ValueError('Unsupported source database version')
        db.execute('BEGIN')
        snapshot={table:[dict(row) for row in db.execute('SELECT * FROM '+table+
            (' WHERE published=1' if table!='schedules' else '')+' ORDER BY id')]
            for table in ('books','knowledge','schedules')}
    target.mkdir(parents=True)
    store=Store(target/'library.sqlite3')
    with store.connect() as db:
        for table,rows in snapshot.items():
            columns=[row['name'] for row in db.execute('PRAGMA table_info('+table+')')]
            for row in rows:
                if not set(columns)<=row.keys():
                    raise ValueError('Incomplete source table; preserve partial target and choose a fresh directory')
                db.execute('INSERT INTO '+table+'('+','.join(columns)+') VALUES ('+','.join('?' for _ in columns)+')',
                    tuple(row[column] for column in columns))
        db.execute('CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
        db.executemany('INSERT INTO meta VALUES (?,?)',[('seeded','1'),('books_seeded','1')])
        assert not db.execute('SELECT 1 FROM users').fetchone()
        assert not db.execute('SELECT 1 FROM messages').fetchone()
    report={'schema_version':2,'counts':{table:len(rows) for table,rows in snapshot.items()},
        'source_hashes':{table:row_fingerprint(rows) for table,rows in snapshot.items()},
        'private_tables_copied':False,'copied_tables':list(snapshot)}
    (target/'public-snapshot.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True,help='Existing application library.sqlite3')
    parser.add_argument('--output',type=Path,required=True,help='New trial DATA_DIR; existing paths are refused')
    args=parser.parse_args()
    try:
        print(json.dumps(prepare_snapshot(args.source,args.output)))
    except ValueError as error:
        parser.error(str(error))


if __name__=='__main__':
    main()
