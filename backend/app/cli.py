"""Operator commands. Run from backend: python -m app.cli --help."""
import argparse
import getpass
import json
import sqlite3
from pathlib import Path
from .config import Settings, ROOT
from .database.connection import Store
from .api.auth import password_hash, Registration
from .services.knowledge import KnowledgeInput, insert_knowledge, seed, published_rows
from .services.rag_service import VectorIndex
from .services import llm_service


def main():
    parser=argparse.ArgumentParser(description='Library assistant operator tools')
    sub=parser.add_subparsers(dest='command',required=True)
    admin=sub.add_parser('create-admin')
    admin.add_argument('--email',required=True)
    admin.add_argument('--name',default='Quản trị viên')
    indexing=sub.add_parser('index')
    indexing.add_argument('--namespace',choices=('knowledge','books'),default='knowledge')
    sub.add_parser('ai-check')
    knowledge=sub.add_parser('import-knowledge')
    knowledge.add_argument('file',type=Path)
    backup=sub.add_parser('backup')
    backup.add_argument('directory',type=Path)
    args=parser.parse_args()
    if args.command=='ai-check':
        result=llm_service.check_model()
        print(json.dumps(result,ensure_ascii=False))
        raise SystemExit(0 if result['ready'] else 1)
    if args.command=='import-knowledge':
        try:
            raw=json.loads(args.file.read_text(encoding='utf-8'))
            if not isinstance(raw,list):
                raise ValueError
            entries=[KnowledgeInput.model_validate(row) for row in raw]
        except (OSError,ValueError,TypeError,RecursionError):
            parser.error('Knowledge pack must be a JSON list of valid, dated KnowledgeInput records; nothing was imported.')
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
    elif args.command=='import-knowledge':
        imported=0
        with store.connect() as db:
            for entry in entries:
                if db.execute('SELECT 1 FROM knowledge WHERE question=? AND source_url=?',(entry.question,entry.source_url)).fetchone():
                    continue
                insert_knowledge(db,entry)
                imported+=1
            db.execute("INSERT INTO audit(action,target) VALUES ('knowledge.import',?)",(str(imported),))
        print(json.dumps({'imported':imported,'skipped':len(entries)-imported}))
    elif args.command=='index':
        index=VectorIndex(settings)
        try:
            rows=published_rows(store.connect)
            if args.namespace=='books':
                from .services.catalog import item,book_documents
                with store.connect() as db:
                    rows=book_documents([item(row) for row in db.execute('SELECT * FROM books WHERE published=1')])
            count=index.rebuild(rows,namespace=args.namespace)
            print(json.dumps({'indexed':count,'model':index.model_name,**index.status()}))
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
