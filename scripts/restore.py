"""Restore a library assistant SQLite backup into a new directory, never over live data."""
import argparse
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

TABLES = {'users', 'sessions', 'knowledge', 'conversations', 'messages'}


def restore(source: Path, destination: Path):
    with closing(sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True)) as backup:
        if backup.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
            raise ValueError('Source database integrity check failed.')
        tables = {row[0] for row in backup.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not TABLES <= tables:
            raise ValueError('Source is not a library assistant application database.')
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('xb'):
            pass
        try:
            with closing(sqlite3.connect(destination)) as target, target:
                backup.backup(target)
                target.execute('DELETE FROM sessions')
                if target.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
                    raise ValueError('Restored database integrity check failed.')
        except Exception:
            destination.unlink()
            raise


def self_test():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source, target = root / 'source.sqlite3', root / 'new' / 'library.sqlite3'
        with closing(sqlite3.connect(source)) as db, db:
            for table in TABLES:
                db.execute(f'CREATE TABLE {table}(value TEXT)')
            db.execute("INSERT INTO users VALUES ('reader')")
            db.execute("INSERT INTO sessions VALUES ('old-token')")
            db.execute('CREATE TABLE renewals(state TEXT)')
            db.execute("INSERT INTO renewals VALUES ('uncertain')")
            db.execute('CREATE TABLE channel_events(state TEXT)')
            db.execute("INSERT INTO channel_events VALUES ('processing')")
        restore(source, target)
        with closing(sqlite3.connect(target)) as db:
            assert db.execute('SELECT value FROM users').fetchone() == ('reader',)
            assert db.execute('SELECT count(*) FROM sessions').fetchone() == (0,)
            assert db.execute('SELECT state FROM renewals').fetchone() == ('uncertain',)
            assert db.execute('SELECT state FROM channel_events').fetchone() == ('processing',)
        try:
            restore(source, target)
        except FileExistsError:
            pass
        else:
            raise AssertionError('Restore overwrote an existing destination')
        invalid = root / 'invalid.sqlite3'
        invalid.write_bytes(b'not a database')
        try:
            restore(invalid, root / 'bad' / 'library.sqlite3')
        except sqlite3.DatabaseError:
            pass
        else:
            raise AssertionError('Restore accepted an invalid database')
        assert not (root / 'bad').exists()
    print('Restore self-test passed: rows/ledgers retained, sessions revoked, overwrite/corruption refused.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, nargs='?')
    parser.add_argument('destination', type=Path, nargs='?')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        self_test()
    elif not args.source or not args.destination:
        parser.error('Provide source backup and a new destination library.sqlite3 path.')
    else:
        restore(args.source, args.destination)
        print('Restore verified. Sessions revoked. Set DATA_DIR to the destination parent and rebuild vectors.')
