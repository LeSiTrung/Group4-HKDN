"""Operator commands. Run from backend: python -m app.cli --help."""
import argparse
import getpass
import json
import sqlite3
from pathlib import Path
from .config import Settings, ROOT
from .database.connection import Store
from .api.auth import password_hash, Registration
from .services.knowledge import seed, published_rows
from .services.rag_service import VectorIndex


def main():
    parser=argparse.ArgumentParser(description='D7 operator tools')
    sub=parser.add_subparsers(dest='command',required=True)
    admin=sub.add_parser('create-admin')
    admin.add_argument('--email',required=True)
    admin.add_argument('--name',default='Quản trị viên')
    sub.add_parser('index')
    backup=sub.add_parser('backup')
    backup.add_argument('directory',type=Path)
    args=parser.parse_args()
    settings=Settings.load()
    store=Store(settings.data_dir/'library.sqlite3')
    seed(store.connect,ROOT.parent/'data/faq/library.json')
    if args.command=='create-admin':
        password=getpass.getpass('New administrator password (12+ characters): ')
        if password!=getpass.getpass('Confirm password: '):
            parser.error('Passwords do not match.')
        account=Registration(email=args.email,name=args.name,password=password)
        with store.connect() as db:
            if db.execute('SELECT 1 FROM users WHERE email=?',(account.email,)).fetchone():
                parser.error('Account already exists; no role or password was changed.')
            db.execute("INSERT INTO users(email,name,password_hash,role) VALUES (?,?,?,'admin')",(account.email,account.name,password_hash.hash(password)))
        print('Administrator created. No library credentials were configured.')
    elif args.command=='index':
        index=VectorIndex(settings)
        try:
            print(json.dumps({'indexed':index.rebuild(published_rows(store.connect)),'model':index.model_name}))
        finally:
            index.close()
    else:
        args.directory.mkdir(parents=True,exist_ok=True)
        target=args.directory/'library.sqlite3'
        if target.exists():
            parser.error('Backup already exists; choose a new directory.')
        with store.connect() as source, sqlite3.connect(target) as destination:
            source.backup(destination)
        print('SQLite backup created. Protect it as private data. Rebuild vector index after restore.')


if __name__=='__main__':
    main()
